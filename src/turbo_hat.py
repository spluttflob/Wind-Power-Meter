#!/usr/bin/python3
"""!
@file turbo_hat.py
    This file contains a driver for the Wind Turbine Power Measurement
    Sort-of-Pi-HAT which measures wind turbine power using a TI
    ADS112C04 ADC, some isolated current sensors, and voltage dividers.
@author    JR Ridgely
@date      2021-Jun-07 JRR Original file
@date      2022-Jan-08 JRR Updates to documentation for repository
@copyright Copyright (c) 2021-2022 by JR Ridgely and released under the
           Lesser GNU Public License, Version 3.
"""

import time
import RPi.GPIO as gpio
from smbus import SMBus      # This is I2C...?


class TurboHAT:
    """!
    This class drives a turbine power sensor on a Raspberry Pi Hat.
    The sensor uses a TI ADS112C04 A/D converter on I2C bus 1.
    """
    ## Reset the ADC
    CMD_RESET = 0x06
    ## Start or restart conversion
    CMD_START_SYNC = 0x08
    ## Power down the ADC
    CMD_PWR_DOWN = 0x02
    ## Load ADC output with data
    CMD_RDATA = 0x10
    ## Read a register; address in bits 3,2
    CMD_RREG = 0x20
    ## Write register; address in bits 3,2
    CMD_WREG = 0x40

    ## Configuration register 0
    REG_CFG_0 = 0x00
    ## Configuration register 1
    REG_CFG_1 = 0x01
    ## Configuration register 2
    REG_CFG_2 = 0x02
    ## Configuration register 3
    REG_CFG_3 = 0x03

    ## Internal 2.048 volt reference
    VREF_INT_2048 = 0x00
    ## External reference on REFP, REFN pins
    VREF_EXT = 0x02          
    ## Analog supply AVDD - AVSS used as reference
    VREF_SUP = 0x04          

    # Data rates for normal (not turbo) mode; in turbo, rates are doubled
    ## Data rate 20 Hz     
    DR_20HZ = 0x00           
    ## Data rate 45 Hz
    DR_45HZ = 0x20           
    ## Data rate 90 Hz
    DR_90HZ = 0x40           
    ## Data rate 175 Hz
    DR_175HZ = 0x60          
    ## Data rate 330 Hz
    DR_330HZ = 0x80          
    ## Data rate 600 Hz
    DR_600HZ = 0xA0          
    ## Data rate 1000 Hz
    DR_1000HZ = 0xC0         


    def __init__ (self, i2c_bus, i2c_address=0x40, reset_pin=12, drdy_pin=16,
                  ref_voltage=VREF_SUP, data_rate=DR_20HZ):
        """! Set up the GPIO ports to talk to the ADC and save the ADC's
        address on the I2C bus.
        @param i2c_bus The I2C bus used, created by "SMBus(1)" or similar
        @param i2c_address The ADC's address on the I2C bus
        @param reset_pin The GPIO pin connected to the ADC's RESET' line
        @param drdy_pin The GPIO pin connected to the ADC's DRDY' line
        @param ref_voltage The reference voltage source, chosen from the set
               of @c VREF_... constants given in this class
        @param data_rate The data rate in Hz for conversions, chosen from the
               set of @c DR_... constants given in this class
        """
        self._i2c_bus = i2c_bus
        self._address = i2c_address
        self._reset_pin = reset_pin
        self._drdy_pin = drdy_pin
        self._ref_voltage = ref_voltage
        self._data_rate = data_rate

        # Set pin numbering mode to use Broadcom pins (more commonly used)
        # Turbine measurement ADC pins: RESET' on GPIO12, DRDY' on GPIO16
        gpio.setwarnings (False)
        gpio.setmode (gpio.BCM)
        gpio.setup (self._reset_pin, gpio.OUT)
        gpio.setup (self._drdy_pin, gpio.IN, pull_up_down=gpio.PUD_UP)

        # Set the RESET' pin high so the ADC will operate
        gpio.output (self._reset_pin, gpio.HIGH)

        # Set the reference voltage and data rate in config. register 1
        self._i2c_bus.write_byte_data (self._address,
                        TurboHAT.CMD_WREG | (TurboHAT.REG_CFG_1 << 2),
                        self._ref_voltage | self._data_rate)


    def clean_up (self):
        """!
        Set the GPIO pins back to normal (input) mode and close the I2C bus.
        """
        gpio.cleanup ()
        self._i2c_bus.close ()


    def show_ADC_registers (self):
        """! Display the contents of the registers in the ADC. The read
        register command has bits 0010rrxx, where rr hold the address
        and xx don't seem to matter
        """
        for reggie in range (4):
            data = self._i2c_bus.read_byte_data (self._address,
                       TurboHAT.CMD_RDATA | (reggie << 2))
            print ("Reg {:d}: 0b{:08b}".format (reggie, data), end=' ')
        print ("")


    def read_channel (self, chan):
        """! Read one ADC channel. The value returned is a signed 16 bit
        number with the maximum corresponding to a voltage equal to the
        reference. Ref: https://www.abelectronics.co.uk/kb/article/1094/
                   i2c-part-4---programming-i-c-with-python
        @param chan The channel to read
        """
        # Set the multiplexer to select the correct channel for
        # a single-ended measurement
        self._i2c_bus.write_byte_data (self._address,
                        TurboHAT.CMD_WREG | (TurboHAT.REG_CFG_0 << 2),
                        (0x08 | (chan & 0x03)) << 4)

        # Send a start/sync command to begin reading
        self._i2c_bus.write_byte (self._address,
                                 TurboHAT.CMD_START_SYNC)

#         # Check the DRDY bit in configuration register 2 to see if the
#         # conversion is complete
#         counter = 0
#         while True:
#             cr2 = self._i2c_bus.read_byte_data (self._address,
#                 TurboHAT.CMD_RREG | (TurboPower.REG_CFG_2 << 2))
#             if cr2 & 0x80:
#                 break
#             else:
# #                 if not counter:
# #                     print ("CR2:", cr2)  ####################
#                 counter += 1
#                 if counter > 1000:
#                     raise IOError ("Timeout waiting for ADS112C04")
#                     break

        # Wait for the DRDY' line to go low
        counter = 0
        while gpio.input (self._drdy_pin):
            time.sleep (0.01)
            counter += 1
            if counter > 100000:
                raise IOError ("Timeout waiting for ADS112C04")
                break

        # Read and return the data, with bytes swapped
        adc_data = self._i2c_bus.read_word_data (self._address,
                                                TurboHAT.CMD_RDATA)
        return ((adc_data & 0x00FF) << 8) | ((adc_data & 0xFF00) >> 8)


def main ():
    """! Test the ADC somehow or other. This function isn't run when 
    this driver is imported as a module.
    """
    print ("Testing Turbine Power Sensors")

    i2c_bus = SMBus (1)
    turbo = TurboHAT (i2c_bus, i2c_address=0x40, reset_pin=12, drdy_pin=16)
    turbo.show_ADC_registers ()
#     turbo.show_ADC_registers ()
    for count in range (20):
        ch0data = turbo.read_channel (0)
        print ("Ch 0:", ch0data)
        time.sleep (1.0)

    turbo.show_ADC_registers ()

    turbo.clean_up ()


if __name__ == "__main__":
    main ()

