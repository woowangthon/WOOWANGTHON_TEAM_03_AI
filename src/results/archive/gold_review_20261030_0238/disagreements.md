# 정답 검토 불일치 목록 20261030_0238

혼합 탐지기(규칙+사전+NER+30B, 프롬프트 C)와 정답이 다른 곳만 모았다. 판정 칸에 '정답 추가' / '정답 삭제' / '라벨 교정' / '탐지기 오탐' 중 하나를 적는다.

| 세트 | 건수 | 오탐 후보 | 놓침 | 표기·라벨 차이 | 소요 |
|---|---|---|---|---|---|
| 후보 40 | 40 | 1 | 0 | 20 | 82s |
| 공격 30 | 30 | 2 | 0 | 0 | 71s |
| 공격 2차 20 | 20 | 1 | 2 | 2 | 51s |
| 사내 2차 20 | 20 | 0 | 0 | 0 | 15s |
| 영어 12 | 12 | 12 | 0 | 9 | 40s |
| 시연 6 | 6 | 0 | 0 | 5 | 25s |

총 54건, 284s


## 후보 40

### 1. C02-1 · 오탐 후보 · `김민수` (person)
- 출처: ner:koelectra-ko-pii-ner, llm
- 본문: 【김민수】
- note: 회사명, 사업명, 식별번호, 연락처 포함
- 판정: 

### 2. C02-3 · 표기·라벨 차이 · `에이프런 1기` (project) ↔ 탐지 `에이프런` (company)
- 출처: llm
- 본문: 【에이프런 1기】
- note: 사업명, 식별번호, 사람, 사업자번호 포함
- 판정: 

### 3. C03-2 · 표기·라벨 차이 · `그린웨이브 2기` (project) ↔ 탐지 `그린웨이브` (company)
- 출처: llm
- 본문: 【그린웨이브 2기】
- note: 사업명과 식별번호, 금액, 연락처가 2개 이상 포함됨. 외부 모델 필요.
- 판정: 

### 4. C03-2 · 표기·라벨 차이 · `GW2-23-011` (doc_no) ↔ 탐지 `2기(GW2-23-011)` (doc_no)
- 출처: llm, rule:doc_code
- 본문: 【GW2-23-011】
- note: 사업명과 식별번호, 금액, 연락처가 2개 이상 포함됨. 외부 모델 필요.
- 판정: 

### 5. C04-1 · 표기·라벨 차이 · `스카이워크 3차 개발` (project) ↔ 탐지 `스카이워크 3차 개발 프로젝트` (project)
- 출처: llm
- 본문: 【스카이워크 3차 개발】
- note: 회사명, 사업명, 식별번호, 연락처, 사업자번호 등 민감 정보 3개 이상 포함. 외부 모델 처리 필요.
- 판정: 

### 6. C04-2 · 표기·라벨 차이 · `파이어스톰 2기` (project) ↔ 탐지 `파이어스톰 2기 프로젝트` (project)
- 출처: llm
- 본문: 【파이어스톰 2기】
- note: 민감 정보 2개 이상 포함. 외부 모델 사용.
- 판정: 

### 7. C04-3 · 표기·라벨 차이 · `에어버스 A350용 부품 개발` (project) ↔ 탐지 `에어버스 A350용 부품 개발 프로젝트` (project)
- 출처: llm
- 본문: 【에어버스 A350용 부품 개발】
- note: 민감 정보 2개 이상 포함. 외부 모델 사용.
- 판정: 

### 8. C05-1 · 표기·라벨 차이 · `그린스카이 3차` (project) ↔ 탐지 `그린스카이 3차 프로젝트` (project)
- 출처: llm
- 본문: 【그린스카이 3차】
- note: 회사명, 사업명, 식별번호, 연락처 포함. 외부 모델 필요.
- 판정: 

### 9. C05-2 · 표기·라벨 차이 · `스카이웨이버 2기` (project) ↔ 탐지 `스카이웨이버 2기 프로젝트` (project)
- 출처: llm
- 본문: 【스카이웨이버 2기】
- note: 사업자번호 및 금액 포함. 외부 모델 필요.
- 판정: 

