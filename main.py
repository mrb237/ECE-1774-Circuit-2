# ECE 1896 Tabletop Grid Demonstrator - Team 20
# Solver Classes
from Breaker import Breaker
from bus import Bus
from circuit import Circuit
from generator import Generator
from jacobian import Jacobian
from load import Load
from power_flow import PowerFlow
from settings import SETTINGS
from settings import Settings
from transformer import Transformer
from transmission_line import TransmissionLine

# LED Classes
import time
import signal
import sys
from gpiozero import OutputDevice, Button
from gpiozero import Device
from gpiozero.pins.rpigpio import RPiGPIOFactory
from rpi_ws281x import PixelStrip, Color

# Imported Libraries
import numpy as np
import pandas as pd

# Force gpiozero to use RPi.GPIO backend to avoid PWM conflict on GPIO 18
Device.pin_factory = RPiGPIOFactory()

# ---------- GPIO CONFIG ----------
SIGNAL_PINS  = [4, 17, 27, 22, 23, 24, 25]

# NeoPixel (addressable LED) config on GPIO 18
LED_COUNT    = 54 # CHANGE TO 174 (3 strands)
LED_PIN      = 18
LED_FREQ_HZ  = 800_000
LED_DMA      = 10
LED_INVERT   = False
LED_CHANNEL  = 0
LED_BRIGHTNESS = 128       # 0-255

# ---------- PUT LED CODE HERE ----------


# ---------- Build Default 5-Bus System ----------
Bus.index_counter = 0
c = Circuit("5-Bus Solver Test Circuit")

# Buses
c.add_bus("Bus1", 15.0, "Slack")
c.add_bus("Bus2", 345.0, "PQ")
c.add_bus("Bus3", 15.0, "PV")
c.add_bus("Bus4", 345.0, "PQ")
c.add_bus("Bus5", 345.0, "PQ")

# Transformers
c.add_transformer("T1", "Bus1", "Bus5", 0.0015, 0.02, 9999.0)
c.add_transformer("T2", "Bus3", "Bus4", 0.00075, 0.01, 9999.0)

# Transmission lines
c.add_transmission_line("TL1", "Bus5", "Bus4", 0.00225, 0.025, 0.0, 0.44, 9999.0)
c.add_transmission_line("TL2", "Bus5", "Bus2", 0.0045, 0.05, 0.0, 0.88, 9999.0)
c.add_transmission_line("TL3", "Bus4", "Bus2", 0.009, 0.1, 0.0, 1.72, 9999.0)

# Generators
c.add_generator("G1", "Bus1", 1.00, 0.0)
c.add_generator("G2", "Bus3", 1.05, 520.0)

# Loads
c.add_load("L1", "Bus3", 80.0, 40.0)
c.add_load("L2", "Bus2", 800.0, 280.0)

# Breakers
c.add_breaker("BR_G1", "G1", "Bus1", True)
c.add_breaker("BR_G2", "G2", "Bus3", True)

c.add_breaker("BR_T1", "Bus1", "Bus5", True)
c.add_breaker("BR_T2", "Bus3", "Bus4", True)

c.add_breaker("BR_TL1", "Bus5", "Bus4", True)
c.add_breaker("BR_TL2", "Bus5", "Bus2", True)
c.add_breaker("BR_TL3", "Bus4", "Bus2", True)

c.add_breaker("BR_L1", "L1", "Bus3", True)
c.add_breaker("BR_L2", "L2", "Bus2", True)