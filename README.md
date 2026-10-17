# 8-Bit R-2R DAC Streaming with WeMos D1 R1 (ESP8266)

A low-cost, host-controlled 8-bit DAC built from a WeMos D1 R1 ESP8266
development board and a discrete R-2R resistor ladder. A Python driver
streams samples over UART, and a GNU Radio sink block can forward
real-valued samples to the driver.

> **Sample-rate note:** the validated target is **100 kS/s (100,000
> samples/second)**. UART is configured for 2,000,000
> baud. The sample rate is set in the receiver firmware and must match
> the host application.

## Features

-   8-bit parallel R-2R DAC output.
-   Fast GPIO writes using a precomputed lookup table.
-   Timer1-based sample scheduling on the ESP8266.
-   UART streaming from a PC at 2 Mbps.
-   ACK-driven packet transmission.
-   Reusable Python driver independent of WAV and GNU Radio.
-   GNU Radio integration through a real `float32` sink input.
-   Finite-stream completion using a padded final packet and STOP
    handshake.

## System architecture

``` text
Signal source (Python / WAV / GNU Radio)
                 |
                 | float32 samples in [-1, +1]
                 v
          Python WemosDAC driver
          - converts float to uint8
          - buffers and packetizes samples
          - handles ACKs and STOP
                 |
                 | UART, 2,000,000 baud
                 v
          WeMos D1 R1 / ESP8266
          - packet parser and RX buffer
          - Timer1 sample scheduling
          - DAC GPIO output and ACKs
                 |
                 v
          R-2R ladder -> LM741 buffer
                      -> coupling capacitor -> speaker/load
```

The Python driver owns the serial protocol. Applications and GNU Radio
should provide samples; they should not implement packet headers or ACK
handling.

## Hardware

-   **Board:** WeMos D1 R1 based on ESP8266.
-   **DAC:** discrete 8-bit R-2R ladder.
-   **Output stage:** LM741 op-amp used as a buffer in the tested
    circuit.
-   **Output coupling:** series capacitor between the amplifier output
    and speaker/load.
-   **Host connection:** USB-to-serial connection, shown as a COM port
    on Windows.

### Resistor values

The nominal ladder design uses:

-   `R = 1 kΩ`
-   `2R = 2 kΩ`

Resistor ratios matter for linearity. Use closely matched resistors. If
the final physical build uses different values, update this section with
the installed values and keep the ratio as close to 1:2 as possible.

### Op-amp/output stage

The tested circuit uses an **LM741 as a buffer**, followed by a series
coupling capacitor before the speaker/load. The ladder output represents
the current 8-bit sample.

The LM741 is not a rail-to-rail, 3.3 V op-amp. Do not assume it can
operate correctly from the ESP8266's 3.3 V supply alone. Verify the
actual supply rails, pinout, grounding, output swing, and capacitor
value against the physical circuit. The ESP8266 ground, ladder ground,
and amplifier signal reference must be compatible. Do not connect a
speaker directly to a GPIO.

> Record the exact LM741 supply rails and coupling-capacitor value from
> the final physical circuit/schematic; these values are not assumed
> here.

## R-2R ladder wiring

The following bit-to-pin mapping is fixed in the working `DAC8Bit`
library. The physical wiring must match it.

  DAC bit      Arduino pin   ESP8266 GPIO
  ---------- ------------- --------------
  D7 (MSB)              D2         GPIO16
  D6                    D3          GPIO5
  D5                    D4          GPIO4
  D4                    D5         GPIO14
  D3                    D6         GPIO12
  D2                    D7         GPIO13
  D1                    D8          GPIO0
  D0 (LSB)             D10         GPIO15

Connect each listed output to the corresponding ladder bit input. The
ladder analog output goes to the LM741 buffer input. Implement the
standard R-2R topology consistently, using the `R` and `2R` branches.

### Why these pins?

-   These are the eight GPIOs used by the tested DAC library and its
    lookup table.
-   GPIO16 is handled separately because it does not use the same GPIO
    register path as the other seven pins on the ESP8266.
-   The other seven outputs are updated using GPIO register writes and a
    precomputed lookup table, reducing software overhead compared with
    eight `digitalWrite()` calls per sample.
-   GPIO0 and GPIO15 are ESP8266 boot-strapping pins. Ensure the ladder
    does not force invalid logic levels during reset, and verify that
    the board boots reliably with the circuit attached.