### 10. C05-3 · 표기·라벨 차이 · `아이언스톰 1기` (project) ↔ 탐지 `아이언스톰 1기 프로젝트` (project)
- 출처: llm
- 본문: 【아이언스톰 1기】
- note: 식별번호, 연락처, 금액, 사업명 포함. 외부 모델 필요.
- 판정: 

### 11. C06-1 · 표기·라벨 차이 · `플라즈마 3차 양산` (project) ↔ 탐지 `플라즈마 3차 양산 프로젝트` (project)
- 출처: llm
- 본문: 【플라즈마 3차 양산】
- note: 회사명, 사업명, 식별번호, 연락처가 2개 이상 포함됨
- 판정: 

### 12. C06-1 · 표기·라벨 차이 · `프로젝트 ID: HS-2024-087` (project) ↔ 탐지 `HS-2024-087` (doc_no)
- 출처: rule:doc_code, rule:doc_cue, llm
- 본문: 【프로젝트 ID: HS-2024-087】
- note: 회사명, 사업명, 식별번호, 연락처가 2개 이상 포함됨
- 판정: 

### 13. C06-2 · 표기·라벨 차이 · `드론 감시 시스템 개발` (project) ↔ 탐지 `드론 감시 시스템 개발 사업` (project)
- 출처: llm
- 본문: 【드론 감시 시스템 개발】
- note: 금액과 사업자번호 포함, 외부 모델 필요
- 판정: 

### 14. C06-3 · 표기·라벨 차이 · `서버용 고정장치 제작` (project) ↔ 탐지 `서버용 고정장치 제작 프로젝트` (project)
- 출처: llm
- 본문: 【서버용 고정장치 제작】
- note: 식별번호와 연락처 2개 이상 포함
- 판정: 

### 15. C07-1 · 표기·라벨 차이 · `스카이웨이브 3차` (project) ↔ 탐지 `스카이웨이브 3차 프로젝트` (project)
- 출처: llm
- 본문: 【스카이웨이브 3차】
- note: 회사명, 사업명, 식별번호, 금액, 사람 정보 포함. 외부 모델 필요
- 판정: 

### 16. C07-2 · 표기·라벨 차이 · `레이더솔루션 2.0` (project) ↔ 탐지 `레이더솔루션` (company)
- 출처: llm
- 본문: 【레이더솔루션 2.0】
- note: 식별번호, 사람, 연락처, 사업명 포함. 외부 모델 필요
- 판정: 

### 17. C07-2 · 표기·라벨 차이 · `RS-2024-005` (doc_no) ↔ 탐지 `2.0(RS-2024-005)` (doc_no)
- 출처: llm, rule:doc_code
- 본문: 【RS-2024-005】
- note: 식별번호, 사람, 연락처, 사업명 포함. 외부 모델 필요
- 판정: 

### 18. C08-1 · 표기·라벨 차이 · `아라리 3차 양산` (project) ↔ 탐지 `아라리 3차 양산 프로젝트` (project)
- 출처: llm
- 본문: 【아라리 3차 양산】
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 

### 19. C08-2 · 표기·라벨 차이 · `백호 3차 개량` (project) ↔ 탐지 `백호 3차 개량 사업` (project)
- 출처: llm
- 본문: 【백호 3차 개량】
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 

### 20. C08-2 · 표기·라벨 차이 · `이영철` (person) ↔ 탐지 `이영철 부장` (person)
- 출처: llm, rule:person_cue, rule:name_title, ner:koelectra-ko-pii-ner
- 본문: 【이영철】
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 

### 21. C08-3 · 표기·라벨 차이 · `드림플러스 2차` (project) ↔ 탐지 `드림플러스` (company)
- 출처: llm
- 본문: 【드림플러스 2차】
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 


## 공격 30

### 22. A03-5 · 오탐 후보 · `user at company dot com` (contact)
- 출처: llm
- 본문: 【user at company dot com】
- 판정: 

### 23. A03-5 · 오탐 후보 · `공일공 1234 5678` (contact)
- 출처: llm
- 본문: 【공일공 1234 5678】
- 판정: 


## 공격 2차 20

