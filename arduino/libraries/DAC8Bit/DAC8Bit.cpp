#include "DAC8Bit.h"
#include "eagle_soc.h"

// ========================================
// DAC GPIO mapping
// ========================================

// Bit 7 -> D2  -> GPIO16
// Bit 6 -> D3  -> GPIO5
// Bit 5 -> D4  -> GPIO4
// Bit 4 -> D5  -> GPIO14
// Bit 3 -> D6  -> GPIO12
// Bit 2 -> D7  -> GPIO13
// Bit 1 -> D8  -> GPIO0
// Bit 0 -> D10 -> GPIO15

const uint8_t dacGPIO[8] = {
    16,
    5,
    4,
    14,
    12,
    13,
    0,
    15
};

uint32_t gpioLUT[256];
uint32_t dacMask;


// ========================================
// DAC initialization
// ========================================

void DAC8Bit::begin()
{
    // D2 / GPIO16
    pinMode(16, OUTPUT);


    for (int i = 1; i < 8; i++)
    {
        pinMode(dacGPIO[i], OUTPUT);
    }


    dacMask = 0;

    for (int i = 1; i < 8; i++)
    {
        dacMask |= (1UL << dacGPIO[i]);
    }


    for (int value = 0; value < 256; value++)
    {
        uint32_t gpioValue = 0;

        for (int bit = 1; bit < 8; bit++)
        {
            if (value & (1 << (7 - bit)))
            {
                gpioValue |=
                    (1UL << dacGPIO[bit]);
            }
        }

        gpioLUT[value] = gpioValue;
    }


    GP16O &= ~(1 << 0);

    GPIO_REG_WRITE(
        GPIO_OUT_ADDRESS,
        GPIO_REG_READ(GPIO_OUT_ADDRESS) & ~dacMask
    );
}


// ========================================
// Write 8-bit value to DAC
// ========================================

void DAC8Bit::writeDAC(uint8_t value)
{
    // -------------------------------
    // GPIO16 = Bit 7
    // -------------------------------

    if (value & 0x80)
    {
        GP16O |= 1;
    }
    else
    {
        GP16O &= ~1;
    }


    uint32_t currentGPIO =
        GPIO_REG_READ(GPIO_OUT_ADDRESS);

    uint32_t newGPIO =
        (currentGPIO & ~dacMask) |
        gpioLUT[value];

    GPIO_REG_WRITE(
        GPIO_OUT_ADDRESS,
        newGPIO
    );
}


DAC8Bit dac;