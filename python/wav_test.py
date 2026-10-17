import wave
import numpy as np

from wemos_dac import WemosDAC


# =========================================================
# SETTINGS
# =========================================================

PORT = "COM5"
BAUDRATE = 2_000_000

DAC_SAMPLE_RATE = 100_000

WAV_FILE = "audio.wav"


# =========================================================
# READ WAV
# =========================================================

def read_wav(filename):

    with wave.open(filename, "rb") as wav:

        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        num_frames = wav.getnframes()

        raw = wav.readframes(num_frames)


    print()
    print("--------------------------------")
    print("WAV FILE")
    print("--------------------------------")
    print("Sample rate :", sample_rate, "Hz")
    print("Channels    :", channels)
    print("Sample width:", sample_width * 8, "bit")
    print("Samples     :", num_frames)
    print("--------------------------------")


    # -----------------------------------------------------
    # Convert WAV samples to float32 [-1, +1]
    # -----------------------------------------------------

    if sample_width == 1:

        # 8-bit WAV is normally unsigned
        data = np.frombuffer(
            raw,
            dtype=np.uint8
        ).astype(np.float32)

        data = (data - 128.0) / 128.0


    elif sample_width == 2:

        data = np.frombuffer(
            raw,
            dtype=np.int16
        ).astype(np.float32)

        data /= 32768.0


    elif sample_width == 3:

        # 24-bit PCM
        bytes_data = np.frombuffer(
            raw,
            dtype=np.uint8
        ).reshape(-1, 3)

        data = (
            bytes_data[:, 0].astype(np.int32)
            |
            (bytes_data[:, 1].astype(np.int32) << 8)
            |
            (bytes_data[:, 2].astype(np.int32) << 16)
        )

        # Sign extension
        negative = (data & 0x800000) != 0
        data[negative] -= 0x1000000

        data = data.astype(np.float32)
        data /= 8388608.0


    elif sample_width == 4:

        data = np.frombuffer(
            raw,
            dtype=np.int32
        ).astype(np.float32)

        data /= 2147483648.0


    else:

        raise ValueError(
            f"Unsupported WAV sample width: "
            f"{sample_width * 8} bit"
        )


    # -----------------------------------------------------
    # Convert stereo/multi-channel to mono
    # -----------------------------------------------------

    if channels > 1:

        data = data.reshape(
            -1,
            channels
        )

        data = np.mean(
            data,
            axis=1
        )


    # Safety clipping
    data = np.clip(
        data,
        -1.0,
        1.0
    )

    return data, sample_rate


# =========================================================
# RESAMPLE
# =========================================================

def resample_linear(samples, input_rate, output_rate):

    if input_rate == output_rate:
        return samples.astype(np.float32)


    duration = len(samples) / input_rate

    output_length = int(
        round(duration * output_rate)
    )


    input_positions = np.arange(
        len(samples),
        dtype=np.float64
    )

    output_positions = (
        np.arange(
            output_length,
            dtype=np.float64
        )
        * input_rate
        / output_rate
    )


    output = np.interp(
        output_positions,
        input_positions,
        samples
    )


    return output.astype(np.float32)


# =========================================================
# MAIN
# =========================================================

print()
print("Loading WAV file...")

samples, wav_sample_rate = read_wav(
    WAV_FILE
)


# =========================================================
# RESAMPLE TO DAC RATE
# =========================================================

if wav_sample_rate != DAC_SAMPLE_RATE:

    print()
    print(
        f"Resampling: "
        f"{wav_sample_rate} Hz -> "
        f"{DAC_SAMPLE_RATE} Hz"
    )

    samples = resample_linear(
        samples,
        wav_sample_rate,
        DAC_SAMPLE_RATE
    )

else:

    print()
    print("No resampling required.")


# =========================================================
# INFORMATION
# =========================================================

duration = (
    len(samples) / DAC_SAMPLE_RATE
)

print()
print("--------------------------------")
print("DAC STREAM")
print("--------------------------------")
print("DAC sample rate :", DAC_SAMPLE_RATE, "Hz")
print("Samples         :", len(samples))
print("Duration        :", f"{duration:.3f}", "sec")
print("UART            :", BAUDRATE)
print("--------------------------------")


# =========================================================
# CREATE DRIVER
# =========================================================

dac = WemosDAC(
    port=PORT,
    baudrate=BAUDRATE,
    sample_rate=DAC_SAMPLE_RATE,
    buffer_packets=20
)


# =========================================================
# START STREAM
# =========================================================

print()
print("Starting Wemos DAC...")

dac.start()

try:

    print("Sending WAV samples...")

    dac.write(samples)

    print("All samples sent to driver.")

    print("Finishing...")

    dac.finish()

    print("Stream finished successfully.")


except KeyboardInterrupt:

    print()
    print("Stopped by user.")


except Exception as e:

    print()
    print("ERROR:", e)


finally:

    dac.close()

    print("Driver closed.")

