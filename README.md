# watlow\_controller

Python interface for communicating with Watlow F4 and Watlow 93 temperature controllers via serial (Modbus/RS-485).

## Features

* Control Watlow F4 and 93 controllers over serial (RS-485)
* Read and write process variables
* Set temperature setpoints and ramp rates
* Designed for integration into lab automation workflows

## Requirements

* Python 3.11+
* Watlow controller (F4 or 93) with serial communication enabled
* RS-485 to USB adapter (e.g. Safe Port SP-1150T)

## Installation

Use Poetry to install:

```bash
poetry add git+https://github.com/shanedertrain/watlow_controller.git
```

Or clone locally for development:

```bash
git clone https://github.com/shanedertrain/watlow_controller.git
cd watlow_controller
poetry install
```

## Usage

```python
from watlow_controller import WatlowF4

controller = WatlowF4(port="COM4", baudrate=19200)
controller.set_temperature(100.0)
temp = controller.read_temperature()
print(f"Current temperature: {temp} °C")
```

## Development

Install with:

```bash
poetry install
```

Run tests:

```bash
poetry run pytest
```

## License

GNU GENERAL PUBLIC LICENSE © 2007 Cameron Basham
