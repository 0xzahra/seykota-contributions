import solcx, json, os
from web3 import Web3
from eth_account import Account

solcx.set_solc_version("0.8.20")
"""
for v in solcx.get_installed_solc_versions(): print("solc", v)
"""
# compile the registry
src = open("/workspace/SeykotaAgentRegistry.sol").read()
compiled = solcx.compile_source(src, output_values=["abi", "bin"], solc_version="0.8.20")
name = "<stdlib>:SeykotaAgentRegistry" if "<stdlib>:SeykotaAgentRegistry" in compiled else list(compiled.keys())[0]
# find the right contract name
key = [k for k in compiled.keys() if "SeykotaAgentRegistry" in k][0]
abi = compiled[key]["abi"]
bytecode = compiled[key]["bin"]
print("compiled", key, "bytecode_len", len(bytecode))
open("/workspace/seykota_registry_abi.json", "w").write(json.dumps(abi))

# deploy
W3 = Web3(Web3.HTTPProvider("https://rpc.testnet.arc.io"))
PRIV = "0x60b0ef62b31d51973c1ba516eefab034d14d4a5588df0b1da4a0b6d17d341dbf"
acct = Account.from_key(PRIV)
me = acct.address
print("deployer", me)
Contract = W3.eth.contract(abi=abi, bytecode="0x" + bytecode)
nonce = W3.eth.get_transaction_count(me)
txn = Contract.constructor().build_transaction({"chainId": 5042002, "from": me, "nonce": nonce, "gasPrice": W3.eth.gas_price, "gas": 3000000})
signed = acct.sign_transaction(txn)
txh = W3.eth.send_raw_transaction(signed.raw_transaction)
print("deploy tx", txh.hex()[:22])
rcpt = W3.eth.wait_for_transaction_receipt(txh, timeout=120)
print("DEPLOY status", rcpt.status, "contract", rcpt.contractAddress, "block", rcpt.blockNumber)
