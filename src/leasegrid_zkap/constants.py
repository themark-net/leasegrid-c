"""v0 constants. Denomination and domain are architecture, not knobs."""

import os

DOMAIN = "leasegrid-v0"
PLUGIN_NAME = "leasegrid-zkap-v0"
TOKEN_EPOCH_V0 = 0
DENOMINATION = "1 token = 1 GiB-share × 30 days on one node"
GIB = 2**30
DEFAULT_LEASE_SECONDS = 30 * 24 * 60 * 60
DEFAULT_SHARE_BYTES = GIB
# Lab secrets stay off git. LEASEGRID_LAB_DIR picks the directory; callers expanduser.
LAB_DIR = (os.environ.get("LEASEGRID_LAB_DIR") or "").strip() or "~/leasegrid-lab-private"
DEFAULT_ISSUER_KEY = LAB_DIR + "/issuer.signing.key"
DEFAULT_WALLET = LAB_DIR + "/client-wallet.json"
DEFAULT_SPENT_SET = LAB_DIR + "/storage-spent.json"
DEFAULT_EJECT_SET = LAB_DIR + "/ejected.json"
