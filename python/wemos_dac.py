import serial
import numpy as np
import threading
import queue
import time


class WemosDAC:

    HEADER = 0xAA
    STOP = 0xBB
    PACKET_SAMPLES = 1023

    def __init__(
        self,
        port,
        baudrate=2_000_000,
        sample_rate=100_000,
        buffer_packets=20,
        ack_timeout=2.0
    ):
        self.port = port
        self.baudrate = baudrate
        self.sample_rate = sample_rate
        self.buffer_packets = buffer_packets
        self.ack_timeout = ack_timeout

        self.ser = None

        self.sample_queue = queue.Queue(
            maxsize=self.PACKET_SAMPLES * buffer_packets
        )

        self.running = False
        self.finish_requested = False

        self.worker = None
        self.error = None

        self.finish_event = threading.Event()

    # =========================================================
    # SERIAL
    # =========================================================

    def open(self):

        if self.ser is not None:
            return

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.ack_timeout,
            dsrdtr=False,
            rtscts=False
        )

        self.ser.dtr = False
        self.ser.rts = False

        time.sleep(3)

        self.ser.reset_input_buffer()

    # =========================================================
    # FLOAT -> UINT8
    # =========================================================

    @staticmethod
    def _float_to_uint8(samples):

        samples = np.asarray(
            samples,
            dtype=np.float32
        )

        samples = np.clip(
            samples,
            -1.0,
            1.0
        )

        samples = (
            127.5 +
            127.5 * samples
        )

        return samples.astype(np.uint8)

    # =========================================================
    # WRITE
    # =========================================================

    def write(self, samples):

        if not self.running:
            raise RuntimeError(
                "Driver is not running."
            )

        if self.finish_requested:
            raise RuntimeError(
                "Stream is already finishing."
            )

        samples = self._float_to_uint8(samples)

        for sample in samples:
            self.sample_queue.put(
                int(sample)
            )

    # =========================================================
    # MAKE FULL PACKET
    # =========================================================

    def _make_packet(self):

        samples = np.empty(
            self.PACKET_SAMPLES,
            dtype=np.uint8
        )

        for i in range(self.PACKET_SAMPLES):
            samples[i] = self.sample_queue.get()

        return (
            bytes([self.HEADER]) +
            samples.tobytes()
        )

    # =========================================================
    # MAKE FINAL PACKET
    # =========================================================

    def _make_final_packet(self):

        samples = np.full(
            self.PACKET_SAMPLES,
            128,
            dtype=np.uint8
        )

        count = 0

        while (
            count < self.PACKET_SAMPLES
            and not self.sample_queue.empty()
        ):
            samples[count] = self.sample_queue.get()
            count += 1

        return (
            bytes([self.HEADER]) +
            samples.tobytes()
        )

    # =========================================================
    # START
    # =========================================================

    def start(self):

        if self.running:
            return

        self.open()

        self.error = None
        self.finish_requested = False
        self.finish_event.clear()

        self.running = True

        self.worker = threading.Thread(
            target=self._stream_worker,
            daemon=True
        )

        self.worker.start()

    # =========================================================
    # STREAM WORKER
    # =========================================================

    def _stream_worker(self):

        try:

            required = (
                2 *
                self.PACKET_SAMPLES
            )

            # -------------------------------------------------
            # Wait for first two packets
            # -------------------------------------------------

            while self.running:

                if self.sample_queue.qsize() >= required:
                    break

                time.sleep(0.001)

            if not self.running:
                return

            # -------------------------------------------------
            # Send exactly two initial packets
            # -------------------------------------------------

            packet1 = self._make_packet()
            packet2 = self._make_packet()

            self.ser.write(packet1)
            self.ser.write(packet2)
            self.ser.flush()

            # -------------------------------------------------
            # ACK-driven streaming
            # -------------------------------------------------

            while self.running:

                ack = self.ser.read(1)

                if len(ack) == 0:
                    raise RuntimeError(
                        "ACK timeout."
                    )

                # -------------------------------------------------
                # ACK = 0xAA
                # -------------------------------------------------

                if ack[0] == self.HEADER:

                    # -------------------------------------------------
                    # Finish requested
                    # -------------------------------------------------

                    if self.finish_requested:

                        # Send exactly one final packet.
                        # Remaining samples are followed by
                        # zero-amplitude samples = 128.
                        packet = self._make_final_packet()

                        self.ser.write(packet)
                        self.ser.flush()

                        # -------------------------------------------------
                        # Wait for final packet ACK
                        # -------------------------------------------------

                        final_ack = self.ser.read(1)

                        if len(final_ack) == 0:
                            raise RuntimeError(
                                "Final ACK timeout."
                            )

                        if final_ack[0] != self.HEADER:
                            raise RuntimeError(
                                "Unexpected final ACK: "
                                f"0x{final_ack[0]:02X}"
                            )

                        # -------------------------------------------------
                        # Send STOP
                        # -------------------------------------------------

                        self.ser.write(
                            bytes([self.STOP])
                        )

                        self.ser.flush()

                        # -------------------------------------------------
                        # Wait for STOP ACK.
                        #
                        # Ignore any extra AA ACKs that may already
                        # be waiting in the serial input buffer.
                        # -------------------------------------------------

                        stop_start = time.monotonic()

                        while True:

                            if (
                                time.monotonic() - stop_start
                                > self.ack_timeout
                            ):
                                raise RuntimeError(
                                    "STOP ACK timeout."
                                )

                            stop_ack = self.ser.read(1)

                            if len(stop_ack) == 0:
                                continue

                            if stop_ack[0] == self.STOP:
                                break

                            if stop_ack[0] == self.HEADER:
                                continue

                            raise RuntimeError(
                                "Unexpected byte while waiting "
                                f"for STOP ACK: 0x{stop_ack[0]:02X}"
                            )

                        self.running = False
                        self.finish_event.set()

                        break

                    # -------------------------------------------------
                    # Normal packet
                    # -------------------------------------------------

                    packet = self._make_packet()

                    self.ser.write(packet)
                    self.ser.flush()

                # -------------------------------------------------
                # STOP
                # -------------------------------------------------

                elif ack[0] == self.STOP:

                    self.running = False
                    self.finish_event.set()

                    break

                # -------------------------------------------------
                # Unexpected byte
                # -------------------------------------------------

                else:

                    raise RuntimeError(
                        "Unexpected byte from Wemos: "
                        f"0x{ack[0]:02X}"
                    )

        except Exception as e:

            self.error = e
            self.running = False
            self.finish_event.set()

    # =========================================================
    # FINISH
    # =========================================================

    def finish(self):

        if not self.running:
            if self.error is not None:
                raise self.error
            return

        if self.finish_requested:
            return

        self.finish_requested = True

        self.finish_event.wait()

        if self.error is not None:
            raise self.error

    # =========================================================
    # EMERGENCY STOP
    # =========================================================

    def stop(self):

        if not self.running:
            return

        self.running = False

        try:

            if self.ser is not None:

                self.ser.write(
                    bytes([self.STOP])
                )

                self.ser.flush()

        except Exception:
            pass

        if self.worker is not None:

            self.worker.join(
                timeout=2
            )

            self.worker = None

    # =========================================================
    # CLOSE
    # =========================================================

    def close(self):

        self.stop()

        if self.ser is not None:

            self.ser.close()
            self.ser = None

    # =========================================================
    # ERROR
    # =========================================================

    def get_error(self):

        return self.error
