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

# Gate 0c: XMR → vid. 1 XMR = 1e12 piconero.
XMR_PICONERO = 10**12
# Lab rate (not a market price): 0.001 XMR per token.
PICONERO_PER_TOKEN = 10**9
VID_LEN = 8
QUOTE_TTL_SECONDS = 3600
DEFAULT_QUOTE_TOKENS = 2
CONFIRMATIONS_REQUIRED_SIMULATED = 1
CONFIRMATIONS_REQUIRED_CHAIN = 10
# nimo mainnet monerod. Never connect. See GATE0C_NETWORK_CONSTRAINT.md.
BANNED_XMR_RPC_PORTS = frozenset({18081, 18083})
ALLOWED_XMR_NETWORKS = frozenset({"stagenet", "testnet", "fakechain", "regtest"})
DEFAULT_XMR_NETWORK = "stagenet"
