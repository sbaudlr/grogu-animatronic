import sys
import time
from pimoroni import Analog, AnalogMux, Button
from plasma import WS2812
from servo import Servo, servo2040, Calibration

from machine import Pin, UART

"""
Control software for a Grogu animatronic based around the Pimoroni Servo 2040 board.
"""

POWER_INDICATOR_LED = 0
STARTUP_INDICATOR_LED = 1
BUST_STATE_INDICATOR_LED = 2
LED_BRIGHTNESS = 0.3
CALIBRATION_SELECT_PIN = servo2040.SENSOR_1_ADDR
MOTOR_DISABLE_SELECT_PIN = servo2040.SENSOR_6_ADDR

CALIBRATION_PLUS_PIN_SMALL = servo2040.SENSOR_2_ADDR
CALIBRATION_MINUS_PIN_SMALL = servo2040.SENSOR_3_ADDR
CALIBRATION_PLUS_PIN_LARGE = servo2040.SENSOR_4_ADDR
CALIBRATION_MINUS_PIN_LARGE = servo2040.SENSOR_5_ADDR
CALIBRATION_STEP_SMALL = 100
CALIBRATION_STEP_LARGE = 20
CALIBRATION_STEP_DELAY = 0.1

MAGIC_HEADER = [0x04, 0x0c, 0x08, 0x0e]
COMMAND_SERVO_POSITION = [0x05, 0x08]
PACKET_SIZE = 16

SERVO_MOUTH = 0
SERVO_EYE_BL = 2
SERVO_EYE_BR = 3
SERVO_EYE_TL = 4
SERVO_EYE_TR = 5
SERVO_EAR_BL = 6
SERVO_EAR_BR = 7
SERVO_EAR_TL = 8
SERVO_EAR_TR = 9

def mapFromTo(val,originalMin,originalMax,newMin,newMax):
   y=(val-originalMin)/(originalMax-originalMin)*(newMax-newMin)+newMin
   return y

def set_led_colour(leds, led: int, r: int, g: int, b: int):
	leds.set_rgb(led, (int)(r * LED_BRIGHTNESS), (int)(g * LED_BRIGHTNESS), (int)(b * LED_BRIGHTNESS))

def read_servo_position(bus, leds):
	set_led_colour(leds, BUST_STATE_INDICATOR_LED, 0, 0, 255)
	try:
		data = bus.readline()
		if data == None:
			return None
		if len(data) != PACKET_SIZE:
			# print("Size is wrong ", len(data))
			return None
		# print([hex(i) for i in data])
		# Must start with all 1s
		if data[0] != 0xff:
			# print("First bit is wrong")
			return None
		# Must end with newline
		if data[PACKET_SIZE - 1] != 0x0a:
			# print("Last bit is wrong")
			return None
		# Check header
		for i in range(len(MAGIC_HEADER)):
			if data[1 + i] != MAGIC_HEADER[i]:
				# print("Header is wrong")
				return None
		# Check command
		for i in range(len(COMMAND_SERVO_POSITION)):
			if data[1 + len(MAGIC_HEADER) + i] != COMMAND_SERVO_POSITION[i]:
				# print("Command is wrong")
				return None
		# Return data bits
		# print("Good data")
		return data[-3:-1]
	except Exception as e:
		set_led_colour(leds, BUST_STATE_INDICATOR_LED, 255, 0, 0)
		print("[", time.time(), "] Error reading from uart ", e)
		time.sleep(2)
		return None

def panic(leds):
	while not user_sw.raw():
		for i in range(0, servo2040.NUM_LEDS):
			set_led_colour(leds, i, 255, 0, 0)
			time.sleep(0.1)
		time.sleep(1)
		for i in range(0, servo2040.NUM_LEDS):
			set_led_colour(leds, i, 0, 0, 0)
			time.sleep(0.1)
		time.sleep(1)
	sys.exit(1)

# Create the LED bar, using PIO 1 and State Machine 0
led_bar = WS2812(servo2040.NUM_LEDS, 1, 0, servo2040.LED_DATA)
# Create the user button
user_sw = Button(servo2040.USER_SW)
# Start updating the LED bar
led_bar.start()

# Indicate that power is on
set_led_colour(led_bar, POWER_INDICATOR_LED, 0, 255, 0)

uart=UART(0, tx=Pin(16), rx=Pin(17), rxbuf=10*PACKET_SIZE, txbuf=10*PACKET_SIZE, bits=8, baudrate=9600, timeout=100, timeout_char=100, parity=None, stop=1)

# Configure analog mux
sen_adc = Analog(servo2040.SHARED_ADC)
mux = AnalogMux(servo2040.ADC_ADDR_0, servo2040.ADC_ADDR_1, servo2040.ADC_ADDR_2,
                muxed_pin=Pin(servo2040.SHARED_ADC))
