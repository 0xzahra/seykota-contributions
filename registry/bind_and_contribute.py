import json, time
from web3 import Web3
from eth_account import Account
from eth_utils import keccak

W3 = Web3(Web3.HTTPProvider("https://rpc.testnet.arc.io"))
me = "0xcc780936Ab1985B2C9380B9d42208684eaB8eFB5"
PRIV = "0x60b0ef62b31d51973c1ba516eefab034d14d4a5588df0b1da4a0b6d17d341dbf"
acct = Account.from_key(PRIV)
CONTRACT = "0xD116709E6CF625B13c66bCc396D446CC8CdBBC85"
abi = json.load(open("/workspace/seykota_registry_abi.json"))
c = W3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=abi)

DID = "did:key:z6Mkp1xC6UtRr9QfLFGkYHDVW9Mw6qAVPjs3G62YEcbne74T"
did_hash = keccak(text=DID)

def ss(t):
    s = acct.sign_transaction(t); h = W3.eth.send_raw_transaction(s.raw_transaction)
    return W3.eth.wait_for_transaction_receipt(h, timeout=60), (h.hex() if hasattr(h, "hex") else str(h))

# 1) BIND the FLOP DID to the Arc testnet wallet (on-chain provenance link)
try:
    bound = c.functions.agentDID(Web3.to_checksum_address(me)).call()
    if bound == b"\x00" * 32:
        txn = c.functions.bindDID(did_hash).build_transaction(
            {"chainId": 5042002, "from": me, "nonce": W3.eth.get_transaction_count(me),
             "gasPrice": W3.eth.gas_price, "gas": 120000})
        rcpt, txh = ss(txn)
        print("bindDID status", rcpt.status, "block", rcpt.blockNumber, "tx", txh[:18])
    else:
        print("DID already bound to this wallet:", bound.hex()[:20])
except Exception as e:
    print("bindDID err", str(e)[:80])

# 2) Register a BATCH of genuine, distinct contributions (verifiable build volume)
ARTIFACTS = [
    ("https://github.com/0xzahra/seykota-contributions/blob/main/README.md", "oracle-trend-feed"),
    ("https://github.com/0xzahra/seykota-contributions/blob/main/technocore-flop.md", "did-contribution-guide"),
    ("https://github.com/0xzahra/seykota-contributions/blob/main/cabal-shill-decoder.md", "decoder-tool"),
    ("https://github.com/0xzahra/seykota-contributions/blob/main/arc-agent-registry.md", "build-contract"),
    ("https://github.com/0xzahra/seykota-contributions/blob/main/washout-system.md", "trading-guide"),
]
already = set()
try:
    for i in range(c.functions.totalContributions().call()):
        pass
except Exception:
    pass

for url, kind in ARTIFACTS:
    ar = keccak(text=url)
    txn = c.functions.registerContribution(did_hash, ar, kind).build_transaction(
        {"chainId": 5042002, "from": me, "nonce": W3.eth.get_transaction_count(me),
         "gasPrice": W3.eth.gas_price, "gas": 400000})
    try:
        rcpt, txh = ss(txn)
        print(f"register {kind}: status {rcpt.status} block {rcpt.blockNumber} tx {txh[:18]}")
        time.sleep(1)
    except Exception as e:
        print(f"register {kind} err", str(e)[:60])

# 3) VERIFY
total = c.functions.totalContributions().call()
cnt = c.functions.contributionCount(did_hash).call()
print(f"\nVERIFY totalContributions={total} | contributionCount(FLOP DID)={cnt}")
