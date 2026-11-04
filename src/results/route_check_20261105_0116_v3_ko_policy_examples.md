# 라우팅 검증 2026-11-05 01:15 · 기준 v3_ko_policy_examples

## samples.jsonl · 10건 · 일치 8/10 (80%) · p50 1.02s

| 정답 \ 판정 | local | external | block |
|---|---|---|---|
| local | 3 | 0 | 0 |
| external | 2 | 5 | 0 |

틀린 것:
- S01: 정답 external → local (p local 0.49 / external 0.47 / block 0.04)
- S04: 정답 external → local (p local 0.49 / external 0.28 / block 0.23)

## demo_docs_v1.jsonl · 6건 · 일치 4/6 (67%) · p50 1.40s

| 정답 \ 판정 | local | external | block |
|---|---|---|---|
| local | 2 | 0 | 0 |
| external | 1 | 2 | 0 |
| block | 1 | 0 | 0 |

틀린 것:
- D4: 정답 external → local (p local 0.66 / external 0.16 / block 0.18)
- D5: 정답 block → local (p local 0.71 / external 0.20 / block 0.09)