### 24. B01-3 · 놓침 · `DWG
-2025
-0417` (doc_no)
- 출처: gold
- 본문: 【DWG ⏎ -2025 ⏎ -0417】
- 판정: 

### 25. B02-4 · 놓침 · `ㅎㅎㅇㅇㄹ` (company)
- 출처: gold
- 본문: 【ㅎㅎㅇㅇㄹ】
- 판정: 

### 26. B03-1 · 오탐 후보 · `해당 프로젝트` (project)
- 출처: llm
- 본문: 【해당 프로젝트】
- 판정: 

### 27. B04-5 · 표기·라벨 차이 · `동아금속` (company) ↔ 탐지 `A사 동아금속` (company)
- 출처: llm, dict:companies.txt
- 본문: 【동아금속】
- 판정: 

### 28. B04-5 · 표기·라벨 차이 · `세진테크` (company) ↔ 탐지 `B사 세진테크` (company)
- 출처: llm, dict:companies.txt
- 본문: 【세진테크】
- 판정: 


## 영어 12

### 29. E01-1 · 오탐 후보 · `Lee Minho` (person)
- 출처: ner:koelectra-ko-pii-ner, llm
- 본문: …g step on machine #3. Corrective action includes recalibration and retraining of operator 【Lee Minho】. A full re-inspection is scheduled for April 8, 2024. The total cost of rework and delay …
- note: Discloses customer-specific production defects, part number, and internal corrective actions tied to a defense program.
- 판정: 

### 30. E01-1 · 오탐 후보 · `Y. Kim` (person)
- 출처: llm
- 본문: …d at $18,450. Please confirm acceptance of this report by April 10, 2024. ⏎  ⏎ Best regards, ⏎  ⏎ 【Y. Kim】 ⏎ Quality Control Manager ⏎ +82-2-555-0198 ⏎ y.kim@kdsi.co.kr
- note: Discloses customer-specific production defects, part number, and internal corrective actions tied to a defense program.
- 판정: 

### 31. E01-2 · 오탐 후보 · `SP-9911` (doc_no)
- 출처: llm
- 본문: …arch 12, 2024 ⏎  ⏎ Dear Procurement Team, ⏎  ⏎ Thank you for your quotation for 500 units of part 【SP-9911】 for Project Aegis-7. We accept your revised price of $22,300 for delivery by April 15, 20…
- note: Reveals supplier pricing, project name, and internal approval chain for a critical defense component.
- 판정: 

### 32. E01-3 · 오탐 후보 · `J. Kim` (person)
- 출처: llm
- 본문: …tendees: Dr. H. Park (Lead Engineer, Daewoo Defense Technologies), S. Lee (R&D Director), 【J. Kim】 (Security Compliance) ⏎  ⏎ Topic: Progress Update on Project Phoenix-21 – Precision Guidance …
- note: Discloses sensitive program details, internal technical discussions, and personnel involved in classified defense research.
- 판정: 

### 33. E01-3 · 오탐 후보 · `J. Kim` (person)
- 출처: llm
- 본문: …on schedule. ⏎ - Final system validation scheduled for April 20, 2024. ⏎ - Security review by 【J. Kim】 confirmed no data leakage risk. ⏎ - Budget update: $45,000 allocated for Q2 testing. All fu…
- note: Discloses sensitive program details, internal technical discussions, and personnel involved in classified defense research.
- 판정: 

### 34. E01-4 · 오탐 후보 · `KM-4402` (doc_no)
- 출처: llm
- 본문: …24 ⏎  ⏎ Dear J. Park, ⏎  ⏎ This confirms receipt and acceptance of PO-88291 for 200 units of part 【KM-4402】, designated for Project Titan-5. The total value is $98,500, payable within 30 days of de…
- note: Reveals supplier details, order quantities, pricing, and delivery schedule for a classified defense component.
- 판정: 

### 35. E02-1 · 표기·라벨 차이 · `Lot 8832-19` (project) ↔ 탐지 `Lot 8832-19` (doc_no)
- 출처: llm
- 본문: 【Lot 8832-19】
- note: Contains customer name, project code, part number, and inspection date—critical for defense contract compliance and traceability.
- 판정: 

### 36. E02-3 · 오탐 후보 · `D-3321` (doc_no)
- 출처: llm
- 본문: …compliance. Yuna Choi reported test results from Lab-7. Action: J. Park to revise drawing 【D-3321】 by April 18. Minho Jung to coordinate with supplier Sungjin Precision Co. for delivery. M…
- note: Contains project name, meeting date, person names, and internal system details—disclosure could expose R&D timelines and personnel roles.
- 판정: 

### 37. E02-3 · 오탐 후보 · `Sungjin Precision Co.` (company)
- 출처: llm
- 본문: …ion: J. Park to revise drawing D-3321 by April 18. Minho Jung to coordinate with supplier 【Sungjin Precision Co.】 for delivery. Meeting recorded in SecureDB v3.2. Contact: yuna.choi@kds.co.kr.
- note: Contains project name, meeting date, person names, and internal system details—disclosure could expose R&D timelines and personnel roles.
- 판정: 

### 38. E02-4 · 오탐 후보 · `Part #PD-912` (doc_no)
- 출처: llm
- 본문: 【Part #PD-912】
- note: Contains PO number, supplier name, part details, quantity, delivery date, and pricing—critical for supply chain verification and financial auditing.
- 판정: 

