#!/usr/bin/env python3
"""Arc testnet MULTI-ACTIVITY farmer (real signed txns, no cost). Builds a DIVERSE
footprint — token transfers (varied amounts/recipients) + oracle state write — so the
mainnet snapshot sees contract-call diversity, not one repeated transfer.

Snapshot rewards diversity (tokens + NFTs + state updates), per the airdrop skill.
Cost = testnet USDC gas (free). Safe to run heavily. Never prints the private key.
"""
from web3 import Web3
from eth_abi import encode
import time, sys

PRIV = "0x60b0ef62b31d51973c1ba516eefab034d14d4a5588df0b1da4a0b6d17d341dbf"
RPC = "https://rpc.testnet.arc.io"
CHAIN = 5042002
W3 = Web3(Web3.HTTPProvider(RPC))
acct = W3.eth.account.from_key(PRIV)
ME = acct.address

AREWA = "0xA9eD819e48124735011ea59EB71B58ba62ae45B0"
ORACLE = "0xADf0B89Bd55C3673aCB87738908BAda4f38730e1"
NFT = "0x4687F7D5B59c695bc88916FF063b16cAd6Bf0261"

ERC20 = [{"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"v","type":"uint256"}],
          "name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
         {"constant":True,"inputs":[{"name":"a","type":"address"}],"name":"balanceOf",
          "outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]

def sign_send(txn):
    signed = acct.sign_transaction(txn)
    txh = W3.eth.send_raw_transaction(signed.raw_transaction)
    rcpt = W3.eth.wait_for_transaction_receipt(txh, timeout=90)
    return txh.hex() if hasattr(txh, "hex") else txh, rcpt

def transfer_token(addr, to, amount_str, label):
    tok = W3.eth.contract(address=Web3.to_checksum_address(addr), abi=ERC20)
    amount = W3.to_wei(amount_str, "ether")
    txn = tok.functions.transfer(Web3.to_checksum_address(to), amount).build_transaction({
        "chainId": CHAIN, "from": ME, "nonce": W3.eth.get_transaction_count(ME),
        "gasPrice": W3.eth.gas_price, "gas": 250000})
    txh, rcpt = sign_send(txn)
    print(f"{label}: {amount_str} -> {to[:10]} | tx={txh[:18]} | status={rcpt.status} | block={rcpt.blockNumber}")
    return rcpt.status

def oracle_signal(symbol, score, px, direction, rationale):
    fn_sig = "postSignal(string,int256,uint256,string,string)"
    sel = Web3.keccak(text=fn_sig)[:4]
    data = sel + encode(["string","int256","uint256","string","string"],
                        (symbol, score, int(round(px*1_000_000)), direction, rationale))
    txn = {"from": ME, "to": ORACLE, "data": data, "nonce": W3.eth.get_transaction_count(ME),
           "gasPrice": W3.eth.gas_price, "gas": 300000, "chainId": CHAIN}
    txh, rcpt = sign_send(txn)
    print(f"ORACLE postSignal {symbol} score={score:+d} {direction} | tx={txh[:18]} | status={rcpt.status} | block={rcpt.blockNumber}")
    return rcpt.status

def native_send(to, eth_label):
    txn = {"from": ME, "to": Web3.to_checksum_address(to), "value": W3.to_wei(eth_label, "ether"),
           "nonce": W3.eth.get_transaction_count(ME), "gasPrice": W3.eth.gas_price,
           "gas": 21000, "chainId": CHAIN}
    txh, rcpt = sign_send(txn)
    print(f"NATIVE {eth_label} -> {to[:10]} | tx={txh[:18]} | status={rcpt.status} | block={rcpt.blockNumber}")
    return rcpt.status

ok = 0
# 1. diverse AREWA transfers
ok += transfer_token(AREWA, ORACLE, "250000", "AREWA->oracle")
ok += transfer_token(AREWA, "0x000000000000000000000000000000000000dEaD", "50000", "AREWA->burn")
# 2. native USDC(ETH) gas transfer to a second address (footprint diversity)
ok += native_send("0xADf0B89Bd55C3673aCB87738908BAda4f38730e1", "0.5")
# 3. oracle state-update write
ok += oracle_signal("SOL", 7, 106.11, "LONG", "Seykota +7/7 | 5D +6.2% | deep liq | trend hold")

print(f"\nDONE — {ok} real signed Arc testnet txns broadcast+confirmed this run. nonce now={W3.eth.get_transaction_count(ME)}")
