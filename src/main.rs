use std::{
    io::{BufRead, BufReader, BufWriter, Write},
    thread,
    time::Duration,
};

use serialport::{Parity, StopBits};

const MAGIC_HEADER: [u8; 4] = [0x04, 0x0c, 0x08, 0x0e]; // 4, 12, 8, 14
const COMMAND_SERVO_POSITION: [u8; 2] = [0x05, 0x08];
const PACKET_SIZE: usize = 16;

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

    buf[PACKET_SIZE - 3] = 0;

    /*let mut pos: u8 = 0;
    let mut add = true;
    loop {
        // println!("Setting to pos {pos}");
        // println!("{:#04x?}", buf);
        buf[PACKET_SIZE - 2] = pos;

        port.write_all(&buf).unwrap();
        port.flush().unwrap();

        if add == true {
            if let Some(val) = pos.checked_add(1) {
                pos = val;
            } else {
                pos = 254;
                add = false;
            }
        } else {
            if let Some(val) = pos.checked_sub(1) {
                pos = val;
            } else {
                pos = 1;
                add = true;
            }
        }
    }*/

    // writer.write_all(b"MODE\n").unwrap();
    // writer.flush().unwrap();

    // Iterate over all connected gamepads
    for (_id, gamepad) in gilrs.gamepads() {
        println!("{} is {:?}", gamepad.name(), gamepad.power_info());
    }

    let mut active_gamepad = None;

    let mut pressed = false;

    loop {
        // Examine new events
        while let Some(Event { id, event, time }) = gilrs.next_event() {
            println!("{:?} New event from {}: {:?}", time, id, event);
            /*match event {
                gilrs::EventType::ButtonPressed(_, _) => {}
                gilrs::EventType::ButtonRepeated(_, _) => {}
                gilrs::EventType::ButtonReleased(_, _) => {}
                gilrs::EventType::ButtonChanged(button, val, _) => match button {
                    Button::South => todo!(),
                    Button::East => todo!(),
                    Button::North => todo!(),
                    Button::West => todo!(),
                    Button::C => todo!(),
                    Button::Z => todo!(),
                    Button::LeftTrigger => todo!(),
                    Button::LeftTrigger2 => todo!(),
                    Button::RightTrigger => todo!(),
                    Button::RightTrigger2 => todo!(),
                    Button::Select => todo!(),
                    Button::Start => todo!(),
                    Button::Mode => todo!(),
                    Button::LeftThumb => todo!(),
                    Button::RightThumb => todo!(),
                    Button::DPadUp => todo!(),
                    Button::DPadDown => todo!(),
                    Button::DPadLeft => todo!(),
                    Button::DPadRight => todo!(),
                    Button::Unknown => todo!(),
                },
                gilrs::EventType::AxisChanged(axis, val, _) => {}
                gilrs::EventType::Connected => {}
                gilrs::EventType::Disconnected => {}
                gilrs::EventType::Dropped => {}
            }*/
            active_gamepad = Some(id);
        }

        // You can also use cached gamepad state
        if let Some(gamepad) = active_gamepad.map(|id| gilrs.gamepad(id)) {
            if gamepad.is_pressed(Button::RightTrigger) {
                if !pressed {
                    buf[PACKET_SIZE - 3] = 0x00;
                    buf[PACKET_SIZE - 2] = 0xff;

                    pressed = true;

                    port.write_all(&buf).unwrap();
                    port.flush().unwrap();
                }
            } else if pressed {
                buf[PACKET_SIZE - 3] = 0x00;
                buf[PACKET_SIZE - 2] = 0x00;

                pressed = false;

                port.write_all(&buf).unwrap();
                port.flush().unwrap();
            }
        }
    }
}
