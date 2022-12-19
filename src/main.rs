use std::{
    io::{BufRead, BufReader, BufWriter, Write},
    thread,
    time::Duration,
};

use serialport::{Parity, SerialPort, StopBits};

const MAGIC_HEADER: [u8; 4] = [0x04, 0x0c, 0x08, 0x0e]; // 4, 12, 8, 14
const COMMAND_SERVO_POSITION: [u8; 2] = [0x05, 0x08];
const PACKET_SIZE: usize = 16;

#[derive(Clone)]
struct GamepadState {
    right_trigger: f32,
    left_trigger: f32,
    right_bumper: bool,
    left_bumper: bool,
    right_stick_x: f32,
    right_stick_y: f32,
}

impl Default for GamepadState {
    fn default() -> Self {
        Self {
            right_trigger: Default::default(),
            left_trigger: Default::default(),
            right_bumper: Default::default(),
            left_bumper: Default::default(),
            right_stick_x: Default::default(),
            right_stick_y: Default::default(),
        }
    }
}

const EYE_TOP_LEFT_OPEN: u8 = 255;
const EYE_TOP_LEFT_CLOSED: u8 = 0;
const EYE_TOP_LEFT_MID: u8 = 128;
const EYE_BOTTOM_LEFT_OPEN: u8 = 0;
const EYE_BOTTOM_LEFT_CLOSED: u8 = 255;
const EYE_BOTTOM_LEFT_MID: u8 = 128;
const EYE_TOP_RIGHT_OPEN: u8 = 0;
const EYE_TOP_RIGHT_CLOSED: u8 = 255;
const EYE_TOP_RIGHT_MID: u8 = 128;
const EYE_BOTTOM_RIGHT_OPEN: u8 = 255;
const EYE_BOTTOM_RIGHT_CLOSED: u8 = 0;
const EYE_BOTTOM_RIGHT_MID: u8 = 128;

const MOUTH_OPEN: u8 = 255;
const MOUTH_CLOSED: u8 = 0;
const MOUTH_MID: u8 = 128;

const EAR_TOP_LEFT_FORWARD: u8 = 255;
const EAR_TOP_LEFT_BACKWARD: u8 = 0;
const EAR_TOP_LEFT_MID: u8 = 128;
const EAR_BOTTOM_LEFT_UP: u8 = 255;
const EAR_BOTTOM_LEFT_DOWN: u8 = 0;
const EAR_BOTTOM_LEFT_MID: u8 = 128;
const EAR_TOP_RIGHT_FORWARD: u8 = 0;
const EAR_TOP_RIGHT_BACKWARD: u8 = 255;
const EAR_TOP_RIGHT_MID: u8 = 128;
const EAR_BOTTOM_RIGHT_UP: u8 = 0;
const EAR_BOTTOM_RIGHT_DOWN: u8 = 255;
const EAR_BOTTOM_RIGHT_MID: u8 = 128;

const SERVO_MOUTH: u8 = 0;
const SERVO_EYE_BL: u8 = 2;
const SERVO_EYE_BR: u8 = 3;
const SERVO_EYE_TL: u8 = 4;
const SERVO_EYE_TR: u8 = 5;
const SERVO_EAR_BL: u8 = 6;
const SERVO_EAR_BR: u8 = 7;
const SERVO_EAR_TL: u8 = 8;
const SERVO_EAR_TR: u8 = 9;

const SERVO_BYTE: usize = PACKET_SIZE - 3;
const DATA_BYTE: usize = PACKET_SIZE - 2;

fn map_from_to(val: f32, original_min: f32, original_max: f32, new_min: f32, new_max: f32) -> f32 {
    (val - original_min) / (original_max - original_min) * (new_max - new_min) + new_min
}

fn send(port: &mut Box<dyn SerialPort>, buf: &mut [u8; PACKET_SIZE], servo: u8, position: u8) {
    buf[SERVO_BYTE] = servo;
    buf[DATA_BYTE] = position;
    port.write_all(buf).unwrap();
    port.flush().unwrap();
}

