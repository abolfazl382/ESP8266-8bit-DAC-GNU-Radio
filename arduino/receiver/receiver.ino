#include <Arduino.h>
#include "DAC8Bit.h"


#define SAMPLE_RATE 100000UL

bool is_data = false;
bool is_buffer_full = false;
int byte_count = 0;

// =================================================
// Timer1 ISR
// =================================================

void IRAM_ATTR onTimer()
{
  if(is_buffer_full){
    if(is_data){
      dac.writeDAC(Serial.read());
      byte_count++;
      if(byte_count == 1023){
        Serial.write(0xAA);
        is_data = false;
        byte_count = 0;
      }
    }else{
      byte header = Serial.read();
      if(header == 0xAA){
        is_data = true;
        dac.writeDAC(Serial.read());
        byte_count++;
      }else if(header == 0xBB){
        dac.writeDAC(0);
        Serial.write(0xBB);
        is_buffer_full = false;
      }
    }
  }
}


// =================================================
// SETUP
// =================================================

void setup()
{
    Serial.setRxBufferSize(4096);
    Serial.begin(2000000);

    dac.begin();

    // =============================================
    // Timer1
    // =============================================

    uint32_t timerTicks = 80000000UL / SAMPLE_RATE;

    timer1_disable();
    timer1_detachInterrupt();

    timer1_isr_init();

    timer1_attachInterrupt(onTimer);

    timer1_enable(
        TIM_DIV1,
        TIM_EDGE,
        TIM_LOOP
    );

    timer1_write(timerTicks);
}

// =================================================
// LOOP
// =================================================

void loop()
{
    if (Serial.available() >= 2048 && !is_buffer_full)
    {
        is_buffer_full = true;
    }
}