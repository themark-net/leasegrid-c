"""Mutants for this run. `scripts/prove-red.py` restores every target."""

CASES = [
    (
        "skill-ss3-section",
        ".grok/skills/systems-safety/SKILL.md",
        "## SS3 IPC\n",
        "",
        ["tests/test_systems_rules_doc.py::test_semgrep_ids_are_in_agents_and_the_skill"],
    ),
    (
        "r9n-zombie-as-running",
        "src/leasegrid_sync/backend.py",
        '    if info is None:\n        return "running"\n    return "exited"\n',
        '    if info is None:\n        return "running"\n    return "running"\n',
        ["tests/test_sync_backend.py::test_start_respawns_an_unreaped_exited_leader"],
    ),
    (
        "n1i-yes-joins",
        "src/leasegrid_sync/app.py",
        "            if pending:\n"
        "                self.invite_edit.setText(pending)\n"
        "                self.invite_edit.setFocus()\n"
        "        self._dump_handed_invite()\n",
        "            if pending:\n"
        "                self.invite_edit.setText(pending)\n"
        "                self.invite_edit.setFocus()\n"
        "                self.on_join_invite()\n"
        "        self._dump_handed_invite()\n",
        ["tests/test_sync_handed_invite.py::test_yes_on_handed_replace_does_not_start_a_join"],
    ),
    (
        "l5n-drop-second-trylock",
        "src/leasegrid_sync/app.py",
        "        if _lock_pid_readable(lock):\n"
        "            return False\n"
        "        if not lock.tryLock(0):\n"
        "            return False\n",
        "        if _lock_pid_readable(lock):\n"
        "            return False\n"
        "        return False\n",
        ["tests/test_sync_instance_lock.py::test_second_trylock_takes_the_lock_after_the_writer_grace"],
    ),
    (
        "latest-wins-keep-pending",
        "src/leasegrid_sync/app.py",
        "        if current == text:\n"
        "            # The latest hand is the text already in the field. Drop an older\n"
        "            # pending replacement so a later Yes cannot apply it.\n"
        "            self._dismiss_handed_replace_box()\n"
        "            self._dump_handed_invite()\n"
        "            return\n",
        "        if current == text:\n"
        "            # The latest hand is the text already in the field. Drop an older\n"
        "            # pending replacement so a later Yes cannot apply it.\n"
        "            self._dump_handed_invite()\n"
        "            return\n",
        ["tests/test_sync_handed_invite.py::test_rehanding_the_current_invite_drops_the_older_pending"],
    ),
    (
        "sigterm-no-handler",
        "src/leasegrid_sync/app.py",
        "    _arm_already_running_dismiss(QtCore, QtWidgets)\n"
        "    _arm_already_running_shown(QtCore, QtWidgets)\n"
        "    _arm_already_running_signal_quit(app, QtCore, QtWidgets)\n",
        "    _arm_already_running_dismiss(QtCore, QtWidgets)\n"
        "    _arm_already_running_shown(QtCore, QtWidgets)\n",
        [
            "tests/test_sync_already_running.py::test_already_running_second_launch_exits_0_on_sigterm"
        ],
    ),
]
