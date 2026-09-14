#!/usr/bin/env python3
"""Live end-to-end demo of AgentLaunchpad on Arc testnet.

Proves the whole launchpad flow on-chain:
  faucet -> registerAgent -> launchToken -> quote -> buy -> sell
Every state-changing call is verified to land with status=1 and the on-chain
state is read back afterwards (no claims without receipts).
"""
import json, os
from web3 import Web3
from eth_account import Account

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://rpc.testnet.arc.io"
CHAIN = 5042002
DEP = json.load(open(os.path.join(HERE, "deployment.json")))
PAD = DEP["AgentLaunchpad"]["address"]
USD = DEP["LaunchUSD"]["address"]


def load_key() -> str:
    env = os.environ.get("ARC_PRIVATE_KEY")
    if env:
        return env if env.startswith("0x") else "0x" + env
    for line in open(os.path.join(HERE, ".env")):
        line = line.strip()
        if line and not line.startswith("#"):
            return line if line.startswith("0x") else "0x" + line
    raise SystemExit("no key")


w3 = Web3(Web3.HTTPProvider(RPC))
acct = Account.from_key(load_key())
me = acct.address
print(f"chain {w3.eth.chain_id} | account {me} | nonce {w3.eth.get_transaction_count(me)}")

pad = w3.eth.contract(address=Web3.to_checksum_address(PAD), abi=DEP["AgentLaunchpad"]["abi"])
usd = w3.eth.contract(address=Web3.to_checksum_address(USD), abi=DEP["LaunchUSD"]["abi"])

# Arc USDC is 6-decimal via the ERC-20 interface; our LaunchUSD is 6 decimals.
def call(tx, label, expect=1):
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    rc = w3.eth.wait_for_transaction_receipt(h, timeout=120)
    ok = (rc.status == expect)
    print(f"  {label:<34} tx={h.hex()[:16]}.. status={rc.status} block={rc.blockNumber} "
          f"{'✅' if ok else '❌ ' + str(rc)}")
    assert ok, f"{label} failed"
    return rc


# 0. test liquidity
print("\n[0] faucet quote (lUSD)")
amt = 1000 * 10**6
call(usd.functions.faucet(amt).build_transaction({
    "chainId": CHAIN, "from": me, "nonce": w3.eth.get_transaction_count(me),
    "gasPrice": w3.eth.gas_price, "gas": 150000}), "faucet 1000 lUSD")
print(f"  lUSD balance = {usd.functions.balanceOf(me).call()/1e6}")

# 1. register the agent identity (skip if already registered — re-runnable)
print("\n[1] registerAgent (Seykota / ArewaOS DID)")
DID = "did:key:z6Mkp1xC6UtRr9QfLFGkYHDVW9Mw6qAVPjs3G62YEcbne74T"
did_hash = Web3.keccak(text=DID)
if not pad.functions.getAgent(me).call()[5]:
    call(pad.functions.registerAgent(did_hash, "Seykota / ArewaOS Agent",
         "ipfs://arewaos-agent-card").build_transaction({
        "chainId": CHAIN, "from": me, "nonce": w3.eth.get_transaction_count(me),
        "gasPrice": w3.eth.gas_price, "gas": 300000}), "registerAgent")
else:
    print("  already registered, skipping")
agent = pad.functions.getAgent(me).call()
print(f"  got name={agent[1]!r} launched={agent[3]} exists={agent[5]}")

# 2. launch a token on the curve (only if there is no launch yet — re-runnable)
print("\n[2] launchToken TREND (1M supply, 100k on curve)")
base = 100_000   # 0.10 lUSD / token
slope = 10       # +0.00001 lUSD per token sold
if pad.functions.totalLaunches().call() == 0:
    call(pad.functions.launchToken("TREND", "TREND", 1_000_000, 100_000, base, slope).build_transaction({
        "chainId": CHAIN, "from": me, "nonce": w3.eth.get_transaction_count(me),
        "gasPrice": w3.eth.gas_price, "gas": 3_000_000}), "launchToken")
