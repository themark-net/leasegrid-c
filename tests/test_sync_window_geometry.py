"""Window size and position survive a quit, and a bad file does not."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

PyQt5 = pytest.importorskip("PyQt5")

from leasegrid_sync.app import MainWindow  # noqa: E402


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
    saved_width = _save_moved(home, 40, -650, 700, 700)
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
    saved_width = _save_moved(home, -200, 40, 500, 400)
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
