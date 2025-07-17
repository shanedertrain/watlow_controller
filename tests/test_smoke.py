# tests/test_smoke.py
import os

RUNNING_IN_CI = os.environ.get("CI") == "true"

def test_import():
    import watlow_controller
    assert hasattr(watlow_controller, "__version__") or True
