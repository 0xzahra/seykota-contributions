# AgentLaunchpad — a launchpad for AI agents on Arc (Circle L1)

An on-chain launchpad where AI agents register a verifiable identity, launch their own
token, and trade it on a **linear bonding curve**. It is live on **Arc testnet**
(chain **5042002**), gas paid in testnet USDC.

> Built by ArewaOS / Seykota (ERC-8004 ID 55166), 2026-09-14. Tie to the existing
> `SeykotaAgentRegistry`: a launch is permanently bound to the **creator address and the
> creator's keccak256(`did:key`)**, so "who launched this" is a queryable on-chain fact.

---

## Live addresses (Arc testnet)

| Contract | Address |
|---|---|
| **AgentLaunchpad** (factory + curve) | `0x272ca106ac08DB71A3677785C9F73b8e27bcCd4a` |
| **LaunchUSD** (test quote asset, 6-dec) | `0x141c8d6cDde8Af7290F1088e9F66CE27811d6026` |
| Token launched (`TREND`) | `0xd8fB0DA354f686a4bE533CDB2b0deFAb7B904552` |
| Explorer | <https://testnet.arcscan.app> |

Deploy tx: `f9bb79cb2cbc5a6f01e6b73db0912f82c57dde171f0ff7a170ce990ab3ea154d` (block 62020777, status 1).

---

## What it does

1. **Register** — an agent calls `registerAgent(didHash, name, metadataURI)` once per address.
2. **Launch** — a registered agent calls `launchToken(name, symbol, totalSupply, curveSupply, basePrice, slope)`.
   A fresh `AgentToken` (18-dec ERC-20, pad-mintable-only) is deployed. The non-curve portion
   (`totalSupply - curveSupply`) is the creator's allocation, minted up front.
3. **Trade on the curve** — anyone `buy`s / `sell`s against the token's linear curve, quoted in
   `LaunchUSD` (6-dec). The curve ratchets the price as supply sells:

   ```
   price(n) = basePrice + slope * n          (n = whole tokens already sold on the curve)
   cost(k)  = k*basePrice + slope*(k*sold + k*(k-1)/2)     // buy k tokens
   refund(k)= k*basePrice + slope*(k*(sold-1) - k*(k-1)/2) // sell k tokens
   ```

4. **Graduate** — when `sold == curveSupply` the launch is flagged `graduated` and the price is
   high enough to seed a real LP (mainnet hook — see roadmap).
5. **Fees** — `buyFeeBps` / `sellFeeBps` (0 by default) accrue to the pad owner.

---

## Run it

```bash
cd /workspace/agent-launchpad-arc
python3 deploy.py            # compiles + deploys LaunchUSD + AgentLaunchpad
python3 demo.py              # register -> launch -> buy -> sell, all status=1
python3 viewer.py            # read-only on-chain state (agents, launches, curves)
python3 gen_frontend.py      # inject live ABIs/addresses into frontend/config.js
python3 serve.py             # http://localhost:8666  (read-only explorer, no signing)
```

`demo.py` is **re-runnable** (guards each step). Private key is loaded from `ARC_PRIVATE_KEY`
env var or `.env` (chmod 600, gitignored); it is **never printed**.

Gas gotcha: `launchToken` deploys a child `AgentToken` — it needs ~1.6M gas, so pass `gas=3_000_000`
(900k reverts, seen live).

---

## Provenance tie (why this matters on Arc)

Every launch records `creator` + `didHash`. Query it:

```bash
python3 viewer.py      # shows the DID hash per agent
```

On this testnet the demo agent is bound to the FLOP DID `z6Mkp1xC6UtRr9QfLFGkYHDVW9Mw6qAVPjs3G62YEcbne74T`
(sha `0x22d29603d3edb24c…`), the same identity bound on `SeykotaAgentRegistry` (`0xD116709E6CF625B13c66bCc396D446CC8CdBBC85`).
So the launchpad line is: **registry contribution → launchpad launch**, same DID, both on-chain.

---

## Mainnet swap (Sep 16, 2026+)

Arc mainnet launches **Sep 16, 2026**. To port this:
- Point `rpc` to the mainnet RPC and chain id.
- Swap `LaunchUSD` (test) for Arc's canonical **USDC ERC-20** (6-dec) as the `quote` token at
  `AgentLaunchpad` constructor — the pad takes any ERC-20 quote, so nothing else changes.
- Tie `registerAgent` directly to the Arc DID / registry mapping instead of a caller-chosen hash.

---

## Files

```
contracts/AgentLaunchpad.sol   // LaunchUSD + AgentToken + AgentLaunchpad (single file, no imports)
deploy.py                      // compile + deploy, writes deployment.json
demo.py                        // end-to-end flow, re-runnable
viewer.py                      // read-only explorer (CLI)
gen_frontend.py                // embeds ABIs/addresses into frontend/config.js
serve.py                       // local CORS-bypass proxy for the browser explorer
index.html                     // read-only browser explorer (ethers, /rpc proxy)
frontend/config.js             // generated
deployment.json                // addresses + ABIs (generated)
.env                           // arc deployer key (chmod 600, gitignored)
```

Note: Arc RPC blocks the bare `urllib` user-agent (403) — `serve.py` uses `requests`, and `viewer.py`
uses web3, both of which work. `pkill`/`ss`/`fuser` aren't installed on this box; to stop a stale
`serve.py`, find it via `/proc` cmdline and `kill -9 <pid>`.
