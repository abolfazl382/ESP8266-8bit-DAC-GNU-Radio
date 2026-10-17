import numpy as np

from wemos_dac import WemosDAC


# =========================================================
# SETTINGS
# =========================================================

PORT = "COM5"
BAUDRATE = 2_000_000
SAMPLE_RATE = 100_000

frequency_khz = float(
    input("Enter sine frequency (kHz): ")
)

frequency = frequency_khz * 1000.0

print()
print("--------------------------------")
print("PACKETIZED SINE GENERATOR")
print("--------------------------------")
print("Sample rate :", SAMPLE_RATE, "Hz")
print("Frequency   :", frequency, "Hz")
print("Packet size :", WemosDAC.PACKET_SAMPLES, "samples")
print("UART        :", BAUDRATE)
print("--------------------------------")


# =========================================================
# CREATE DAC DRIVER
# =========================================================

dac = WemosDAC(
    port=PORT,
    baudrate=BAUDRATE,
    sample_rate=SAMPLE_RATE,
    buffer_packets=20
)


# =========================================================
# SINE GENERATOR
# =========================================================

phase = 0.0

phase_step = (
    2.0 * np.pi * frequency / SAMPLE_RATE
)


def make_samples(num_samples):
    global phase

    phases = (
        phase +
        phase_step * np.arange(
            num_samples,
            dtype=np.float32
        )
    )

    samples = np.sin(phases).astype(np.float32)

    phase += phase_step * num_samples
    phase %= 2.0 * np.pi

    return samples


# =========================================================
# START
# =========================================================

print()
print("Starting Wemos DAC...")

dac.start()

try:

    # -----------------------------------------------------
    # First two packets
    #
    # The driver waits until it has enough samples
    # and automatically sends the first two packets.
    # -----------------------------------------------------

    print("Preparing first samples...")

    packet_samples = WemosDAC.PACKET_SAMPLES

    first_samples = make_samples(
        packet_samples * 2
    )

    print("Sending initial samples...")

    dac.write(first_samples)

    print()
    print("Initial samples sent to driver.")
    print("Streaming...")


    # -----------------------------------------------------
    # Continue generating samples
    #
    # The driver handles:
    #   - packet formation
    #   - ACK
    #   - serial transmission
    #   - buffering
    # -----------------------------------------------------

    while True:

        samples = make_samples(
            packet_samples
        )

        dac.write(samples)


except KeyboardInterrupt:

    print()
    print("Stopped by user.")


except Exception as e:

    print()
    print("ERROR:", e)


finally:

    print()
    print("Finishing stream...")

    try:
        dac.finish()
    except Exception as e:
        print("Finish error:", e)

    dac.close()

    print()
    print("--------------------------------")
    print("STREAM FINISHED")
    print("--------------------------------")

