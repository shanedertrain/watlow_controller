# tests/test_watlow.py

import pytest
from watlow_controller.watlow_f4 import WatlowF4

def test_init():
    controller = WatlowF4(0, com_port="COM1")
    assert controller.com_port == "COM1"
