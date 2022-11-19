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

# uart=UART(0, tx=Pin(16), rx=Pin(17), baudrate=9600, timeout=100, timeout_char=100, parity=1, stop=2)
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
servos = [Servo(i) for i in range(START_PIN, END_PIN + 1)]
NUM_SERVOS = len(servos)
servoRanges = [
	[servos[i].min_value(), servos[i].max_value()] for i in range(NUM_SERVOS)
]
# cal = Calibration()
# cal.apply_two_pairs(1000, 2000, -180, 180)
# servos[0].frequency(300)
# servos[0].calibration(cal)

if len(servoRanges) != NUM_SERVOS:
	panic(led_bar)

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
	for s in servos:
		s.enable()
	time.sleep(2)
	for s in servos:
		s.to_mid()
	time.sleep(2)

if calibrationMode and motorsEnabled:
	val = servos[0].mid_value()
	prevVal = val
	step_small = (servos[0].max_value() - servos[0].min_value()) / CALIBRATION_STEP_SMALL
	step_large = (servos[0].max_value() - servos[0].min_value()) / CALIBRATION_STEP_LARGE
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

		if val > servos[0].max_value():
			val = servos[0].max_value()
		if val < servos[0].min_value():
			val = servos[0].min_value()
		
		if val != prevVal:
			servos[0].value(val)
			print(servos[0].pulse())
			prevVal = val
			time.sleep(CALIBRATION_STEP_DELAY)

# Indicate that we've reached main loop
set_led_colour(led_bar, STARTUP_INDICATOR_LED, 200, 0, 255)

while not user_sw.raw():
	position = read_servo_position(uart, led_bar)
	if position is None:
		continue
	print([hex(i) for i in position])
	if position[0] > NUM_SERVOS - 1:
		continue
	if motorsEnabled:
		servo = servos[position[0]]
		servo_min = servo.min_value()
		servo_max = servo.max_value()
		val = mapFromTo(position[1], 0, 255, 1000, 2000)
		servos[position[0]].pulse(val)

for s in servos:
	s.disable()
for i in range(servo2040.NUM_LEDS):
	set_led_colour(led_bar, i, 255, 0, 0)
