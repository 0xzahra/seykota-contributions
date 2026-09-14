#!/usr/bin/env python3
"""Deploy the AgentLaunchpad stack to Arc testnet (chain 5042002).

Deploys:
  1. LaunchUSD  — 6-decimal test quote asset for the bonding curve (faucet-able)
  2. AgentLaunchpad(quote) — the pad itself

Writes deployment.json (addresses + ABIs) for the viewer / frontend.
Gas is paid in Arc testnet USDC. The private key is NEVER printed.
"""
import json, os, sys
import solcx
from web3 import Web3
from eth_account import Account

HERE = os.path.dirname(os.path.abspath(__file__))
RPC = "https://rpc.testnet.arc.io"
CHAIN = 5042002


def load_key() -> str:
    env = os.environ.get("ARC_PRIVATE_KEY")
    if env:
        return env if env.startswith("0x") else "0x" + env
    for p in (os.path.join(HERE, ".env"), "/workspace/.arc_key"):
        if os.path.exists(p):
            for line in open(p):
                line = line.strip()
                if line and not line.startswith("#"):
                    return line if line.startswith("0x") else "0x" + line
    raise SystemExit("no key: set ARC_PRIVATE_KEY or write .env")


def compile_contracts() -> dict:
    src = open(os.path.join(HERE, "contracts", "AgentLaunchpad.sol")).read()
    out = solcx.compile_source(
        src, output_values=["abi", "bin"], solc_version="0.8.20", optimize=True
    )
    return {k.split(":")[-1]: v for k, v in out.items()}


def deploy(w3, acct, abi, bytecode, *args, gas=6_000_000):
    C = w3.eth.contract(abi=abi, bytecode="0x" + bytecode)
    txn = C.constructor(*args).build_transaction({
        "chainId": CHAIN, "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gasPrice": w3.eth.gas_price, "gas": gas,
    })
    signed = acct.sign_transaction(txn)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    rc = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    print(f"  tx {h.hex()} status={rc.status} block={rc.blockNumber} gasUsed={rc.gasUsed}")
    if rc.status != 1:
        raise SystemExit("deploy reverted")
    return rc.contractAddress


def main():
    # make sure solc 0.8.20 is present
    try:
        solcx.set_solc_version("0.8.20")
    except Exception:
        solcx.install_solc("0.8.20")
        solcx.set_solc_version("0.8.20")

    w3 = Web3(Web3.HTTPProvider(RPC))
    assert w3.is_connected(), "cannot reach Arc RPC"
    acct = Account.from_key(load_key())
    bal = w3.from_wei(w3.eth.get_balance(acct.address), "ether")
    print(f"Arc testnet | chain {w3.eth.chain_id} | deployer {acct.address}")
    print(f"balance {bal} USDC | nonce {w3.eth.get_transaction_count(acct.address)} | gasPrice {w3.eth.gas_price}")

    c = compile_contracts()
    print("compiled:", ", ".join(f"{k}({len(v['bin'])//2}B)" for k, v in c.items() if v["bin"]))

    print("\n[1/2] deploying LaunchUSD (quote asset)...")
    usd_addr = deploy(w3, acct, c["LaunchUSD"]["abi"], c["LaunchUSD"]["bin"])

    print("[2/2] deploying AgentLaunchpad(quote=LaunchUSD)...")
    pad_addr = deploy(w3, acct, c["AgentLaunchpad"]["abi"], c["AgentLaunchpad"]["bin"], usd_addr)

    dep = {
        "chainId": CHAIN,
        "rpc": RPC,
        "explorer": "https://testnet.arcscan.app",
        "deployer": acct.address,
        "LaunchUSD": {"address": usd_addr, "abi": c["LaunchUSD"]["abi"]},
        "AgentLaunchpad": {"address": pad_addr, "abi": c["AgentLaunchpad"]["abi"]},
        "AgentToken": {"abi": c["AgentToken"]["abi"]},
        "deployedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    out = os.path.join(HERE, "deployment.json")
    json.dump(dep, open(out, "w"), indent=2)
    print(f"\nquote  LaunchUSD     = {usd_addr}")
    print(f"pad    AgentLaunchpad= {pad_addr}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
