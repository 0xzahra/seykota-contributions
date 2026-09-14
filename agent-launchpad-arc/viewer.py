#!/usr/bin/env python3
"""Read-only explorer for the AgentLaunchpad on Arc testnet.

Prints the live on-chain state: every registered agent and every launched token
with the current curve position (sold / reserve / spot / raised / graduation).
Pure eth_call — no signing, no gas, read-only.
"""
import json, os
from web3 import Web3

HERE = os.path.dirname(os.path.abspath(__file__))
DEP = json.load(open(os.path.join(HERE, "deployment.json")))
w3 = Web3(Web3.HTTPProvider(DEP["rpc"]))

def norm(addr):
    return Web3.to_checksum_address(addr)

pad = w3.eth.contract(address=norm(DEP["AgentLaunchpad"]["address"]), abi=DEP["AgentLaunchpad"]["abi"])
TAB = 18

def fmt_usd(x):
    return f"{x/1e6:,.4f}"

print(f"AgentLaunchpad  {DEP['AgentLaunchpad']['address']}")
print(f"quote (lUSD)    {DEP['LaunchUSD']['address']}")
print(f"chain           {DEP['chainId']}  ({DEP['deployedAt']})\n")

nA = pad.functions.totalAgents().call()
nL = pad.functions.totalLaunches().call()
print(f"agents={nA}   launches={nL}\n")

print("── AGENTS ─────────────────────────────────")
for i in range(nA):
    who = pad.functions.agentAt(i).call()
    a = pad.functions.getAgent(who).call()
    did = Web3.to_hex(a[0])
    print(f"[{i}] {who}")
    print(f"    name={a[1]!r}  launched={a[3]}  did={did}  uri={a[2]!r}")

print("\n── LAUNCHES ───────────────────────────────")
for i in range(nL):
    L = pad.functions.getLaunch(i).call()
    symbol = L.symbol if hasattr(L, "symbol") else L[5]
    name = L.name if hasattr(L, "name") else L[4]
    creator = L.creator if hasattr(L, "creator") else L[2]
    sold = L.sold if hasattr(L, "sold") else L[8]
    cs = L.curveSupply if hasattr(L, "curveSupply") else L[7]
    rs = L.reserve if hasattr(L, "reserve") else L[9]
    raised = L.raised if hasattr(L, "raised") else L[12]
    grad = L.graduated if hasattr(L, "graduated") else L[13]
    spot = pad.functions.spotPrice(i).call()
    mcap = pad.functions.impliedMarketCap(i).call()
    print(f"[{i}] {symbol} — {name}")
    print(f"    token   {L.token if hasattr(L,'token') else (L[1] if len(L)>1 else '')}")
    print(f"    creator {creator}")
    print(f"    sold    {sold:,}/{cs:,}  ({100*sold//cs if cs else 0}% of curve)")
    print(f"    spot    {fmt_usd(spot)} lUSD   raised {fmt_usd(raised)}   reserve {fmt_usd(rs)}")
    print(f"    mcap    {fmt_usd(mcap)} lUSD   {'GRADUATED' if grad else 'on curve'}")
    cost, fee, total = pad.functions.quoteBuy(i, 100).call()
    print(f"    quoteBuy(100) = {fmt_usd(total)} lUSD (fee {fmt_usd(fee)})")
    print()
