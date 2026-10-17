#ifndef DAC8BIT_H
#define DAC8BIT_H

#include <Arduino.h>

class DAC8Bit
{
public:

    void begin();

    void writeDAC(uint8_t value);
};

extern DAC8Bit dac;

#endif