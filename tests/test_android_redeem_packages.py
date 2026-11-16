"""Phone short-code redeem needs an Android PyNaCl wheel on the pip line.

PyPI has no Android wheel. Chaquopy's index has PyNaCl 1.5.0 for cp311
arm64-v8a and x86_64. A newer PyNaCl would be built from source and fail.
autobahn 24.4.2 is the last pure-Python release that still allows
cryptography below 45. The mailbox server and the transit relay stay off
the phone.
"""

from pathlib import Path

GRADLE = (
    Path(__file__).resolve().parents[1] / "android" / "app" / "build.gradle.kts"
)


def _pip_block(text: str) -> str:
    start = text.index("pip {")
    end = text.index("}", start)
    return text[start:end]


def test_phone_pip_pins_android_pynacl_and_keeps_the_cryptography_cap():
    block = _pip_block(GRADLE.read_text())
    assert 'install("pynacl==1.5.0")' in block
    assert 'install("autobahn[twisted]==24.4.2")' in block
    assert 'install("magic-wormhole==0.24.0")' in block
    assert 'install("twisted==25.5.0")' in block
    assert 'install("cryptography<45")' in block
    assert "mailbox-server" not in block
    assert "transit-relay" not in block
    assert "cryptography>=" not in block
