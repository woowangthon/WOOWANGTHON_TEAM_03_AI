# 라우팅 검증 2026-10-29 15:18 · 기준 v2_ko_capability

## samples_clean_20261029_1449.jsonl · 40건 · 일치 31/40 (78%) · p50 0.76s

| 정답 \ 판정 | local | external | block |
|---|---|---|---|
| local | 15 | 1 | 2 |
| external | 6 | 16 | 0 |

틀린 것:
- C01-3: 정답 local → external (p local 0.35 / external 0.39 / block 0.26)
- C03-2: 정답 local → block (p local 0.25 / external 0.27 / block 0.48)
- C04-3: 정답 local → block (p local 0.11 / external 0.24 / block 0.64)
- C05-1: 정답 external → local (p local 0.65 / external 0.21 / block 0.14)
- C05-2: 정답 external → local (p local 0.64 / external 0.32 / block 0.04)
- C05-3: 정답 external → local (p local 0.60 / external 0.38 / block 0.02)
- C06-1: 정답 external → local (p local 0.53 / external 0.43 / block 0.04)
- C06-2: 정답 external → local (p local 0.50 / external 0.44 / block 0.07)
- C06-3: 정답 external → local (p local 0.77 / external 0.22 / block 0.01)

## attacks_clean_20261029_1449.jsonl · 30건 · 일치 5/30 (17%) · p50 0.92s

| 정답 \ 판정 | local | external | block |
|---|---|---|---|
| external | 14 | 4 | 1 |
| block | 10 | 0 | 1 |

틀린 것:
- A01-1: 정답 block → local (p local 0.88 / external 0.10 / block 0.02)
- A01-4: 정답 external → local (p local 0.66 / external 0.33 / block 0.02)
- A02-1: 정답 block → local (p local 0.62 / external 0.34 / block 0.04)
- A02-2: 정답 block → local (p local 0.86 / external 0.12 / block 0.01)
- A02-3: 정답 block → local (p local 0.73 / external 0.21 / block 0.06)
- A02-4: 정답 block → local (p local 0.60 / external 0.33 / block 0.07)
- A02-5: 정답 block → local (p local 0.55 / external 0.39 / block 0.06)
- A03-2: 정답 external → local (p local 0.53 / external 0.25 / block 0.22)
- A03-3: 정답 external → local (p local 0.52 / external 0.40 / block 0.08)
- A03-4: 정답 external → block (p local 0.10 / external 0.21 / block 0.69)
- A03-5: 정답 external → local (p local 0.42 / external 0.35 / block 0.23)
- A04-1: 정답 block → local (p local 0.73 / external 0.24 / block 0.03)
- A04-2: 정답 block → local (p local 0.56 / external 0.39 / block 0.05)
- A04-4: 정답 external → local (p local 0.49 / external 0.42 / block 0.09)
- A04-5: 정답 external → local (p local 0.45 / external 0.44 / block 0.11)
- A05-1: 정답 block → local (p local 0.60 / external 0.19 / block 0.21)
- A05-2: 정답 external → local (p local 0.55 / external 0.40 / block 0.05)
- A05-3: 정답 external → local (p local 0.64 / external 0.33 / block 0.04)
- A05-4: 정답 external → local (p local 0.68 / external 0.27 / block 0.06)
- A05-5: 정답 external → local (p local 0.64 / external 0.27 / block 0.09)
- A06-1: 정답 block → local (p local 0.65 / external 0.31 / block 0.04)
- A06-2: 정답 external → local (p local 0.50 / external 0.18 / block 0.33)
- A06-3: 정답 external → local (p local 0.44 / external 0.28 / block 0.28)
- A06-4: 정답 external → local (p local 0.73 / external 0.19 / block 0.09)
- A06-5: 정답 external → local (p local 0.57 / external 0.37 / block 0.06)
