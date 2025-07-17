import os
import typing as t

from watlow_controller.watlow_f4 import WatlowF4

class DummyWatlowF4(WatlowF4):
    def __init__(self, slave_address: int, com_port: t.Optional[str] = None):
        self.slave_address = slave_address
        self.com_port = com_port or "DUMMY"
        self.instrument = None
        self.logger = self.setup_logger()
        self.logger.info("DummyWatlowF4 initialized.")

    def find_and_connect(self, com_port: t.Optional[str] = None):
        self.logger.info(f"Pretending to connect to port {com_port or 'DUMMY'}")
        return True

    def try_port(self, com_port: t.Optional[str]) -> bool:
        self.logger.info(f"Pretending to try port {com_port}")
        return True

    def read_temp(self) -> float:
        return 123.4


ControllerClass = DummyWatlowF4 if os.environ.get("CI") == "true" else WatlowF4
