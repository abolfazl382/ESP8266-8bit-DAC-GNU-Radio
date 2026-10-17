import numpy as np
from gnuradio import gr
import sys

sys.path.insert(0, r"your driver path")

from wemos_dac import WemosDAC


class blk(gr.sync_block):

    def __init__(
        self,
        port="COM5",
        baudrate=2000000,
        sample_rate=100000,
        buffer_packets=20,
        ack_timeout=2.0
    ):
        gr.sync_block.__init__(
            self,
            name="Wemos DAC Sink",
            in_sig=[np.float32],
            out_sig=None
        )

        self.port = port
        self.baudrate = int(baudrate)
        self.sample_rate = int(sample_rate)
        self.buffer_packets = int(buffer_packets)
        self.ack_timeout = float(ack_timeout)

        self.dac = None
        self.work_count = 0

    def start(self):

        print("Wemos DAC: starting...", flush=True)

        self.dac = WemosDAC(
            port=self.port,
            baudrate=self.baudrate,
            sample_rate=self.sample_rate,
            buffer_packets=self.buffer_packets,
            ack_timeout=self.ack_timeout
        )

        self.dac.start()

        print("Wemos DAC: started.", flush=True)

        return gr.sync_block.start(self)

    def work(self, input_items, output_items):

        samples = input_items[0]

        self.dac.write(samples)

        self.work_count += 1

        if self.work_count % 100 == 0:
            print(
                "Wemos DAC: received samples:",
                self.work_count,
                flush=True
            )

        return len(samples)

    def stop(self):

        print("Wemos DAC: stopping...", flush=True)

        if self.dac is not None:

            try:
                self.dac.finish()
            except Exception as e:
                print("Wemos DAC finish error:", e)

            self.dac.close()
            self.dac = None

        print("Wemos DAC: stopped.", flush=True)

        return gr.sync_block.stop(self)