fn main() {
    use gilrs::{Button, Event, Gilrs};

    let mut gilrs = Gilrs::new().unwrap();

    let ports = serialport::available_ports().expect("No ports found!");
    for p in ports {
        println!("{}", p.port_name);
    }

    let mut port = serialport::new("/dev/rfcomm0", 9600)
        // .parity(Parity::Odd)
        .stop_bits(StopBits::One)
        .timeout(Duration::from_millis(100))
        .open()
        .expect("Failed to open port");

    let mut buf: [u8; PACKET_SIZE] = [0; PACKET_SIZE];
    buf[0] = 0xff;
    for i in 0..MAGIC_HEADER.len() {
        buf[1 + i] = MAGIC_HEADER[i];
    }
    for i in 0..COMMAND_SERVO_POSITION.len() {
        buf[1 + MAGIC_HEADER.len() + i] = COMMAND_SERVO_POSITION[i]
    }
    buf[PACKET_SIZE - 1] = b"\n"[0];

    send(&mut port, &mut buf, SERVO_MOUTH, 0);
    send(&mut port, &mut buf, SERVO_EYE_BL, 128);
    send(&mut port, &mut buf, SERVO_EYE_BR, 128);
    send(&mut port, &mut buf, SERVO_EYE_TL, 128);
    send(&mut port, &mut buf, SERVO_EYE_TR, 128);
    send(&mut port, &mut buf, SERVO_EAR_BL, 128);
    send(&mut port, &mut buf, SERVO_EAR_BR, 128);
    send(&mut port, &mut buf, SERVO_EAR_TL, 128);
    send(&mut port, &mut buf, SERVO_EAR_TR, 128);

    // Iterate over all connected gamepads
    for (_id, gamepad) in gilrs.gamepads() {
        println!("{} is {:?}", gamepad.name(), gamepad.power_info());
    }

    let mut prev_state = GamepadState::default();

    loop {
        // Examine new events
        while let Some(Event { id, event, time }) = gilrs.next_event() {
            let mut gamepad_state = prev_state.clone();

            println!("{:?} New event from {}: {:?}", time, id, event);
            match event {
                gilrs::EventType::ButtonPressed(button, _) => match button {
                    Button::LeftTrigger => gamepad_state.left_bumper = true,
                    Button::RightTrigger => gamepad_state.right_bumper = true,
                    _ => {}
                },
                gilrs::EventType::ButtonRepeated(_, _) => {}
                gilrs::EventType::ButtonReleased(button, _) => match button {
                    Button::LeftTrigger => gamepad_state.left_bumper = false,
                    Button::RightTrigger => gamepad_state.right_bumper = false,
                    _ => {}
                },
                gilrs::EventType::ButtonChanged(button, val, _) => match button {
                    Button::LeftTrigger2 => gamepad_state.left_trigger = val,
                    Button::RightTrigger2 => gamepad_state.right_trigger = val,
                    _ => {}
                },
                gilrs::EventType::AxisChanged(axis, val, _) => match axis {
                    gilrs::Axis::RightStickX => {
                        if val.abs() > 0.48 && val.abs() <= 1.0 {
                            if val < 0.0 {
                                gamepad_state.right_stick_x = -1.0;
                            } else {
                                gamepad_state.right_stick_x = 1.0;
                            }
                        } else {
                            gamepad_state.right_stick_x = 0.0;
                        }
                    }
                    gilrs::Axis::RightStickY => {
                        if val.abs() > 0.48 && val.abs() <= 1.0 {
                            if val < 0.0 {
                                gamepad_state.right_stick_y = -1.0;
                            } else {
                                gamepad_state.right_stick_y = 1.0;
                            }
                        } else {
                            gamepad_state.right_stick_y = 0.0;
                        }
                    }
                    _ => {}
                },
                gilrs::EventType::Connected => {}
                gilrs::EventType::Disconnected => {}
                gilrs::EventType::Dropped => {}
            }

            if gamepad_state.right_bumper != prev_state.right_bumper {
                if gamepad_state.right_bumper == true {
                    send(&mut port, &mut buf, SERVO_MOUTH, MOUTH_OPEN);
                } else {
                    send(&mut port, &mut buf, SERVO_MOUTH, MOUTH_CLOSED);
                }
            } else if gamepad_state.left_bumper != prev_state.left_bumper {
                if gamepad_state.left_bumper == true {
                    send(&mut port, &mut buf, SERVO_MOUTH, MOUTH_MID);
                } else {
                    send(&mut port, &mut buf, SERVO_MOUTH, MOUTH_CLOSED);
                }
            }

            if gamepad_state.right_trigger != prev_state.right_trigger {
                let val_tl = map_from_to(
                    gamepad_state.right_trigger,
                    0.0,
                    1.0,
                    EYE_TOP_LEFT_MID.into(),
                    EYE_TOP_LEFT_CLOSED.into(),
                ) as u8;
                let val_bl = map_from_to(
                    gamepad_state.right_trigger,
                    0.0,
                    1.0,
                    EYE_BOTTOM_LEFT_MID.into(),
                    EYE_BOTTOM_LEFT_CLOSED.into(),
                ) as u8;
                let val_tr = map_from_to(
                    gamepad_state.right_trigger,
                    0.0,
                    1.0,
                    EYE_TOP_RIGHT_MID.into(),
                    EYE_TOP_RIGHT_CLOSED.into(),
                ) as u8;
                let val_br = map_from_to(
                    gamepad_state.right_trigger,
                    0.0,
                    1.0,
                    EYE_BOTTOM_RIGHT_MID.into(),
                    EYE_BOTTOM_RIGHT_CLOSED.into(),
                ) as u8;

                send(&mut port, &mut buf, SERVO_EYE_TL, val_tl);
                send(&mut port, &mut buf, SERVO_EYE_BL, val_bl);
                send(&mut port, &mut buf, SERVO_EYE_TR, val_tr);
                send(&mut port, &mut buf, SERVO_EYE_BR, val_br);
            } else if gamepad_state.left_trigger != prev_state.left_trigger {
                let val_tl = map_from_to(
                    gamepad_state.left_trigger,
                    0.0,
                    1.0,
                    EYE_TOP_LEFT_MID.into(),
                    EYE_TOP_LEFT_OPEN.into(),
                ) as u8;
                let val_bl = map_from_to(
                    gamepad_state.left_trigger,
                    0.0,
                    1.0,
                    EYE_BOTTOM_LEFT_MID.into(),
                    EYE_BOTTOM_LEFT_OPEN.into(),
                ) as u8;
                let val_tr = map_from_to(
                    gamepad_state.left_trigger,
                    0.0,
                    1.0,
                    EYE_TOP_RIGHT_MID.into(),
                    EYE_TOP_RIGHT_OPEN.into(),
                ) as u8;
                let val_br = map_from_to(
                    gamepad_state.left_trigger,
                    0.0,
                    1.0,
                    EYE_BOTTOM_RIGHT_MID.into(),
                    EYE_BOTTOM_RIGHT_OPEN.into(),
                ) as u8;

                send(&mut port, &mut buf, SERVO_EYE_TL, val_tl);
                send(&mut port, &mut buf, SERVO_EYE_BL, val_bl);
                send(&mut port, &mut buf, SERVO_EYE_TR, val_tr);
                send(&mut port, &mut buf, SERVO_EYE_BR, val_br);
            }

            if gamepad_state.right_stick_x != prev_state.right_stick_x {
                let mut val_tr = EAR_TOP_RIGHT_MID;
                let mut val_tl = EAR_TOP_LEFT_MID;
                if gamepad_state.right_stick_x >= 0.48 {
                    val_tr = EAR_TOP_RIGHT_BACKWARD;
                    val_tl = EAR_TOP_LEFT_BACKWARD;
                } else if gamepad_state.right_stick_x <= -0.48 {
                    val_tr = EAR_TOP_RIGHT_FORWARD;
                    val_tl = EAR_TOP_LEFT_FORWARD;
                }

                send(&mut port, &mut buf, SERVO_EAR_TR, val_tr);
                send(&mut port, &mut buf, SERVO_EAR_TL, val_tl);
            }

            if gamepad_state.right_stick_y != prev_state.right_stick_y {
                let mut val_br = EAR_BOTTOM_RIGHT_MID;
                let mut val_bl = EAR_BOTTOM_LEFT_MID;
                if gamepad_state.right_stick_y >= 0.48 {
                    val_br = EAR_BOTTOM_RIGHT_UP;
                    val_bl = EAR_BOTTOM_LEFT_UP;
                } else if gamepad_state.right_stick_y <= -0.48 {
                    val_br = EAR_BOTTOM_RIGHT_DOWN;
                    val_bl = EAR_BOTTOM_LEFT_DOWN;
                }

                send(&mut port, &mut buf, SERVO_EAR_BR, val_br);
                send(&mut port, &mut buf, SERVO_EAR_BL, val_bl);
            }

            prev_state = gamepad_state;
        }
    }
}