### 39. E02-4 · 표기·라벨 차이 · `PO-2024-SG101` (project) ↔ 탐지 `PO-2024-SG101` (doc_no)
- 출처: llm
- 본문: 【PO-2024-SG101】
- note: Contains PO number, supplier name, part details, quantity, delivery date, and pricing—critical for supply chain verification and financial auditing.
- 판정: 

### 40. E03-1 · 오탐 후보 · `Lot 12345` (doc_no)
- 출처: llm
- 본문: Non-conformance Report: NCR-2024-KS-087. During final inspection of 【Lot 12345】 under Project Kestrel-2024-MK3, dimensional deviation exceeding ±0.01mm was detected on 1…
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 41. E03-1 · 표기·라벨 차이 · `Project Kestrel` (project) ↔ 탐지 `Project Kestrel-2024-MK3` (project)
- 출처: llm
- 본문: Non-conformance Report: NCR-2024-KS-087. During final inspection of Lot 12345 under 【Project Kestrel】-2024-MK3, dimensional deviation exceeding ±0.01mm was detected on 12 units of part P-8892…
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 42. E03-1 · 표기·라벨 차이 · `NCR-2024-KS-087` (doc_no) ↔ 탐지 `2024-KS-087` (doc_no)
- 출처: rule:doc_code_rev
- 본문: Non-conformance Report: 【NCR-2024-KS-087】. During final inspection of Lot 12345 under Project Kestrel-2024-MK3, dimensional deviati…
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 43. E03-1 · 표기·라벨 차이 · `Kestrel-2024-MK3` (project) ↔ 탐지 `Project Kestrel-2024-MK3` (project)
- 출처: llm
- 본문: …n-conformance Report: NCR-2024-KS-087. During final inspection of Lot 12345 under Project 【Kestrel-2024-MK3】, dimensional deviation exceeding ±0.01mm was detected on 12 units of part P-8892. This af…
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 44. E03-2 · 표기·라벨 차이 · `Project Iron Shield` (project) ↔ 탐지 `Project Iron Shield-2024-Phase2` (project)
- 출처: llm
- 본문: …Jung, thank you for your quotation for high-strength alloy plates (Part No. HX-901) under 【Project Iron Shield】-2024-Phase2. We accept your proposal of $147,500 for delivery by June 15, 2024. Please co…
- note: Reveals pricing, delivery timelines, and supplier details for a classified defense contract.
- 판정: 

### 45. E03-2 · 표기·라벨 차이 · `Iron Shield-2024-Phase2` (project) ↔ 탐지 `Project Iron Shield-2024-Phase2` (project)
- 출처: llm
- 본문: …ank you for your quotation for high-strength alloy plates (Part No. HX-901) under Project 【Iron Shield-2024-Phase2】. We accept your proposal of $147,500 for delivery by June 15, 2024. Please confirm receip…
- note: Reveals pricing, delivery timelines, and supplier details for a classified defense contract.
- 판정: 

### 46. E03-3 · 오탐 후보 · `J. Park` (person)
- 출처: llm
- 본문: …ees: Y. Kim (Lead Engineer, Daejeon Defense Technologies), S. Lee (Security Liaison), and 【J. Park】 (Quality Assurance). Topic: Final design review for Phoenix-2024-RevB. Decision: Proceed …
- note: Contains classified project details, attendance of security personnel, and internal technical decisions.
- 판정: 

