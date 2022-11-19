# Grogu Animatronic Controller

This repository contains code for controlling a Grogu animatronic based on the [Pimoroni Servo 2040 platform](https://shop.pimoroni.com/products/servo-2040?variant=39800591679571).

It requires that the Servo 2040 is running the [Pimoroni MicroPython](https://github.com/pimoroni/pimoroni-pico/releases).

The file `grogu_servo_2040.py` should be loaded onto the Servo 2040 board.

You can then connect to the Servo 2040 via Bluetooth using `connect.sh` with a single argument, the MAC of the Bluetooth device.

Then run the control software with `cargo run`. Connect a games controller and pres buttons.
