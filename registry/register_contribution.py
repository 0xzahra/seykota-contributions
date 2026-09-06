import json
from web3 import Web3
from eth_account import Account
from eth_utils import keccak

W3 = Web3(Web3.HTTPProvider("https://rpc.testnet.arc.io"))
me = "0xcc780936Ab1985B2C9380B9d42208684eaB8eFB5"
PRIV = "0x60b0ef62b31d51973c1ba516eefab034d14d4a5588df0b1da4a0b6d17d341dbf"
acct = Account.from_key(PRIV)
CONTRACT = "0xD116709E6CF625B13c66bCc396D446CC8CdBBC85"
abi = json.load(open("/workspace/seykota_registry_abi.json"))

DID = "did:key:z6Mkp1xC6UtRr9QfLFGkYHDVW9Mw6qAVPjs3G62YEcbne74T"
ARTIFACT = "https://github.com/0xzahra/seykota-contributions/blob/main/README.md"
c = W3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=abi)

def ss(t):
    s = acct.sign_transaction(t); h = W3.eth.send_raw_transaction(s.raw_transaction)
    return W3.eth.wait_for_transaction_receipt(h, timeout=60), (h.hex() if hasattr(h, "hex") else str(h))

did_hash = keccak(text=DID)
art_hash = keccak(text=ARTIFACT)

# register the contribution
txn = c.functions.registerContribution(did_hash, art_hash, "oracle-trend-feed").build_transaction(
    {"chainId": 5042002, "from": me, "nonce": W3.eth.get_transaction_count(me), "gasPrice": W3.eth.gas_price, "gas": 200000})
rcpt, txh = ss(txn)
print("registerContribution status", rcpt.status, "block", rcpt.blockNumber, "tx", txh[:18])

# verify reads
total = c.functions.totalContributions().call()
cnt = c.functions.contributionCount(did_hash).call()
print("VERIFY totalContributions =", total)
print("VERIFY contributionCount(our DID) =", cnt)