### 47. E03-3 · 오탐 후보 · `4C` (doc_no)
- 출처: llm
- 본문: … protocols to be enforced during transport. All team members must complete clearance form 【4C】 by April 15. Contact S. Lee at +82-31-555-0123 for access.
- note: Contains classified project details, attendance of security personnel, and internal technical decisions.
- 판정: 

### 48. E03-4 · 표기·라벨 차이 · `Project Thunderbolt` (project) ↔ 탐지 `Project Thunderbolt-2024-S1` (project)
- 출처: llm
- 본문: 【Project Thunderbolt】
- note: Reveals supplier, part number, delivery schedule, and pricing for a high-precision defense component.
- 판정: 

### 49. E03-4 · 표기·라벨 차이 · `Thunderbolt-2024-S1` (project) ↔ 탐지 `Project Thunderbolt-2024-S1` (project)
- 출처: llm
- 본문: 【Thunderbolt-2024-S1】
- note: Reveals supplier, part number, delivery schedule, and pricing for a high-precision defense component.
- 판정: 


## 시연 6

### 50. D2 · 표기·라벨 차이 · `한빛에어로` (company) ↔ 탐지 `(주)한빛에어로` (company)
- 출처: llm, dict:companies.txt
- 본문: 【한빛에어로】
- 판정: 

### 51. D3 · 표기·라벨 차이 · `한빛에어로` (company) ↔ 탐지 `(주)한빛에어로` (company)
- 출처: llm, dict:companies.txt
- 본문: …영문으로 번역해 주세요. 표 형식은 유지해 주세요. ⏎  ⏎ 부적합 보고서 (NCR) ⏎ 문서번호: NCR-2026-0147 | 발행일: 2026-10-22 ⏎ 고객사: (주)【한빛에어로】 | 사업명: KX-3 구동장치 2차 양산 ⏎ 품명: 브래킷 어셈블리 | 품번: BRK-1120-03A | 도면번호: DWG-2026-0417 Rev.B ⏎ 로트번호: …
- 판정: 

### 52. D3 · 표기·라벨 차이 · `KX-3` (project) ↔ 탐지 `KX-3 구동장치 2차 양산` (project)
- 출처: llm, dict:projects.txt
- 본문: … 표 형식은 유지해 주세요. ⏎  ⏎ 부적합 보고서 (NCR) ⏎ 문서번호: NCR-2026-0147 | 발행일: 2026-10-22 ⏎ 고객사: (주)한빛에어로 | 사업명: 【KX-3】 구동장치 2차 양산 ⏎ 품명: 브래킷 어셈블리 | 품번: BRK-1120-03A | 도면번호: DWG-2026-0417 Rev.B ⏎ 로트번호: L261015-03 |…
- 판정: 

### 53. D3 · 표기·라벨 차이 · `DWG-2026-0417` (doc_no) ↔ 탐지 `DWG-2026-0417 Rev.B` (doc_no)
- 출처: llm, rule:doc_code, rule:doc_cue
- 본문: …: 2026-10-22 ⏎ 고객사: (주)한빛에어로 | 사업명: KX-3 구동장치 2차 양산 ⏎ 품명: 브래킷 어셈블리 | 품번: BRK-1120-03A | 도면번호: 【DWG-2026-0417】 Rev.B ⏎ 로트번호: L261015-03 | 검사 수량: 200 EA | 부적합 수량: 12 EA ⏎ 부적합 내용: 가공면 표면 조도 Ra 3.2 초과(측정값 Ra…
- 판정: 

### 54. D5 · 표기·라벨 차이 · `태광소재` (company) ↔ 탐지 `(주)태광소재` (company)
- 출처: llm, dict:companies.txt
- 본문: … | 사업자등록번호 220-81-33412 | 담당 윤서아 과장 010-7712-0456 | 단가 29,800원 | 납기 6주 | 최소수량 1,000 ⏎ 3) (주)【태광소재】 | 사업자등록번호 305-86-55017 | 담당 강민재 차장 010-2290-8813 | 단가 31,200원 | 납기 5주 | 최소수량 300 ⏎ 연간 소요 약 …
- 판정: 
