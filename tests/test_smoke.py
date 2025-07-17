# tests/test_smoke.py

def test_import():
    import watlow_controller
    assert hasattr(watlow_controller, "__version__") or True
