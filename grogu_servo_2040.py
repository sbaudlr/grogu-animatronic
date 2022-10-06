import time
from machine import I2C
from pimoroni import Analog, AnalogMux, Button
from plasma import WS2812
from servo import Servo, servo2040

from machine import mem32,mem8,Pin

class i2c_peripheral:
	"""
	Taken from https://forums.raspberrypi.com/viewtopic.php?t=302978#p1823668
	"""

	I2C0_BASE = 0x40044000
	I2C1_BASE = 0x40048000
	IO_BANK0_BASE = 0x40014000
	
	mem_rw =  0x0000
	mem_xor = 0x1000
	mem_set = 0x2000
	mem_clr = 0x3000
	
	IC_CON = 0
	IC_TAR = 4
	IC_SAR = 8
	IC_DATA_CMD = 0x10
	IC_RAW_INTR_STAT = 0x34
	IC_RX_TL = 0x38
	IC_TX_TL = 0x3C
	IC_CLR_INTR = 0x40
	IC_CLR_RD_REQ = 0x50
	IC_CLR_TX_ABRT = 0x54
	IC_ENABLE = 0x6c
	IC_STATUS = 0x70
	
	def write_reg(self, reg, data, method=0):
		mem32[ self.i2c_base | method | reg] = data
		
	def set_reg(self, reg, data):
		self.write_reg(reg, data, method=self.mem_set)
		
	def clr_reg(self, reg, data):
		self.write_reg(reg, data, method=self.mem_clr)
				
	def __init__(self, i2cID = 0, sda=0,  scl=1, peripheralAddress=0x41):
		self.scl = scl
		self.sda = sda
		self.peripheralAddress = peripheralAddress
		self.i2c_ID = i2cID
		if self.i2c_ID == 0:
			self.i2c_base = self.I2C0_BASE
		else:
			self.i2c_base = self.I2C1_BASE
		
		# 1 Disable DW_apb_i2c
		self.clr_reg(self.IC_ENABLE, 1)
		# 2 set peripheral address
		# clr bit 0 to 9
		# set peripheral address
		self.clr_reg(self.IC_SAR, 0x1ff)
		self.set_reg(self.IC_SAR, self.peripheralAddress &0x1ff)
		# 3 write IC_CON  7 bit, enable in peripheral-only
		self.clr_reg(self.IC_CON, 0b01001001)
		# set SDA PIN
		mem32[ self.IO_BANK0_BASE | self.mem_clr |  ( 4 + 8 * self.sda) ] = 0x1f
		mem32[ self.IO_BANK0_BASE | self.mem_set |  ( 4 + 8 * self.sda) ] = 3
		# set SLA PIN
		mem32[ self.IO_BANK0_BASE | self.mem_clr |  ( 4 + 8 * self.scl) ] = 0x1f
		mem32[ self.IO_BANK0_BASE | self.mem_set |  ( 4 + 8 * self.scl) ] = 3
		# 4 enable i2c 
		self.set_reg(self.IC_ENABLE, 1)


	def anyRead(self):
		status = mem32[ self.i2c_base | self.IC_RAW_INTR_STAT] & 0x20
		if status :
			return True
		return False

	def put(self, data):
		# reset flag       
		self.clr_reg(self.IC_CLR_TX_ABRT,1)
		status = mem32[ self.i2c_base | self.IC_CLR_RD_REQ]
		mem32[ self.i2c_base | self.IC_DATA_CMD] = data  & 0xff

	def any(self):
		# get IC_STATUS
		status = mem32[ self.i2c_base | self.IC_STATUS]
		# check RFNE receive fifio not empty
		if (status &  8) :
			return True
		return False
	
	def get(self):
		if not self.any():
			return None
		data = []
		while self.any():
			data.append(mem32[ self.i2c_base | self.IC_DATA_CMD] & 0xff)
		return data

"""
Control software for a Grogu animatronic based around the Pimoroni Servo 2040 board.
"""

POWER_INDICATOR_LED = 0
STARTUP_INDICATOR_LED = 1
I2C_INDICATOR_LED = 2
LED_BRIGHTNESS = 0.3
MODE_SELECT_PIN = servo2040.SENSOR_1_ADDR

def set_led_colour(leds, led: int, r: int, g: int, b: int):
	leds.set_rgb(led, (int)(r * LED_BRIGHTNESS), (int)(g * LED_BRIGHTNESS), (int)(b * LED_BRIGHTNESS))

def read_servo_position(bus, leds):
	set_led_colour(leds, I2C_INDICATOR_LED, 0, 0, 255)
	try:
		return bus.get()
	except:
		set_led_colour(leds, I2C_INDICATOR_LED, 255, 0, 0)
		print("[", time.time(), "] Error reading from i2c bus")
		time.sleep(2)
		return None

# Create the LED bar, using PIO 1 and State Machine 0
led_bar = WS2812(servo2040.NUM_LEDS, 1, 0, servo2040.LED_DATA)
# Create the user button
user_sw = Button(servo2040.USER_SW)
# Start updating the LED bar
led_bar.start()

# Indicate that power on
set_led_colour(led_bar, POWER_INDICATOR_LED, 0, 255, 0)

# Configure analog mux
sen_adc = Analog(servo2040.SHARED_ADC)
mux = AnalogMux(servo2040.ADC_ADDR_0, servo2040.ADC_ADDR_1, servo2040.ADC_ADDR_2,
                muxed_pin=Pin(servo2040.SHARED_ADC))
sensor_addrs = list(range(servo2040.SENSOR_1_ADDR, servo2040.SENSOR_6_ADDR + 1))
for addr in sensor_addrs:
    mux.configure_pull(addr, Pin.PULL_DOWN)

# Create a list of servos for pins 1 to 11 (inclusive).
START_PIN = servo2040.SERVO_1
END_PIN = servo2040.SERVO_12
servos = [Servo(i) for i in range(START_PIN, END_PIN + 1)]
NUM_SERVOS = len(servos)

print("Hello")

# Home all servos
for s in servos:
	s.enable()
time.sleep(2)
print("To Max")
for s in servos:
	s.to_max()
time.sleep(2)
print("To Min")
for s in servos:
	s.to_min()
time.sleep(2)
print("To Mid")
for s in servos:
	s.to_mid()
time.sleep(2)

mux.select(MODE_SELECT_PIN)
if round(sen_adc.read_voltage(), 3) > 3:
	for i in range(1, servo2040.NUM_LEDS):
		set_led_colour(led_bar, i, 200, 0, 255)
	exit(0)

i2c = i2c_peripheral(0, sda=20, scl=21, peripheralAddress=8)

# Indicate that we've reached main loop
set_led_colour(led_bar, STARTUP_INDICATOR_LED, 200, 0, 255)

while not user_sw.raw():
	position = read_servo_position(i2c, led_bar)
	if position is None:
		continue
	if position[0] > NUM_SERVOS - 1:
		continue
	servos[position[0]].value(position[1])

for s in servos:
	s.disable()
for i in range(servo2040.NUM_LEDS):
	set_led_colour(led_bar, i, 255, 0, 0)