-   The UART pins are reserved for serial communication and are not used
    as DAC outputs.

## repository structure

``` text
project/
├── README.md
├── arduino/
│   ├── libraries/
│   │   └── DAC8Bit/
│   │       ├── DAC8Bit.h
│   │       └── DAC8Bit.cpp
│   └── receiver/
│       └── receiver.ino
├── python/
│   ├── wemos_dac.py
│   ├── sine_generator.py
│   └── wav_test.py
└── gnuradio/
    ├── wemos_dac_sink_example.grc
    └── wemos_dac_sink.py
```


## 1. Install the Arduino DAC library

Copy the `DAC8Bit` folder into your Arduino sketchbook's `libraries`
directory. On Windows, a typical path is:

``` text
C:\Users\<YOUR_USER>\Documents\Arduino\libraries\DAC8Bit\
    DAC8Bit.h
    DAC8Bit.cpp
```

Include the library from the receiver sketch:

``` cpp
#include <DAC8Bit.h>
```

The library exposes:

``` cpp
dac.begin();
dac.writeDAC(value);  // uint8_t, range 0..255
```

Restart Arduino IDE if the library is not detected.

## 2. Flash the receiver firmware

1.  Install ESP8266 board support in Arduino IDE.
2.  Select the correct WeMos D1 R1 / ESP8266 board target.
3.  Select the correct serial port.
4.  Set CPU frequency to **160 MHz** for the validated configuration.
5.  Open the receiver sketch, confirm it includes `DAC8Bit.h`, and
    upload it.
6.  Close Arduino Serial Monitor before starting Python; two
    applications normally cannot own the same COM port.

Validated receiver settings:

``` cpp
#define SAMPLE_RATE 100000UL

Serial.setRxBufferSize(4096);
Serial.begin(2000000);

uint32_t timerTicks = 80000000UL / SAMPLE_RATE;
```

The timer expression is specific to the tested configuration. With CPU
frequency set to 160 MHz, the tested code still uses the `80000000UL`
constant. Do not replace it with `F_CPU` without retesting.

The receiver waits until at least 2048 serial bytes are available before
enabling playback. This is two packets of 1024 bytes each. Timer1 then
schedules DAC output at the configured sample rate.

**The host and firmware sample rates must match.** Changing
`SAMPLE_RATE` requires rebuilding and reflashing the receiver and
updating the host configuration.

## 3. Python driver

### Requirements

-   Python 3
-   NumPy
-   pySerial

Install dependencies:

``` bash
python -m pip install numpy pyserial
```

### Basic usage

The driver accepts real-valued floating-point samples in `[-1.0, +1.0]`.
It handles conversion, buffering, packetization, ACKs, and the stop
handshake.

``` python
import numpy as np
from wemos_dac import WemosDAC

dac = WemosDAC(
    port="COM5",
    baudrate=2_000_000,
    sample_rate=100_000,
    buffer_packets=20,
    ack_timeout=2.0,
)

dac.start()

try:
    sample_rate = 100_000
    frequency = 1_000
    duration = 2.0

    n = int(sample_rate * duration)
    t = np.arange(n, dtype=np.float32) / sample_rate
    samples = np.sin(2 * np.pi * frequency * t).astype(np.float32)

    dac.write(samples)
    dac.finish()

finally:
    dac.close()
```

Replace `COM5` with the port assigned by your operating system. Linux
devices may appear as `/dev/ttyUSB0` or `/dev/ttyACM0`, depending on the
board and USB-serial interface.

### Driver API

  -----------------------------------------------------------------------
  Method                              Purpose
  ----------------------------------- -----------------------------------
  `WemosDAC(...)`                     Configure serial port, baud rate,
                                      expected sample rate, queue
                                      capacity, and ACK timeout.

  `start()`                           Open serial and start the
                                      background streaming worker.

  `write(samples)`                    Submit a sequence/array of float
                                      samples in `[-1.0, +1.0]`.

  `finish()`                          End a finite stream, pad the final
                                      packet if needed, wait for
                                      acknowledgements, and perform STOP
                                      handshake.

  `stop()`                            Emergency stop; not the same as a
                                      clean end-of-stream.

  `close()`                           Stop if needed and close the serial
                                      port.

  `get_error()`                       Return a recorded background-worker
                                      error, if any.
  -----------------------------------------------------------------------

`write()` may block when the bounded queue is full. This applies
back-pressure rather than allowing unbounded memory growth. For a finite
stream, call `finish()` after the last `write()`.

