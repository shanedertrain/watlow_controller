import os

if os.environ.get("CI", "").lower() == "true":
    from .watlow_f4_dummy import ControllerClass
else:
    from .watlow_f4 import WatlowF4 as ControllerClass

WatlowF4 = ControllerClass

__all__ = ["WatlowF4"]
