"""Window size and position survive a quit, and a bad file does not."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import (  # noqa: E402
    DEFAULT_WINDOW_SIZE,
    WINDOW_GEOMETRY_FILE,
    _GEOMETRY_VERSION,
    _QWIDGETSIZE_MAX,
    MainWindow,
    _window_record,
)


def _hide(window: MainWindow) -> None:
    window.poll.stop()
    window.win.hide()
    if window.tray is not None:
        window.tray.hide()


def _saved_record(home: Path) -> dict:
    return json.loads((home / WINDOW_GEOMETRY_FILE).read_text(encoding="utf-8"))


def _write_record(home: Path, payload: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload) + "\n"
    (home / WINDOW_GEOMETRY_FILE).write_text(text, encoding="utf-8")


def _valid_record(**overrides) -> dict:
    record = {
        "version": _GEOMETRY_VERSION,
        "x": 10,
        "y": 12,
        "width": 640,
        "height": 480,
        "maximized": False,
    }
    record.update(overrides)
    return record


def test_geometry_round_trips_across_two_windows(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = MainWindow(home=home, autoload=False)
    try:
        first.win.show()
        first.QtWidgets.QApplication.processEvents()
        # Wider than the layout's narrow hint, still inside the offscreen desktop,
        # and not the 920 default. Height follows the layout when 500 is too short.
        first.win.resize(700, 500)
        first.win.move(15, 10)
        first.QtWidgets.QApplication.processEvents()
        saved = (first.win.width(), first.win.height(), first.win.x(), first.win.y())
        assert saved[0] != DEFAULT_WINDOW_SIZE[0]
        first.quit()
    finally:
        _hide(first)

    record = _saved_record(home)
    assert record["version"] == _GEOMETRY_VERSION
    assert (record["width"], record["height"], record["x"], record["y"]) == saved
    assert record["maximized"] is False

    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert (second.win.width(), second.win.height(), second.win.x(), second.win.y()) == saved
    finally:
        _hide(second)


@pytest.mark.parametrize("version", [1, 3])
def test_other_geometry_version_opens_at_the_default(tmp_path: Path, version: int) -> None:
    """Version 2 is the only record. A 1 or a 3 with valid fields stays at the default."""
    home = tmp_path / "home"
    _write_record(home, _valid_record(version=version, x=40, y=30, width=700, height=500))
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())
        assert window.win.x() != 40 or window.win.width() == 920
    finally:
        _hide(window)


def _unmaximize_size(home: Path) -> tuple | None:
    """Save a maximized window and return the normal size and position it had.

    None when this platform does not report a maximized window.
    """
    first = MainWindow(home=home, autoload=False)
    try:
        first.show()
        first.QtWidgets.QApplication.processEvents()
        first.win.resize(700, 500)
        first.win.move(30, 20)
        first.QtWidgets.QApplication.processEvents()
        normal = (
            first.win.width(),
            first.win.height(),
            first.win.x(),
            first.win.y(),
        )
        first.win.showMaximized()
        first.QtWidgets.QApplication.processEvents()
        if not first.win.isMaximized():
            return None
        first.quit()
    finally:
        _hide(first)
    return normal


def test_unmaximize_restores_the_normal_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    normal = _unmaximize_size(home)
    if normal is None:
        pytest.skip("offscreen does not report isMaximized()")
    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert second.win.isMaximized()
        second.win.showNormal()
        second.QtWidgets.QApplication.processEvents()
        assert (second.win.width(), second.win.height(), second.win.x(), second.win.y()) == normal
    finally:
        _hide(second)


def test_three_maximize_cycles_keep_the_normal_position(tmp_path: Path) -> None:
    home = tmp_path / "home"
    normal = _unmaximize_size(home)
    if normal is None:
        pytest.skip("offscreen does not report isMaximized()")
    for _ in range(3):
        window = MainWindow(home=home, autoload=False)
        try:
            window.show()
            window.QtWidgets.QApplication.processEvents()
            assert window.win.isMaximized()
            window.win.showNormal()
            window.QtWidgets.QApplication.processEvents()
            assert (
                window.win.width(),
                window.win.height(),
                window.win.x(),
                window.win.y(),
            ) == normal
            window.win.showMaximized()
            window.QtWidgets.QApplication.processEvents()
            window.quit()
        finally:
            _hide(window)


def test_maximized_record_round_trips(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = MainWindow(home=home, autoload=False)
    try:
        first.show()
        first.QtWidgets.QApplication.processEvents()
        first.win.resize(700, 500)
        first.win.move(30, 20)
        first.QtWidgets.QApplication.processEvents()
        first.win.showMaximized()
        first.QtWidgets.QApplication.processEvents()
        if not first.win.isMaximized():
            pytest.skip("offscreen does not report isMaximized()")
        first.quit()
    finally:
        _hide(first)

    record = _saved_record(home)
    assert record["maximized"] is True
    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert second.win.isMaximized()
    finally:
        _hide(second)


def test_offscreen_geometry_falls_back_to_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = MainWindow(home=home, autoload=False)
    try:
        first.win.show()
        first.QtWidgets.QApplication.processEvents()
        first.win.resize(400, 300)
        first.win.move(-100000, -100000)
        first.QtWidgets.QApplication.processEvents()
        first.quit()
    finally:
        _hide(first)

    second = MainWindow(home=home, autoload=False)
    try:
        second.win.show()
        second.QtWidgets.QApplication.processEvents()
        assert (second.win.width(), second.win.height()) == (920, second.win.minimumHeight())
        assert second.win.x() >= 0 and second.win.y() >= 0
        frame = second.win.frameGeometry()
        screens = second.QtGui.QGuiApplication.screens()
        assert any(screen.availableGeometry().intersects(frame) for screen in screens)
    finally:
        _hide(second)


def _title_grab_inside(window: MainWindow) -> bool:
    frame = window.win.frameGeometry()
    strip = window.QtCore.QRect(
        frame.x(),
        frame.y(),
        min(frame.width(), 80),
        min(frame.height(), 28),
    )
    screens = window.QtGui.QGuiApplication.screens()
    return any(screen.availableGeometry().contains(strip) for screen in screens)


def _save_moved(home: Path, x: int, y: int, width: int, height: int) -> int:
    """Save a moved window and return the width it really had.

    The layout's minimum width depends on the platform fonts (863 px on the
    windows-2022 runner), so a requested width below it is clamped by Qt.
    The restore must bring back the width that was saved, whatever it was.
    """
    first = MainWindow(home=home, autoload=False)
    try:
        first.win.show()
        first.QtWidgets.QApplication.processEvents()
        first.win.resize(width, height)
        first.win.move(x, y)
        first.QtWidgets.QApplication.processEvents()
        saved_width = first.win.width()
        first.quit()
    finally:
        _hide(first)
    return saved_width


def test_title_bar_above_the_screen_stays_on_screen(tmp_path: Path) -> None:
    home = tmp_path / "home"
    # 700 fits an 800 px offscreen desktop, is under the 920 default, and is
    # still not that default when Windows clamps it up to 863.
    saved_width = _save_moved(home, 40, -650, 700, 500)
    assert saved_width != DEFAULT_WINDOW_SIZE[0]
    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert second.win.width() == saved_width
        assert _title_grab_inside(second)
    finally:
        _hide(second)


def test_title_bar_left_of_the_screen_stays_on_screen(tmp_path: Path) -> None:
    home = tmp_path / "home"
    saved_width = _save_moved(home, -200, 40, 700, 500)
    assert saved_width != DEFAULT_WINDOW_SIZE[0]
    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert second.win.width() == saved_width
        assert _title_grab_inside(second)
    finally:
        _hide(second)


def test_title_bar_partly_off_the_left_edge_stays_on_screen(tmp_path: Path) -> None:
    """x=-40 leaves part of the 80px grab on the screen and part off it.

    `intersects` would call that on-screen and keep the saved x. The grab has
    to end fully inside availableGeometry.
    """
    home = tmp_path / "home"
    saved_width = _save_moved(home, -40, 40, 700, 500)
    assert saved_width != DEFAULT_WINDOW_SIZE[0]
    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert second.win.width() == saved_width
        assert _title_grab_inside(second)
    finally:
        _hide(second)


def test_deeply_nested_geometry_file_uses_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / WINDOW_GEOMETRY_FILE).write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())
    finally:
        _hide(window)


def test_failed_geometry_replace_keeps_the_previous_file(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        window.win.resize(700, 500)
        window.win.move(15, 10)
        window._save_window_geometry()
        path = home / WINDOW_GEOMETRY_FILE
        good = path.read_bytes()

        def fail_replace(*_args, **_kwargs):
            raise OSError("replace failed")

        monkeypatch.setattr(os, "replace", fail_replace)
        window.win.resize(640, 480)
        window._save_window_geometry()
        assert path.read_bytes() == good
        assert not (home / "window-geometry.json.tmp").exists()
    finally:
        _hide(window)


def test_corrupt_geometry_file_uses_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / WINDOW_GEOMETRY_FILE).write_text("{", encoding="utf-8")
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())
    finally:
        _hide(window)


def _assert_default_size(window: MainWindow) -> None:
    window.win.show()
    window.QtWidgets.QApplication.processEvents()
    assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("x", (1 << 30) + 1),
        ("y", -(1 << 30) - 1),
        ("width", _QWIDGETSIZE_MAX + 1),
        ("height", 0),
        ("maximized", 1),
        ("width", True),
        ("x", 12.0),
    ],
    ids=["bad-x", "bad-y", "bad-width", "bad-height", "maximized-int", "bool-as-int", "float"],
)
def test_window_record_rejects_one_bad_field(field: str, bad) -> None:
    raw = _valid_record()
    raw[field] = bad
    assert _window_record(raw) is None


def test_bad_record_opens_at_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _write_record(home, _valid_record(x=(1 << 30) + 1))
    window = MainWindow(home=home, autoload=False)
    try:
        _assert_default_size(window)
        log = (home / "logs" / "sync-ui.log").read_text(encoding="utf-8")
        headers = [line for line in log.splitlines() if line.endswith(" window geometry")]
        assert len(headers) == 1
        assert "not usable" in log
    finally:
        _hide(window)


def test_oversized_record_uses_the_default_size(tmp_path: Path) -> None:
    """16777215 passes the range check and must still not be applied."""
    home = tmp_path / "home"
    _write_record(home, _valid_record(width=_QWIDGETSIZE_MAX, height=400))
    window = MainWindow(home=home, autoload=False)
    try:
        window.show()
        window.QtWidgets.QApplication.processEvents()
        assert window.win.width() != _QWIDGETSIZE_MAX
        assert window.win.height() != _QWIDGETSIZE_MAX
        assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())
        span = window._screen_span()
        assert window.win.width() <= max(span.width(), 920)
        assert window.win.height() <= max(span.height(), window.win.minimumHeight())
    finally:
        _hide(window)


def test_oversized_height_uses_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _write_record(home, _valid_record(width=640, height=_QWIDGETSIZE_MAX))
    window = MainWindow(home=home, autoload=False)
    try:
        window.show()
        window.QtWidgets.QApplication.processEvents()
        assert window.win.height() != _QWIDGETSIZE_MAX
        assert window.win.width() == DEFAULT_WINDOW_SIZE[0]
    finally:
        _hide(window)


def _block_huge_resize(monkeypatch):
    """Record resize calls and refuse a span Qt has segfaulted on.

    The cap is far above a real window and far below QWIDGETSIZE_MAX, so the
    assertion can fail before the C++ call.
    """
    from PyQt5.QtWidgets import QWidget

    orig = QWidget.resize
    calls: list[tuple[int, int]] = []

    def wrapped(self, w, h=None):
        if h is None:
            width, height = int(w.width()), int(w.height())
            calls.append((width, height))
            if width > 8192 or height > 8192:
                return
            orig(self, w)
            return
        width, height = int(w), int(h)
        calls.append((width, height))
        if width > 8192 or height > 8192:
            return
        orig(self, width, height)

    monkeypatch.setattr(QWidget, "resize", wrapped)
    return calls


def _within_screen(window: MainWindow, calls: list[tuple[int, int]]) -> None:
    span = window._screen_span()
    hint = window.win.minimumSizeHint()
    cap_w = max(span.width(), DEFAULT_WINDOW_SIZE[0], hint.width())
    cap_h = max(span.height(), DEFAULT_WINDOW_SIZE[1], hint.height())
    assert calls
    assert all(w <= cap_w and h <= cap_h for w, h in calls)


def test_fitter_alone_rejects_an_oversized_record(tmp_path: Path, monkeypatch) -> None:
    """The fitter pins the oversize check by itself, with the post-apply guard off."""
    home = tmp_path / "home"
    _write_record(home, _valid_record(width=_QWIDGETSIZE_MAX, height=_QWIDGETSIZE_MAX))
    seen: list[tuple[int, int]] = []
    orig = MainWindow._fitted_size

    def wrapped(self, width, height):
        got = orig(self, width, height)
        seen.append((int(got[0]), int(got[1])))
        return got

    monkeypatch.setattr(MainWindow, "_fitted_size", wrapped)
    monkeypatch.setattr(MainWindow, "_guard_applied_size", lambda self, *args, **kwargs: None)
    calls = _block_huge_resize(monkeypatch)
    window = MainWindow(home=home, autoload=False)
    try:
        window.show()
        window.QtWidgets.QApplication.processEvents()
        assert seen
        assert seen[-1] == DEFAULT_WINDOW_SIZE
        _within_screen(window, calls)
        assert window.win.width() != _QWIDGETSIZE_MAX
        assert window.win.height() != _QWIDGETSIZE_MAX
        assert window.win.width() == DEFAULT_WINDOW_SIZE[0]
    finally:
        _hide(window)


def test_guard_resets_a_size_the_fitter_let_through(tmp_path: Path, monkeypatch) -> None:
    """The post-apply guard is the backstop when the fitter does not shrink."""
    home = tmp_path / "home"
    _write_record(home, _valid_record())

    def keep(self, width, height):
        return (width, height)

    monkeypatch.setattr(MainWindow, "_fitted_size", keep)
    calls = _block_huge_resize(monkeypatch)
    window = MainWindow(home=home, autoload=False)
    try:
        window.show()
        window.QtWidgets.QApplication.processEvents()
        window.win.move(40, 36)
        window.win.resize(700, 480)
        window.QtWidgets.QApplication.processEvents()
        window._apply_window_record(10, 12, _QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX, False)
        window.QtWidgets.QApplication.processEvents()
        _within_screen(window, calls)
        assert window.win.width() != _QWIDGETSIZE_MAX
        assert window.win.height() != _QWIDGETSIZE_MAX
        assert window.win.x() == 0 and window.win.y() == 0
        assert window.win.width() == DEFAULT_WINDOW_SIZE[0]
    finally:
        _hide(window)


def _live_save_geometry_blob(home: Path) -> bytes:
    """Bytes from QWidget.saveGeometry. The app no longer writes this format."""
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        window.win.resize(700, 500)
        window.win.move(20, 16)
        window.QtWidgets.QApplication.processEvents()
        return bytes(window.win.saveGeometry())
    finally:
        _hide(window)


def _write_old_blob(home: Path, blob: bytes) -> None:
    text = json.dumps({"geometry": base64.b64encode(blob).decode("ascii")}) + "\n"
    (home / WINDOW_GEOMETRY_FILE).write_text(text, encoding="utf-8")


def _flip_old_blob(blob: bytes, *, byte: int | None = None, bit: int | None = None) -> bytes:
    data = bytearray(blob)
    if byte is not None:
        assert len(data) > byte
        data[byte] = 0xFF
    if bit is not None:
        assert len(data) * 8 > bit
        data[bit // 8] ^= 0x80 >> (bit % 8)
    return bytes(data)


@pytest.mark.parametrize(
    ("byte", "bit"),
    [(54, None), (None, 470)],
    ids=["byte-54", "bit-470"],
)
def test_corrupt_old_blob_opens_at_the_default_size(tmp_path: Path, byte, bit) -> None:
    home = tmp_path / "home"
    blob = _flip_old_blob(_live_save_geometry_blob(home), byte=byte, bit=bit)
    _write_old_blob(home, blob)
    window = MainWindow(home=home, autoload=False)
    try:
        _assert_default_size(window)
    finally:
        _hide(window)


def test_old_blob_is_rewritten_as_a_record_on_quit(tmp_path: Path) -> None:
    home = tmp_path / "home"
    blob = _live_save_geometry_blob(home)
    _write_old_blob(home, blob)
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        window.quit()
    finally:
        _hide(window)
    record = _saved_record(home)
    assert record["version"] == _GEOMETRY_VERSION
    assert "geometry" not in record
    assert _window_record(record) is not None


def test_partial_geometry_restore_keeps_the_default_size(tmp_path: Path, monkeypatch) -> None:
    """A restore that resizes and then raises still leaves the default size."""
    home = tmp_path / "home"
    first = MainWindow(home=home, autoload=False)
    try:
        first.win.show()
        first.QtWidgets.QApplication.processEvents()
        first.win.resize(700, 500)
        first.win.move(20, 16)
        first.QtWidgets.QApplication.processEvents()
        first.quit()
    finally:
        _hide(first)

    orig = MainWindow._apply_window_record

    def boom(self, *args):
        orig(self, *args)
        self.win.resize(400, 300)
        self.win.move(30, 30)
        raise RuntimeError("geometry apply stopped")

    monkeypatch.setattr(MainWindow, "_apply_window_record", boom)
    window = MainWindow(home=home, autoload=False)
    try:
        _assert_default_size(window)
        assert window.win.width() != 400
        log = (home / "logs" / "sync-ui.log").read_text(encoding="utf-8")
        assert log.count("window geometry") == 1
        assert "RuntimeError" in log
    finally:
        _hide(window)


_GEOM_DRIVER = r'''
import os
import sys

from PyQt5 import QtCore

import leasegrid_sync.app as appmod

_orig_show = appmod.MainWindow.show


def show(self):
    # Size before show() still has whatever restore did. The guard inside show()
    # must not be the only thing hiding an old blob that restoreGeometry inflated.
    sys.stdout.write("BEFORE_SHOW %d %d\n" % (self.win.width(), self.win.height()))
    sys.stdout.flush()
    _orig_show(self)
    sys.stdout.write("WINDOW_SHOWN %d %d\n" % (self.win.width(), self.win.height()))
    sys.stdout.flush()
    sentinel = os.environ.get("LEASEGRID_TEST_CLOSE_FILE", "")
    if not sentinel:
        return

    def poll():
        if os.path.exists(sentinel):
            self.win.close()
        else:
            QtCore.QTimer.singleShot(50, poll)

    QtCore.QTimer.singleShot(50, poll)


appmod.MainWindow.show = show

from leasegrid_sync.cli import main

rc = main(sys.argv[1:])
sys.stdout.write("EXIT:%s\n" % rc)
sys.stdout.flush()
raise SystemExit(0 if rc is None else int(rc))
'''


def _launch_real_app(tmp_path: Path, home: Path) -> tuple[int, str, str]:
    driver = tmp_path / "driver.py"
    driver.write_text(_GEOM_DRIVER, encoding="utf-8")
    close_file = tmp_path / "close-now"
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["LEASEGRID_TEST_CLOSE_FILE"] = str(close_file)
    nodedir = tmp_path / "no-tahoe"
    proc = subprocess.Popen(
        [sys.executable, str(driver), "--offscreen", "--nodedir", str(nodedir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    out_lines: list[str] = []
    err_lines: list[str] = []

    def read_out() -> None:
        stdout = proc.stdout
        if stdout is None:
            return
        for line in stdout:
            out_lines.append(line)

    def read_err() -> None:
        stderr = proc.stderr
        if stderr is None:
            return
        for line in stderr:
            err_lines.append(line)

    threading.Thread(target=read_out, daemon=True).start()
    threading.Thread(target=read_err, daemon=True).start()
    deadline = time.time() + 30
    try:
        while time.time() < deadline and not any("WINDOW_SHOWN" in line for line in out_lines):
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        shown = "".join(out_lines)
        errors = "".join(err_lines)
        if "WINDOW_SHOWN" in shown:
            close_file.write_text("quit", encoding="utf-8")
            code = proc.wait(timeout=20)
        else:
            code = proc.wait(timeout=20) if proc.poll() is None else proc.returncode
            if code is None:
                code = proc.wait(timeout=5)
        return code if code is not None else 1, shown, errors
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_corrupt_old_blob_launches_the_real_app(tmp_path: Path) -> None:
    home = tmp_path / "home"
    blob = _flip_old_blob(_live_save_geometry_blob(home), byte=54)
    _write_old_blob(home, blob)
    code, shown, errors = _launch_real_app(tmp_path, home)
    assert "WINDOW_SHOWN" in shown, "%s %s" % (shown, errors)
    assert "BEFORE_SHOW" in shown, "%s %s" % (shown, errors)
    assert "Traceback" not in errors
    assert "OverflowError" not in errors
    before = shown.split("BEFORE_SHOW", 1)[1].split()
    after = shown.split("WINDOW_SHOWN", 1)[1].split()
    before_w, before_h = int(before[0]), int(before[1])
    width, height = int(after[0]), int(after[1])
    # A flipped v3 rect is 16,777,215 px. The default window is not.
    assert before_w < 10000 and before_h < 10000
    assert width == DEFAULT_WINDOW_SIZE[0]
    assert height < 10000
    assert code == 0