### Driver parameters

  ------------------------------------------------------------------------
  Parameter                     Tested/default value Description
  --------------------- ---------------------------- ---------------------
  `port`                          `COM5` in examples Serial port for the
                                                     WeMos.

  `baudrate`                               `2000000` UART baud rate.

  `sample_rate`                             `100000` Must match firmware;
                                                     this does not
                                                     configure the board
                                                     itself.

  `buffer_packets`                              `20` Queue capacity
                                                     expressed in packets'
                                                     worth of samples.

  `ack_timeout`                        `2.0` seconds Serial read timeout
                                                     while waiting for an
                                                     ACK.
  ------------------------------------------------------------------------

The driver preserves the tested serial-open behavior: `dsrdtr=False`,
`rtscts=False`, `ser.dtr=False`, `ser.rts=False`, a three-second delay
after opening, and clearing the serial input buffer. These settings
avoid toggling DTR/RTS in the tested setup.

## 4. GNU Radio integration

GNU Radio should use a thin sink block: it receives `float32` samples
and forwards them to `WemosDAC.write()`. It should not implement packet
headers, ACKs, or serial timing.

### Tested environment

-   GNU Radio Companion 3.10.12.0
-   Windows installation under `C:\GNURadio\installation`
-   GNU Radio Python environment: Python 3.12.9 in the tested setup
-   Driver path used in the Embedded Python Block:
    `C:\pyprojects\arduino\wemos_dac.py`

Use the Python environment that runs GNU Radio. Installing pySerial into
another Python installation will not make it available to GNU Radio.

### Embedded Python Block configuration

Create an **Embedded Python Block** with:

-   **Block name:** `Wemos DAC Sink`
-   **Input:** one real `float` stream (`float32`)
-   **Outputs:** none (sink)
-   **Parameters:** `port`, `baudrate`, `sample_rate`, `buffer_packets`,
    `ack_timeout`

Example parameter values:

``` text
port = "COM5"
baudrate = 2000000
sample_rate = 100000
buffer_packets = 20
ack_timeout = 2.0
```

Add the driver directory to Python's module search path before importing
it:

``` python
import sys
sys.path.insert(0, r"C:\pyprojects\arduino")

from wemos_dac import WemosDAC
```

The block should create/start a `WemosDAC` instance when the flowgraph
starts, forward incoming samples to `driver.write(...)`, and call
`driver.finish()` for normal finite-flowgraph completion. On
interruption or error, use an appropriate cleanup path such as
`driver.stop()` followed by `driver.close()`. Lifecycle hooks vary with
the Embedded Python Block template generated by the installed GNU Radio
version.

### Connecting a flowgraph

1.  Add a signal source or other real-valued source.
2.  Ensure its effective sample rate matches the receiver firmware, or
    resample before the sink.
3.  Connect the real `float` output to `Wemos DAC Sink`.
4.  Set the serial port and driver parameters.
5.  Close Arduino Serial Monitor and any other application using the
    same port.
6.  Run the flowgraph.

The sink accepts **real samples**, not complex I/Q. For complex signals,
add a suitable complex-to-real or signal-processing stage. One DAC
output cannot independently reproduce I and Q simultaneously.

An Embedded Python Block inside a `.grc` flowgraph is not automatically
a separately installable block. Keep the Python driver available on the
Python path. For a reusable installed component, use GNU Radio's
hierarchical-block or out-of-tree (OOT) block workflow.

## Packet protocol

The host-to-board protocol is fixed and state-dependent.

### Packet layout

Each data packet is exactly **1024 bytes**:

     Offset       Length Meaning
  --------- ------------ ----------------------------
          0       1 byte Header: `0xAA`
    1--1023   1023 bytes Unsigned 8-bit DAC samples

The header is not a sample. Every byte after the header is sample data,
including data bytes equal to `0xAA` or `0xBB`.

### Startup and streaming sequence

1.  The driver opens the serial port.
2.  It waits until at least 2046 samples are queued.
3.  It sends **two complete packets back-to-back**.
4.  The receiver starts playback when at least 2048 serial bytes are
    available.
5.  After consuming 1023 samples, the receiver sends an ACK byte `0xAA`.
6.  Each subsequent ACK triggers exactly one new packet from the host.
7.  On `finish()`, the driver sends the remaining samples in a final
    packet, padding with `128` if needed.
