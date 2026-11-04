# 라우팅 검증 2026-11-05 01:15 · 기준 v1_en_capability

## samples.jsonl · 10건 · 일치 10/10 (100%) · p50 0.64s

| 정답 \ 판정 | local | external | block |
|---|---|---|---|
| local | 3 | 0 | 0 |
| external | 0 | 7 | 0 |

틀린 것:
- 없음

## demo_docs_v1.jsonl · 6건 · 일치 4/6 (67%) · p50 1.05s

| 정답 \ 판정 | local | external | block |
|---|---|---|---|
| local | 2 | 0 | 0 |
| external | 1 | 2 | 0 |
| block | 1 | 0 | 0 |

틀린 것:
- D5: 정답 block → local (p local 0.56 / external 0.38 / block 0.06)
- D6: 정답 external → local (p local 0.35 / external 0.30 / block 0.35)
