"""Android invite copy asks for the join link, not a raw furl (#50).

Option 1 is copy only. The parser still names a pb:// furl in code.
A user string must not.
"""

from __future__ import annotations

import re
from pathlib import Path

INVITE = (
    Path(__file__).resolve().parents[1]
    / "android/app/src/main/java/net/themark/leasegrid/sync/invite/Invite.kt"
)

# Exact tokens the parser still uses. Any other literal that names them is copy.
_CODE_OK = frozenset({"pb://", "furl"})
_LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')
_FORBIDDEN = re.compile(r"pb://|furl", re.IGNORECASE)


def test_invite_kt_user_strings_do_not_name_a_furl():
    text = INVITE.read_text(encoding="utf-8")
    literals = _LITERAL.findall(text)
    assert any("join link" in item for item in literals)
    assert 'startsWith("pb://")' in text
    hits = [item for item in literals if item not in _CODE_OK and _FORBIDDEN.search(item)]
    assert not hits
    assert "This phone does not take a short code." in text
    assert "That join link is malformed." in text
    assert "get a fresh full join link from your inviter; check network; Retry." in text