8.  The driver waits for the final packet ACK, sends STOP `0xBB`, and
    waits for the receiver's `0xBB` response.

The receiver interprets `0xAA` as a header only while waiting for a
header. After accepting a header, it reads exactly 1023 following bytes
as sample data. This is essential because sample bytes may equal either
protocol byte.

### Protocol bytes

  -----------------------------------------------------------------------
  Byte                    Direction               Meaning
  ----------------------- ----------------------- -----------------------
  `0xAA`                  Host → board            Data packet header

  `0xAA`                  Board → host            ACK: 1023 samples
                                                  consumed

  `0xBB`                  Host → board            STOP request,
                                                  recognized while
                                                  waiting for a header

  `0xBB`                  Board → host            STOP acknowledgement
  -----------------------------------------------------------------------

Do not print debug text to the receiver's serial port while streaming.
Debug strings share the UART with binary packets and can corrupt
synchronization or be mistaken for ACK bytes.

### Buffering model

The receiver's serial RX buffer is configured for 4096 bytes. Playback
starts when at least 2048 bytes are available, providing two packets of
initial data. The Python driver maintains a bounded sample queue and
sends one packet per ACK after startup.

The two-packet startup prefill does not guarantee immunity to every host
scheduling delay. Windows, USB serial drivers, Python scheduling, and
GNU Radio may deliver data in bursts. Average UART throughput must
exceed sample consumption, but bursts can still cause gaps if the
receiver runs out of buffered samples.

## Sample format and amplitude mapping

The driver accepts `float32` values in `[-1.0, +1.0]`, clips
out-of-range values, and converts them to unsigned 8-bit samples.

    Input float                    DAC code
  ------------- ---------------------------
         `-1.0`                         `0`
          `0.0`   approximately `127`/`128`
         `+1.0`                       `255`

This is offset-binary, not signed 8-bit PCM. Zero amplitude corresponds
to the DAC midscale. Therefore, zero-padding a finite float stream
should use unsigned code `128` after conversion, not byte `0`.

The analog voltage depends on the ladder, GPIO high level, resistor
tolerances, loading, and buffer. The tested build measured approximately
2.65 V at full scale under its measurement conditions; this is not a
universal guaranteed output.

## Performance and limitations

-   **Validated sample rate:** 100 kS/s.
-   **Validated serial baud rate:** 2,000,000 baud.
-   **Validated test:** a 1 kHz sine streamed through the Python driver;
    a finite two-second, 200,000-sample test completed the final
    ACK/STOP handshake.
-   **Output:** one real-valued 8-bit channel.
-   This is **not a 100 MS/s DAC**. The current implementation is 100
    kS/s, 1,000 times slower than 100 MS/s.
-   Quantization distortion and small artifacts may occur due to GPIO
    timing, UART buffering, host scheduling, resistor mismatch, and
    analog-stage limitations.
-   The output is not automatically anti-aliased. Select sample rate and
    reconstruction/low-pass filtering for the intended signal.
-   This is an educational/prototyping design, not a calibrated
    laboratory DAC or a high-speed RF DAC.

## Troubleshooting

### The board does not boot with the ladder attached

Check ESP8266 boot-strapping pins, especially GPIO0 and GPIO15. Ensure
the external ladder does not force invalid levels during reset.

### Python says the COM port is busy

Close Arduino Serial Monitor, Serial Plotter, terminals, and any other
application using the port.

### The driver reports an ACK timeout

Check that receiver firmware is running, baud rates match, the sample
rate is consistent, and the receiver is not printing debug text. Ensure
the application supplies samples fast enough.

### GNU Radio cannot import `wemos_dac`

Check `sys.path` and install NumPy and pySerial in the Python
environment used by GNU Radio.

### The signal is distorted or has gaps

Check the flowgraph's effective sample rate, possible underruns, ladder
resistor ratios, grounding, LM741 supply, and output filtering.
Increasing UART baud rate alone does not guarantee uninterrupted
playback.

## Safety and electrical notes

-   ESP8266 GPIOs are **3.3 V logic** and are not 5 V tolerant.
-   Do not drive a speaker directly from GPIOs.
-   Verify the LM741 supply and pinout before powering the circuit.
-   Connect signal grounds appropriately and avoid allowing speaker
    currents to disturb the DAC reference.
-   Disconnect power before changing ladder wiring.
-   Confirm the actual resistor values, amplifier supply rails, and
    coupling capacitor against the physical circuit before reproducing
    it.

