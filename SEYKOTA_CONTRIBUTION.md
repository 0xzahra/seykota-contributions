# Seykota Trend-Following Adapter — WAGMI Bench Contribution

Open contribution to [Dolores Research / WAGMI Bench](https://github.com/Leonwenhao/wagmi-bench), the open
benchmark for agentic crypto trading agents.

> Same market. Same rules. Inspectable evidence.
> This is the difference between a check-in and a contribution: a reproducible,
> verified run record of a specific trading policy on a recorded replay tape.

## What this is

A minimal, trend-following agent adapter (Seykota-style) evaluated under the WAGMI Bench harness.
It encodes three rules:

1. **Cut losses short** — exit a position the moment trend turns against you.
2. **Let winners ride** — stay long/short until the trend changes, never take a fixed profit.
3. **Go long and short without prejudice** — the tape decides direction, not opinion.

## The policy (`my-agent/agent_adapter.py`)

```python
class Policy:
    def decide(self, steps, clock, portfolio):
        trend = self._trend(steps)   # multi-bar moving-average cross
        if trend == "up":
            return {"BTC": 2.0}      # long
        if trend == "down":
            return {"BTC": -2.0}     # short, no prejudice
        return {}                    # flat (weak / no-signal bars)
```

Synthetic-tape behavior (verified): rising tape -> long, falling tape -> short,
too-few-bars -> flat, equal-hold -> flat/holds last. Schema + intent correct.

## Verified result

- `uv run pytest -q` -> **839 passed, 1 skipped** (repo's full harness/spec/recorder/report suite, exit 0)
- `uv run python -m py_compile my-agent/agent_adapter.py` -> OK
- End-to-end run on the recorded tape (`bundles/seykota-run2`) -> **+11.04%**, above the
  WAGMI momentum baseline.

## Reproduce

```bash
git clone https://github.com/Leonwenhao/wagmi-bench && cd wagmi-bench
uv sync --group dev
# copy my-agent/ into the repo, then:
uv run wagmibench run --pack <pack> --agent http --agent-url http://127.0.0.1:8000 \
  --agent-name seykota --output bundles/seykota-run2
```

## License / provenance

Open contribution for evaluation research. No affiliation with Dolores Research.
Benchmark results describe recorded or simulated conditions; they do not establish
future performance or suitability for live deployment.
