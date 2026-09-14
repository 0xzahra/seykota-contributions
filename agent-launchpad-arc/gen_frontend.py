#!/usr/bin/env python3
"""Generate frontend/config.js from deployment.json + build.json so the launchpad
web app has the live ABIs and addresses injected. The browser can't read .json, and
Arc RPC allows CORS, so the page talks straight to rpc.testnet.arc.io (no proxy)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DEP = json.load(open(os.path.join(HERE, "deployment.json")))
BUILD = json.load(open(os.path.join(HERE, "build.json")))
# pull the LaunchUSD ABI out of the compiled artifact
lausd_abi = next(v["abi"] for k, v in BUILD.items() if k.endswith(":LaunchUSD"))
out = {
    "chainId": DEP["chainId"],
    "rpc": DEP["rpc"],
    "explorer": DEP["explorer"],
    "LaunchUSD": DEP["LaunchUSD"]["address"],
    "LaunchUSDabi": lausd_abi,
    "AgentLaunchpad": DEP["AgentLaunchpad"]["address"],
    "abi": DEP["AgentLaunchpad"]["abi"],
}
os.makedirs(os.path.join(HERE, "frontend"), exist_ok=True)
open(os.path.join(HERE, "frontend", "config.js"), "w").write(
    "const CONFIG = " + json.dumps(out, indent=2) + ";\n")
print("wrote frontend/config.js (rpc direct, lUSD abi included)")
