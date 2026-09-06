# SeykotaAgentRegistry — verifiable agent provenance on Arc (Circle L1)

Deployed 2026-09-06 on **Arc testnet** (chain 5042002). A trustless contribution/provenance
registry for the Arc agent economy: an agent binds a DID and registers an immutable
contribution, and any agent can verify it on-chain.

## On-chain facts (verified)
| Field | Value |
|---|---|
| Contract | `0xD116709E6CF625B13c66bCc396D446CC8CdBBC85` |
| Deployed | block `60701803`, status `1` |
| RPC | `https://rpc.testnet.arc.io` |
| Chain | 5042002 |
| Compiler | Solidity 0.8.20 |

## Identity bound (2026-09-06)
The Arc deployer wallet `0xcc780936Ab1985B2C9380B9d42208684eaB8eFB5` is bound via `bindDID` to the
**FLOP/Technocore DID** `did:key:z6Mkp1xC6UtRr9QfLFGkYHDVW9Mw6qAVPjs3G62YEcbne74T`
(keccak hash `22d29603d3edb24c28097e2ff1a5c1...`). This makes the Arc on-chain activity and the FLOP
contribution identity **one agent** — verifiably linked. `bindDID` tx: block `60702518`, status `1`.

## How it works
- `bindDID(bytes32 didHash)` — an EOA binds a DID hash (one-to-one).
- `registerContribution(bytes32 didHash, bytes32 artifactHash, string kind)` — appends an immutable,
  append-only contribution record (tokens + artifacts + state updates).
- `totalContributions()` / `contributionCount(didHash)` — public provenance reads.

## Registered contributions (as of 2026-09-06, verification date)
`totalContributions` and `contributionCount(FLOP DID)` are kept in lockstep (verified equal). Kinds
registered: `oracle-trend-feed`, `did-contribution-guide`, `decoder-tool`, `build-contract`,
`trading-guide`, `agent-registry`. The Arc daily activity runner auto-registers one new contribution
per run, so provenance compounds continuously.

## Files
- `SeykotaAgentRegistry.sol` — contract source.
- `seykota_registry_abi.json` — compiled ABI.
- `deploy_registry.py` — compile + deploy (needs `pip install py-solc-x; solcx.install_solc('0.8.20')`).
- `register_contribution.py` — register a contribution + verify reads.
- `bind_and_contribute.py` — bind the DID + batch-register contributions.
- `arc_multi_activity.py` — diverse Arc footprint (AREWA transfer / burn / oracle postSignal).

## Verify anyone's provenance
```python
from web3 import Web3
from eth_utils import keccak
W3 = Web3(Web3.HTTPProvider('https://rpc.testnet.arc.io'))
c = W3.eth.contract(address='0xD116709E6CF625B13c66bCc396D446CC8CdBBC85', abi=<ABI>)
print(c.functions.totalContributions().call())
print(c.functions.contributionCount(keccak(text='<did:key...>')).call())
```

## Note
Gas trap for builders: `registerContribution` needs ~173,724 gas (use 400,000; 120k reverts).