sensor_addrs = list(range(servo2040.SENSOR_1_ADDR, servo2040.SENSOR_6_ADDR + 1))
for addr in sensor_addrs:
    mux.configure_pull(addr, Pin.PULL_DOWN)

sen_calibration_pot = Analog(servo2040.ADC0)

# Create a list of servos for pins 1 to 12 (inclusive).
START_PIN = servo2040.SERVO_1
END_PIN = servo2040.SERVO_12
SERVOS = [Servo(i) for i in range(START_PIN, END_PIN + 1)]
NUM_SERVOS = len(SERVOS)
CALIBRATION = [
	[500, 2500] for _ in range(NUM_SERVOS)
]

CALIBRATION[SERVO_MOUTH] = [1380, 1480]
CALIBRATION[SERVO_EYE_BL] = [1280, 1720]
CALIBRATION[SERVO_EYE_BR] = [1400, 1760]
CALIBRATION[SERVO_EYE_TL] = [1200, 1720]
CALIBRATION[SERVO_EYE_TR] = [1440, 1760]
CALIBRATION[SERVO_EAR_TL] = [1300, 2140]
CALIBRATION[SERVO_EAR_TR] = [940, 1820]
CALIBRATION[SERVO_EAR_BL] = [1280, 1660]
CALIBRATION[SERVO_EAR_BR] = [1240, 1620]

if len(CALIBRATION) != NUM_SERVOS:
	panic(led_bar)

for i in range(len(CALIBRATION)):
	cal = Calibration()
	cal.apply_two_pairs(CALIBRATION[i][0], CALIBRATION[i][1], -90, 90)
	SERVOS[i].calibration(cal)

# Mouth
SERVOS[SERVO_MOUTH].frequency(300)

print("Hello")

calibrationMode = False
motorsEnabled = True

mux.select(MOTOR_DISABLE_SELECT_PIN)
if round(sen_adc.read_voltage(), 3) > 3:
	motorsEnabled = False

mux.select(CALIBRATION_SELECT_PIN)
if round(sen_adc.read_voltage(), 3) > 3:
	calibrationMode = True
	for i in range(1, servo2040.NUM_LEDS):
		set_led_colour(led_bar, i, 0, 0, 200)

if motorsEnabled:
	# Home all servos
	for s in SERVOS:
		s.enable()
		time.sleep(0.1)
	time.sleep(2)
	for s in SERVOS:
		s.to_mid()
		time.sleep(0.1)
	time.sleep(2)

if calibrationMode and motorsEnabled:
	val = SERVOS[0].mid_value()
	prevVal = val
	step_small = (SERVOS[0].max_value() - SERVOS[0].min_value()) / CALIBRATION_STEP_SMALL
	step_large = (SERVOS[0].max_value() - SERVOS[0].min_value()) / CALIBRATION_STEP_LARGE
	while not user_sw.raw():
		mux.select(CALIBRATION_PLUS_PIN_SMALL)
		cal_plus_small = round(sen_adc.read_voltage(), 3) > 3
		mux.select(CALIBRATION_MINUS_PIN_SMALL)
		cal_minus_small = round(sen_adc.read_voltage(), 3) > 3
		mux.select(CALIBRATION_PLUS_PIN_LARGE)
		cal_plus_large = round(sen_adc.read_voltage(), 3) > 3
		mux.select(CALIBRATION_MINUS_PIN_LARGE)
		cal_minus_large = round(sen_adc.read_voltage(), 3) > 3

		if cal_plus_small == True:
			val += step_small
		if cal_minus_small == True:
			val -= step_small
		if cal_plus_large == True:
			val += step_large
		if cal_minus_large == True:
			val -= step_large

		if val > SERVOS[0].max_value():
			val = SERVOS[0].max_value()
		if val < SERVOS[0].min_value():
			val = SERVOS[0].min_value()
		
		if val != prevVal:
			SERVOS[0].value(val)
			print(SERVOS[0].pulse())
			prevVal = val
			time.sleep(CALIBRATION_STEP_DELAY)

# Indicate that we've reached main loop
set_led_colour(led_bar, STARTUP_INDICATOR_LED, 200, 0, 255)

while not user_sw.raw():
	position = read_servo_position(uart, led_bar)
	if position is None:
		continue
	print([hex(i) for i in position])
	index = position[0]
	if index >= NUM_SERVOS:
		continue
	if motorsEnabled:
		servo_min = CALIBRATION[index][0]
		servo_max = CALIBRATION[index][1]
		val = mapFromTo(position[1], 0x00, 0xff, servo_min, servo_max)
		if val < servo_min:
			val = servo_min
		if val > servo_max:
			val = servo_max
		if val <= 0:
			continue
		SERVOS[index].pulse(val)

for s in SERVOS:
	s.disable()
for i in range(servo2040.NUM_LEDS):
	set_led_colour(led_bar, i, 255, 0, 0)
