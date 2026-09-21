"""v0 constants. Denomination and domain are architecture, not knobs."""

DOMAIN = "leasegrid-v0"
PLUGIN_NAME = "leasegrid-zkap-v0"
TOKEN_EPOCH_V0 = 0
DENOMINATION = "1 token = 1 GiB-share × 30 days on one node"
GIB = 2**30
DEFAULT_LEASE_SECONDS = 30 * 24 * 60 * 60
DEFAULT_SHARE_BYTES = GIB
DEFAULT_ISSUER_KEY = "~/DEVELOP/leasegrid-lab-private/issuer.signing.key"
DEFAULT_WALLET = "~/DEVELOP/leasegrid-lab-private/client-wallet.json"
DEFAULT_SPENT_SET = "~/DEVELOP/leasegrid-lab-private/storage-spent.json"
DEFAULT_EJECT_SET = "~/DEVELOP/leasegrid-lab-private/ejected.json"
