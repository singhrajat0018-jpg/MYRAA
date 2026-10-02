# AI Manager 4.1 — Held-out Evaluation Report

- Items: **101**
- Calibration fitted on development split (a=0.777, b=1.084); reported metrics are held-out only.

## Routing accuracy

| Dimension | Accuracy |
|---|---|
| Intent | 97.03 |
| Domain | 99.01 |
| Capability | 100.0 |
| Output type | 98.02 |
| Execution mode | 99.01 |
| Reasoning depth | 97.03 |
| Freshness | 99.01 |
| Risk level | 99.01 |
| Tool requirement hit | 93.33 |
| Decision (CLARIFY/ABSTAIN) | 100.0 |
| Multi-intent route correctness | 100.0 |
| Reference resolution | 100.0 |
| Hinglish intent | 100.0 |
| Hinglish domain | 100.0 |

## Calibration (held-out)

- Brier raw: **0.2845** vs calibrated: **0.0524**
- ECE raw: **0.4719** vs calibrated: **0.1585**
- False-high-confidence rate (>=0.8): **0.0**
- False-low-confidence rate (<0.3): **0.0**
- Decision accuracy (calibrated >= 0.5): **0.9703**

### Bucket table (calibrated)

| Bucket | n | accuracy | mean conf |
|---|---|---|---|
| [0.0,0.1) | 0 | - | - |
| [0.1,0.2) | 0 | - | - |
| [0.2,0.3) | 0 | - | - |
| [0.3,0.4) | 0 | - | - |
| [0.4,0.5) | 0 | - | - |
| [0.5,0.6) | 0 | - | - |
| [0.6,0.7) | 0 | - | - |
| [0.7,0.8) | 46 | 0.935 | 0.786 |
| [0.8,0.9) | 55 | 1.000 | 0.833 |
| [0.9,1.0) | 0 | - | - |

## Latency

- p50: **1.813 ms**, p95: **2.894 ms**, p99: **4.491 ms**

## Multi-intent decomposition

- Precision: **1.0**, Recall: **1.0**

## Per-category

| Category | n | intent | domain | avg lat (ms) |
|---|---|---|---|---|
| ADVERSARIAL | 1 | 100.0 | 100.0 | 1.992 |
| AMBIGUOUS | 1 | 0.0 | 100.0 | 1.684 |
| CODING | 13 | 92.31 | 100.0 | 1.931 |
| COMPUTER_USE | 23 | 100.0 | 100.0 | 1.782 |
| CONTEXTUAL | 1 | 100.0 | 100.0 | 1.961 |
| CREATION | 4 | 100.0 | 100.0 | 1.846 |
| DOCUMENT | 1 | 100.0 | 100.0 | 2.134 |
| EDUCATION | 5 | 100.0 | 100.0 | 1.788 |
| GENERAL | 15 | 100.0 | 93.33 | 1.183 |
| HINGLISH | 3 | 100.0 | 100.0 | 1.704 |
| MULTIMODAL | 1 | 100.0 | 100.0 | 2.229 |
| MULTI_INTENT | 3 | 100.0 | 100.0 | 4.304 |
| NX | 1 | 100.0 | 100.0 | 2.077 |
| RESEARCH | 10 | 100.0 | 100.0 | 2.031 |
| SYSTEM | 1 | 100.0 | 100.0 | 1.871 |
| TRADING | 15 | 100.0 | 100.0 | 2.032 |
| VISION | 3 | 66.67 | 100.0 | 1.355 |