"""Mutants for this run. `scripts/prove-red.py` restores every target."""

CASES = [
    (
        "skill-ss3-section",
        ".grok/skills/systems-safety/SKILL.md",
        "## SS3 IPC\n",
        "",
        ["tests/test_systems_rules_doc.py::test_semgrep_ids_are_in_agents_and_the_skill"],
    ),
]
