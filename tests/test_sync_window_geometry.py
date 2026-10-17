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
    _GEOM_HEADER,
    _GEOM_RECT,
    MainWindow,
    _saved_frame,
)


def _hide(window: MainWindow) -> None:
    window.poll.stop()
    window.win.hide()
    if window.tray is not None:
        window.tray.hide()


def test_geometry_round_trips_across_two_windows(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = MainWindow(home=home, autoload=False)
    try:
        first.win.show()
        first.QtWidgets.QApplication.processEvents()
        # Taller than the layout's minimum, and still touching the offscreen desktop.
        first.win.resize(1000, 980)
        first.win.move(15, 10)
        first.QtWidgets.QApplication.processEvents()
        assert (first.win.width(), first.win.height(), first.win.x(), first.win.y()) == (1000, 980, 15, 10)
        first.quit()
    finally:
        _hide(first)

    second = MainWindow(home=home, autoload=False)
    try:
        second.show()
        second.QtWidgets.QApplication.processEvents()
        assert (second.win.width(), second.win.height(), second.win.x(), second.win.y()) == (1000, 980, 15, 10)
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
    # 1000 is above the 920 default and the 863 px windows-2022 minimum.
    saved_width = _save_moved(home, 40, -650, 1000, 700)
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
    saved_width = _save_moved(home, -200, 40, 1000, 400)
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
    saved_width = _save_moved(home, -40, 40, 1000, 500)
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
    (home / "window-geometry.json").write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
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
        window.win.resize(1000, 980)
        window.win.move(15, 10)
        window._save_window_geometry()
        path = home / "window-geometry.json"
        good = path.read_bytes()

        def fail_replace(*_args, **_kwargs):
            raise OSError("replace failed")

        monkeypatch.setattr(os, "replace", fail_replace)
        window.win.resize(700, 500)
        window._save_window_geometry()
        assert path.read_bytes() == good
        assert not (home / "window-geometry.json.tmp").exists()
    finally:
        _hide(window)


def test_corrupt_geometry_file_uses_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "window-geometry.json").write_text("{", encoding="utf-8")
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())
    finally:
        _hide(window)


def _read_geometry_blob(home: Path) -> bytes:
    raw = json.loads((home / "window-geometry.json").read_text(encoding="utf-8"))
    return base64.b64decode(raw["geometry"])


def _write_geometry_blob(home: Path, blob: bytes) -> None:
    text = json.dumps({"geometry": base64.b64encode(blob).decode("ascii")}) + "\n"
    (home / "window-geometry.json").write_text(text, encoding="utf-8")


def _save_live_geometry(home: Path) -> bytes:
    """A real MainWindow writes the blob. The next launch is what we corrupt."""
    window = MainWindow(home=home, autoload=False)
    try:
        window.win.show()
        window.QtWidgets.QApplication.processEvents()
        window.win.resize(1000, 700)
        window.win.move(20, 16)
        window.QtWidgets.QApplication.processEvents()
        window._save_window_geometry()
    finally:
        _hide(window)
    return _read_geometry_blob(home)


def _flip_frame_left_sign(blob: bytes) -> bytes:
    """Flip the sign bit of frame-left in the layout `_saved_frame` reads."""
    data = bytearray(blob)
    at = _GEOM_HEADER.size
    left, top, right, bottom = _GEOM_RECT.unpack_from(data, at)
    flipped = (left & 0xFFFFFFFF) ^ 0x80000000
    if flipped >= 0x80000000:
        flipped -= 0x100000000
    _GEOM_RECT.pack_into(data, at, flipped, top, right, bottom)
    return bytes(data)


def _with_frame(blob: bytes, left: int, top: int, right: int, bottom: int) -> bytes:
    data = bytearray(blob)
    _GEOM_RECT.pack_into(data, _GEOM_HEADER.size, left, top, right, bottom)
    return bytes(data)


def _assert_default_size(window: MainWindow) -> None:
    window.win.show()
    window.QtWidgets.QApplication.processEvents()
    assert (window.win.width(), window.win.height()) == (920, window.win.minimumHeight())


def test_saved_frame_rejects_a_sign_flipped_left(tmp_path: Path) -> None:
    home = tmp_path / "home"
    blob = _flip_frame_left_sign(_save_live_geometry(home))
    assert _saved_frame(blob) is None


def test_sign_flipped_frame_opens_at_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    blob = _flip_frame_left_sign(_save_live_geometry(home))
    _write_geometry_blob(home, blob)
    window = MainWindow(home=home, autoload=False)
    try:
        _assert_default_size(window)
    finally:
        _hide(window)


def test_max_int_frame_opens_at_the_default_size(tmp_path: Path) -> None:
    home = tmp_path / "home"
    blob = _with_frame(_save_live_geometry(home), 0, 0, 2**31 - 1, 2**31 - 1)
    assert _saved_frame(blob) is None
    _write_geometry_blob(home, blob)
    window = MainWindow(home=home, autoload=False)
    try:
        _assert_default_size(window)
    finally:
        _hide(window)


def test_partial_geometry_restore_keeps_the_default_size(tmp_path: Path, monkeypatch) -> None:
    """A restore that resizes and then raises still leaves the default size."""
    home = tmp_path / "home"
    _save_live_geometry(home)

    def boom(self, _blob):
        self.resize(400, 300)
        self.move(30, 30)
        raise RuntimeError("geometry apply stopped")

    monkeypatch.setattr("PyQt5.QtWidgets.QMainWindow.restoreGeometry", boom)
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


def test_sign_flipped_geometry_launches_the_real_app(tmp_path: Path) -> None:
    home = tmp_path / "home"
    nodedir = tmp_path / "no-tahoe"
    blob = _flip_frame_left_sign(_save_live_geometry(home))
    _write_geometry_blob(home, blob)
    driver = tmp_path / "driver.py"
    driver.write_text(_GEOM_DRIVER, encoding="utf-8")
    close_file = tmp_path / "close-now"
    env = os.environ.copy()
    env["LEASEGRID_SYNC_HOME"] = str(home)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["LEASEGRID_TEST_CLOSE_FILE"] = str(close_file)
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
        assert "WINDOW_SHOWN" in shown, "%s %s" % (shown, errors)
        assert "OverflowError" not in errors
        assert "Traceback" not in errors
        width = int(shown.split("WINDOW_SHOWN", 1)[1].split()[0])
        assert width == DEFAULT_WINDOW_SIZE[0]
        close_file.write_text("quit", encoding="utf-8")
        assert proc.wait(timeout=20) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