else:
    print("  launch already exists, reusing id 0")

n_l = pad.functions.totalLaunches().call()
print(f"  totalLaunches = {n_l}")
LAUNCH_ID = n_l - 1
L = pad.functions.getLaunch(LAUNCH_ID).call()
TOKEN_ADDR = L.token if hasattr(L, "token") else L[1]
tok = w3.eth.contract(address=Web3.to_checksum_address(TOKEN_ADDR), abi=DEP["AgentToken"]["abi"])
NO = lambda L, field, idx: getattr(L, field, L[idx])
print(f"  token={TOKEN_ADDR} creator={NO(L,'creator',2)} sold={NO(L,'sold',8)} spotPrice={pad.functions.spotPrice(LAUNCH_ID).call()/1e6} lUSD")
print(f"  creator allocation (900k TREND) = {tok.functions.balanceOf(me).call()/1e18}")

# 3. quote + approve + buy
print("\n[3] buy 1000 TREND off the curve")
cost, fee, total = pad.functions.quoteBuy(LAUNCH_ID, 1000).call()
print(f"  quoteBuy(1000) cost={cost/1e6:.4f} lUSD fee={fee/1e6:.4f} total={total/1e6:.4f} lUSD")
call(usd.functions.approve(PAD, total).build_transaction({
    "chainId": CHAIN, "from": me, "nonce": w3.eth.get_transaction_count(me),
    "gasPrice": w3.eth.gas_price, "gas": 200000}), "approve pad")
call(pad.functions.buy(LAUNCH_ID, 1000).build_transaction({
    "chainId": CHAIN, "from": me, "nonce": w3.eth.get_transaction_count(me),
    "gasPrice": w3.eth.gas_price, "gas": 500000}), "buy 1000 TREND")
L = pad.functions.getLaunch(LAUNCH_ID).call()
print(f"  after buy: sold={NO(L,'sold',8)} reserve={NO(L,'reserve',9)/1e6:.4f} raised={NO(L,'raised',12)/1e6:.4f} "
      f"spotPrice={pad.functions.spotPrice(LAUNCH_ID).call()/1e6:.6f} lUSD")
print(f"  TREND held by buyer = {tok.functions.balanceOf(me).call()/1e18}")

# 4. quote + sell some back
print("\n[4] sell 400 TREND back to the curve")
rf, srfee, net = pad.functions.quoteSell(LAUNCH_ID, 400).call()
print(f"  quoteSell(400) refund={rf/1e6:.4f} lUSD fee={srfee/1e6:.4f} net={net/1e6:.4f} lUSD")
call(pad.functions.sell(LAUNCH_ID, 400).build_transaction({
    "chainId": CHAIN, "from": me, "nonce": w3.eth.get_transaction_count(me),
    "gasPrice": w3.eth.gas_price, "gas": 500000}), "sell 400 TREND")
L = pad.functions.getLaunch(LAUNCH_ID).call()
print(f"  after sell: sold={NO(L,'sold',8)} reserve={NO(L,'reserve',9)/1e6:.4f} TREND held={tok.functions.balanceOf(me).call()/1e18}")

print("\nVerification of on-chain provenance:")
print(f"  totalAgents={pad.functions.totalAgents().call()} totalLaunches={pad.functions.totalLaunches().call()}")
print(f"  agentLaunchCount(me)={pad.functions.agentLaunchCount(me).call()} "
      f"launchIdAt(0)={pad.functions.agentLaunchIdAt(me, 0).call()}")
print(f"  launchOfToken(token)={pad.functions.launchOfToken(TOKEN_ADDR).call()}  (id+1)")
print(f"  impliedMarketCap={pad.functions.impliedMarketCap(LAUNCH_ID).call()/1e6:.4f} lUSD")
print("\nDONE — launchpad proven end-to-end on Arc testnet.")
