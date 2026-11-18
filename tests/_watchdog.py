"""Per-test timeout without a Python thread, for Windows (#90).

pytest-timeout has no signal method on Windows, so it starts a Python timer
thread per test. A garbage collection in that thread can free Qt objects off
the GUI thread (access violation in CI 44253243874). On Windows, or when
LEASEGRID_TEST_WATCHDOG=faulthandler, this plugin unregisters pytest-timeout
and arms faulthandler's C watchdog instead: on expiry it dumps every thread's
stack and exits, so CI still fails fast. Limits come from the same
`timeout` ini value and @pytest.mark.timeout(N) markers.
"""

from __future__ import annotations

import faulthandler
import os
import sys

import pytest


def _wanted() -> bool:
    mode = os.environ.get("LEASEGRID_TEST_WATCHDOG", "").strip().lower()
    if mode:
        return mode == "faulthandler"
    return sys.platform == "win32"


def _limit(item) -> float:
    marker = item.get_closest_marker("timeout")
    if marker is not None and marker.args:
        return float(marker.args[0])
    try:
        return float(item.config.getini("timeout") or 0)
    except (TypeError, ValueError):
        return 0.0


def _stderr_fd(config) -> int:
    try:
        from _pytest.faulthandler import fault_handler_stderr_fd_key

        return config.stash[fault_handler_stderr_fd_key]
    except Exception:
        return sys.__stderr__.fileno()


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    config._leasegrid_watchdog = _wanted()
    if config._leasegrid_watchdog:
        plugin = config.pluginmanager.get_plugin("timeout")
        if plugin is not None:
            config.pluginmanager.unregister(plugin)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    limit = _limit(item) if getattr(item.config, "_leasegrid_watchdog", False) else 0.0
    if limit > 0:
        out = os.fdopen(os.dup(_stderr_fd(item.config)), "w")
        faulthandler.dump_traceback_later(limit, exit=True, file=out)
    try:
        yield
    finally:
        if limit > 0:
            faulthandler.cancel_dump_traceback_later()
            out.close()
