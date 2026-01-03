---
description: How to run bounded quant experiments with memory and skills
---

# Quant Wrangler Workflow

Use this workflow for mlang-style sweep experiments, backtests, and pattern mining.

## Core Principle

> **Every experiment is a bounded task with stored results.**
> Never run analysis without saving findings to memory.

---

## 1. Before Starting an Experiment

**Check memory for prior work:**
```
memory(operation='search', content='<your experiment topic>', metadata={'project': 'mlang'})
```

If relevant prior work exists, reference it in your approach.

---

## 2. Queue the Experiment as a Task

Structure experiments with clear boundaries:

```python
queue_add(
    objective="Test ATR(14) vs ATR(21) stop distances on MES 5-day data",
    context="Using LONG_0.25 limit entry, 1.0R target",
    acceptance="Report WR, Net PnL, Max DD for each config",
    max_steps=30,
    max_tool_calls=50,
    metadata={"project": "mlang", "experiment_type": "sweep"}
)
```

**Required fields:**
- `objective`: What you're testing (one specific hypothesis)
- `context`: Fixed parameters / dataset
- `acceptance`: What qualifies as "done" (specific metrics)

---

## 3. Run the Experiment

Use promoted skills when available:
```python
# Load data
from load_ohlcv_data import load_ohlcv_data
df = load_ohlcv_data('path/to/data.parquet')

# Detect patterns
from rejection_patterns import find_rejection_patterns
patterns = find_rejection_patterns(df, wick_ratio=0.6)

# Run simulation
from run_oco_sim import run_oco_sim
results = run_oco_sim(configs=[...], bars=df)
```

**If a script is reusable, promote it:**
```
promote_skill(
    name="run_oco_sim",
    source_path="workspace/scripts/oco_simulation.py",
    description="Runs OCO bracket order simulation on OHLCV data"
)
```

---

## 4. Store Results in Memory

**Always store structured findings:**

```python
memory(operation='store', content='''
EXPERIMENT: ATR(14) vs ATR(21) Stop Distance
DATASET: MES 5-day fresh (2024-12-09 to 2024-12-13)
CONFIG: LONG_0.25_1.0R, $300 risk

RESULTS:
| ATR Period | Trades | WR   | Net PnL | Max DD |
|------------|--------|------|---------|--------|
| 14         | 42     | 57%  | +$2,340 | $890   |
| 21         | 38     | 53%  | +$1,820 | $1,120 |

CONCLUSION: ATR(14) outperforms on this dataset. Tighter stops = more trades but higher WR.
''', metadata={
    'project': 'mlang',
    'category': 'sweep_result',
    'config': 'LONG_0.25_1.0R',
    'atr_periods_tested': [14, 21],
    'winner': 'ATR(14)'
})
```

---

## 5. Log Lessons Learned

**For failures or surprises, use learn:**

```python
memory(operation='learn', content='''
TRIGGER: ATR(21) stops hit breakeven too often
SYMPTOM: Win rate dropped from 57% to 53%
ROOT_CAUSE: Wider stops let price retrace to entry more often
SOLUTION: For pullback entries, tighter ATR periods (7-14) work better
TEST: Compare ATR(7) vs ATR(14) on same dataset
''', metadata={'project': 'mlang', 'category': 'lesson_learned'})
```

**For operational rules, use ledger:**

```
log_mistake(
    trigger="Used percentage normalization instead of Z-score",
    root_cause="CNN outputs constant ~0.27 with tiny percentage values",
    rule="ALWAYS use Z-score normalization: (x - mean) / std per window",
    test="Check CNN output variance > 0.1"
)
```

---

## 6. Mark Task Complete

```python
queue_done(
    task_id="task_XXXX",
    summary="Tested ATR periods, ATR(14) wins",
    what_changed=["results/atr_comparison.parquet", "memory stored"]
)
```

---

## Quick Reference: Memory Categories

| Category | Use For | Example |
|----------|---------|---------|
| `sweep_result` | Completed sweep findings | "ATR(14) beats ATR(21)" |
| `lesson_learned` | Why something failed | "Percentage norm breaks CNN" |
| `best_config` | Proven winning configs | "LONG_0.25_1.0R_5m_SIMPLE" |
| `dataset_info` | Data characteristics | "MES 5-day has 1800 bars" |
| `bug_fix` | Debugging discoveries | "Generator repeat bug fix" |

---

## Skills to Promote

Once you've written a reusable script, promote it:

| Skill | Purpose |
|-------|---------|
| `load_ohlcv_data` | Load parquet/CSV to DataFrame |
| `find_rejection_patterns` | Pattern detection with labeling |
| `calculate_atr` | ATR calculation at any timeframe |
| `run_oco_sim` | OCO bracket order simulation |
| `summarize_results` | Generate trade report from results |

---

## Example Full Experiment

```
# 1. Search prior work
memory(operation='search', content='ATR stop distance comparison')

# 2. Queue task
queue_add(objective="Compare ATR(14) vs ATR(21) stops", ...)

# 3. Run experiment (using skills)
# ... pyexe code using promoted skills ...

# 4. Store results
memory(operation='store', content='EXPERIMENT: ATR comparison...', 
       metadata={'project': 'mlang', 'category': 'sweep_result'})

# 5. Log lessons if any
memory(operation='learn', content='TRIGGER: Wide stops hit BE too often...',
       metadata={'project': 'mlang', 'category': 'lesson_learned'})

# 6. Mark done
queue_done(task_id="task_XXXX", summary="ATR(14) wins", ...)
```
