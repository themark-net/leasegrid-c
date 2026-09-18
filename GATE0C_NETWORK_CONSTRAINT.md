# HARD CONSTRAINT for Gate 0c

Do **NOT** use the existing monerod on nimo if it is **mainnet** (typical RPC :18081 / ZMQ :18083).

Gate 0c allows only:
- Monero **stagenet**, or
- local **regtest / private / dev** chain

Never mainnet. Never ask for Mark credentials. Put all wallet/view keys under `~/DEVELOP/leasegrid-lab-private/` only.
