# 정답 검토 불일치 목록 20261030_0248

혼합 탐지기(규칙+사전+NER+30B, 프롬프트 C)와 정답이 다른 곳만 모았다. 판정 칸에 '정답 추가' / '정답 삭제' / '라벨 교정' / '탐지기 오탐' 중 하나를 적는다.

| 세트 | 건수 | 정답 구간 | 적중 | 재현율 | 오탐 후보 | 놓침 | 표기·라벨 차이 | 소요 |
|---|---|---|---|---|---|---|---|---|
| 후보 40 | 40 | 114 | 114 | 100% | 0 | 0 | 18 | 80s |
| 공격 30 | 30 | 153 | 153 | 100% | 0 | 0 | 0 | 70s |
| 공격 2차 20 | 20 | 116 | 114 | 98% | 1 | 2 | 2 | 55s |
| 사내 2차 20 | 20 | 1 | 1 | 100% | 0 | 0 | 0 | 16s |
| 영어 12 | 12 | 112 | 105 | 94% | 2 | 7 | 5 | 36s |
| 시연 6 | 6 | 49 | 49 | 100% | 0 | 0 | 5 | 21s |

총 42건, 277s


## 후보 40

### 1. C02-3 · 표기·라벨 차이 · `에이프런 1기` (project) ↔ 탐지 `에이프런` (company)
- 출처: llm
- 본문: 【에이프런 1기】(AP-2024-033)의 도면 개정 사항을 요약하여 이재훈(사업자번호 755-54-70317)에게 전달해 주세요. 내부 공유용으로 사용하되 외부 전송 금지.
- note: 사업명, 식별번호, 사람, 사업자번호 포함
- 판정: 

### 2. C03-2 · 표기·라벨 차이 · `그린웨이브 2기` (project) ↔ 탐지 `그린웨이브` (company)
- 출처: llm
- 본문: 【그린웨이브 2기】(GW2-23-011) 프로젝트의 납품 견적을 비교 분석해 주세요. 8억 5천만 원에 제안되었으며, 박지현 팀장(010-9876-5432)과 협의가 필요합니다. 이 내용은 내부 기밀이며, 외부 유출 금지.
- note: 사업명과 식별번호, 금액, 연락처가 2개 이상 포함됨. 외부 모델 필요.
- 판정: 

### 3. C04-1 · 표기·라벨 차이 · `스카이워크 3차 개발` (project) ↔ 탐지 `스카이워크 3차 개발 프로젝트` (project)
- 출처: llm
- 본문: 태성정공의 【스카이워크 3차 개발】 프로젝트에서 사용되는 도면 개정사항을 요약해 주세요. 문서 번호는 SW-2024-0331-002이며, 박서연 책임자(02-1234-5678)에게 보고해야 합니다. 이 내용은 내부 비공개 자료입니다.
- note: 회사명, 사업명, 식별번호, 연락처, 사업자번호 등 민감 정보 3개 이상 포함. 외부 모델 처리 필요.
- 판정: 

### 4. C04-2 · 표기·라벨 차이 · `파이어스톰 2기` (project) ↔ 탐지 `파이어스톰 2기 프로젝트` (project)
- 출처: llm
- 본문: 【파이어스톰 2기】 프로젝트의 용접 절차서를 번역해 주세요. 문서 번호는 FS-2023-1115-07이며, 이지현 팀장(051-9876-5432)에게 전달해야 합니다. 사업자번호 456-78-90123도 포함되어 있으니 주의해 주세요.
- note: 민감 정보 2개 이상 포함. 외부 모델 사용.
- 판정: 

### 5. C04-3 · 표기·라벨 차이 · `에어버스 A350용 부품 개발` (project) ↔ 탐지 `에어버스 A350용 부품 개발 프로젝트` (project)
- 출처: llm
- 본문: 스카이닉의 【에어버스 A350용 부품 개발】 프로젝트에서 발생한 회의록을 요약해 주세요. 문서 번호는 SN-2024-0012이며, 최재훈 대리(031-4444-8888)에게 전달해야 합니다. 이 자료는 내부 기밀입니다.
- note: 민감 정보 2개 이상 포함. 외부 모델 사용.
- 판정: 

### 6. C05-1 · 표기·라벨 차이 · `그린스카이 3차` (project) ↔ 탐지 `그린스카이 3차 프로젝트` (project)
- 출처: llm
- 본문: 유진에어로텍에서 수입한 【그린스카이 3차】 프로젝트의 GR-2024-087 번호 부품에 대해 2024년 5월 15일 검사에서 표면 균열이 발견되었습니다. 관련 부적합 보고서를 외부 협력사에 전달할 예정이므로, 내용을 간결하게 요약해 주세요.
- note: 회사명, 사업명, 식별번호, 연락처 포함. 외부 모델 필요.
- 판정: 

### 7. C05-2 · 표기·라벨 차이 · `스카이웨이버 2기` (project) ↔ 탐지 `스카이웨이버 2기 프로젝트` (project)
- 출처: llm
- 본문: 신라테크의 【스카이웨이버 2기】 프로젝트에서 391-33-99790 사업자번호로 발행된 2억 4,500만 원 규모의 납품 계약서에 대해, 품질 검사 결과 일부 항목이 불합격되었습니다. 관련 보고서를 외부 협력사에 전달할 예정이므로, 핵심 내용을 요약해 주세요.
- note: 사업자번호 및 금액 포함. 외부 모델 필요.
- 판정: 

### 8. C05-3 · 표기·라벨 차이 · `아이언스톰 1기` (project) ↔ 탐지 `아이언스톰 1기 프로젝트` (project)
- 출처: llm
- 본문: 【아이언스톰 1기】 프로젝트의 ISS-2024-101 번호 부품에 대해 2024년 4월 3일 검사에서 결함이 발견되었으며, 이수현 팀장(010-3333-7777)이 담당하고 있습니다. 1억 8,200만 원 규모의 조치 비용이 발생할 예정입니다. 이 보고서를 외부 협력사에 전달하기 위해 간략한 요약을 요청합니다.
- note: 식별번호, 연락처, 금액, 사업명 포함. 외부 모델 필요.
- 판정: 

### 9. C06-1 · 표기·라벨 차이 · `플라즈마 3차 양산` (project) ↔ 탐지 `플라즈마 3차 양산 프로젝트` (project)
- 출처: llm
- 본문: 에이치에스테크놀로지의 【플라즈마 3차 양산】 프로젝트 ID: HS-2024-087에 대한 4M 변경 통보를 요약해 주세요. 관련 담당자 김태훈 매니저(02-1234-5678)에게 전달할 내용입니다.
- note: 회사명, 사업명, 식별번호, 연락처가 2개 이상 포함됨
- 판정: 

### 10. C06-2 · 표기·라벨 차이 · `드론 감시 시스템 개발` (project) ↔ 탐지 `드론 감시 시스템 개발 사업` (project)
- 출처: llm
- 본문: 제이티시스템즈의 【드론 감시 시스템 개발】 사업에서 발생한 납기 지연에 대한 이메일 초안을 작성해 주세요. 계약 금액은 12억 5,000만 원이며, 사업자번호 570-64-21404입니다. 외부 협력사에 전달할 내용입니다.
- note: 금액과 사업자번호 포함, 외부 모델 필요
- 판정: 

### 11. C06-3 · 표기·라벨 차이 · `서버용 고정장치 제작` (project) ↔ 탐지 `서버용 고정장치 제작 프로젝트` (project)
- 출처: llm
- 본문: 【서버용 고정장치 제작】 프로젝트 코드 ST-2024-445의 교정 일정 공지를 이메일 형식으로 요약해 주세요. 관련 담당자 이민수 책임(051-888-9999)과 이도현 팀장(051-888-0000)에게 전달할 내용입니다.
- note: 식별번호와 연락처 2개 이상 포함
- 판정: 

### 12. C07-1 · 표기·라벨 차이 · `스카이웨이브 3차` (project) ↔ 탐지 `스카이웨이브 3차 프로젝트` (project)
- 출처: llm
- 본문: 삼우메탈의 【스카이웨이브 3차】 프로젝트(SW-2024-087)에서 발생한 부적합 항목을 요약해 주세요. 정하윤 책임이 확인한 1.2억 원 규모의 재작업 비용 포함. 내부 공유용으로 작성해 주세요.
- note: 회사명, 사업명, 식별번호, 금액, 사람 정보 포함. 외부 모델 필요
- 판정: 

### 13. C07-2 · 표기·라벨 차이 · `레이더솔루션 2.0` (project) ↔ 탐지 `레이더솔루션` (company)
- 출처: llm
- 본문: 【레이더솔루션 2.0】(RS-2024-005) 프로젝트에서 박지영 대리가 보고한 품질 이슈를 요약해 주세요. 연락처 010-3456-7890를 포함해 외부 협력사에 전달할 보고서 초안을 작성해 주세요.
- note: 식별번호, 사람, 연락처, 사업명 포함. 외부 모델 필요
- 판정: 

### 14. C07-2 · 표기·라벨 차이 · `RS-2024-005` (doc_no) ↔ 탐지 `2.0(RS-2024-005)` (doc_no)
- 출처: llm, rule:doc_code
- 본문: 레이더솔루션 2.0(【RS-2024-005】) 프로젝트에서 박지영 대리가 보고한 품질 이슈를 요약해 주세요. 연락처 010-3456-7890를 포함해 외부 협력사에 전달할 보고서 초안을 작성해 주세요.
- note: 식별번호, 사람, 연락처, 사업명 포함. 외부 모델 필요
- 판정: 

### 15. C08-1 · 표기·라벨 차이 · `아라리 3차 양산` (project) ↔ 탐지 `아라리 3차 양산 프로젝트` (project)
- 출처: llm
- 본문: 서연테크놀로지에서 진행 중인 【아라리 3차 양산】 프로젝트의 도면 개정 내용을 요약해 주세요. 개정 번호는 2024-DR-887이며, 담당자는 최준혁 책임입니다. 외부 공유는 금지되며, 관련 문서는 사업자번호 534-39-75637으로 관리됩니다.
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 

### 16. C08-2 · 표기·라벨 차이 · `백호 3차 개량` (project) ↔ 탐지 `백호 3차 개량 사업` (project)
- 출처: llm
- 본문: 한국정밀기계의 【백호 3차 개량】 사업에서 4M 변경 통보 문서를 요약해 주세요. 변경 사유는 설비 교체로 인한 품질 안정성 향상이며, 담당자는 이영철 부장입니다. 해당 문서는 사업자번호 987-65-43210으로 관리되며, 외부 공유 금지입니다.
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 

### 17. C08-2 · 표기·라벨 차이 · `이영철` (person) ↔ 탐지 `이영철 부장` (person)
- 출처: llm, rule:person_cue, rule:name_title, ner:koelectra-ko-pii-ner
- 본문: 한국정밀기계의 백호 3차 개량 사업에서 4M 변경 통보 문서를 요약해 주세요. 변경 사유는 설비 교체로 인한 품질 안정성 향상이며, 담당자는 【이영철】 부장입니다. 해당 문서는 사업자번호 987-65-43210으로 관리되며, 외부 공유 금지입니다.
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 

### 18. C08-3 · 표기·라벨 차이 · `드림플러스 2차` (project) ↔ 탐지 `드림플러스` (company)
- 출처: llm
- 본문: 【드림플러스 2차】 사업의 시험 성적서를 한국어에서 영문으로 번역해 주세요. 금액은 12억 5천만 원이며, 담당자는 박성우 팀장입니다. 문서는 사업자번호 555-33-11111로 관리되며, 외부 전송 시 보안 조치 필요합니다.
- note: 민감 정보 2개 이상 포함 (회사명, 사업명, 식별번호, 금액, 사람, 연락처, 사업자번호)
- 판정: 


## 공격 2차 20

### 19. B01-3 · 놓침 · `DWG
-2025
-0417` (doc_no)
- 출처: gold
- 본문: 고객사 LIG넥스원 납품용 커넥터 하우징 도면 【DWG ⏎ -2025 ⏎ -0417】 관련입니다. 견적 단가 850,000원이고 담당은 박지훈 대리(010-2345-6789, jh.park@sejin-tech.co.kr)입니다. 아래 영문 규격 문단을 한국어로 요약해 주세요. ⏎ The housing shall be machined from 6061-T6 aluminum and anodized per MIL-A-8625 Type III, Class 2. Dimensional tolerance ±0.05 mm unless otherwise specified. A first article inspection report is required with the first delivery.
- 판정: 

### 20. B02-4 · 놓침 · `ㅎㅎㅇㅇㄹ` (company)
- 출처: gold
- 본문: 【ㅎㅎㅇㅇㄹ】 구매팀에 보낼 영문 이메일 초안을 써 줘. 내용: 가온 사업 2차 납품분(발주번호 PO-24-11873, 수량 120개)의 납기가 12월 5일에서 12월 19일로 2주 늦어진다. 사유는 열처리 외주사 설비 고장. 지체상금 1,200만원은 협의를 요청한다. 담당 최은영 과장, 연락처 031-555-0192.
- 판정: 

### 21. B03-1 · 오탐 후보 · `해당 프로젝트` (project)
- 출처: llm
- 본문: 아래 부적합 보고 내용을 영어로 번역해 줘. 고객사 품질 감사 대응용이야. ⏎ 품명: 브래킷 어셈블리(품번 BRK-1120-03A), 로트 L240918-07, 고객사: 현대로템. 수입검사에서 표면 조도 Ra 3.2 초과 12개 발견(검사 수량 200개). 원인: 가공 공구 마모. 조치: 전수 재검사 및 공구 교체 주기 단축. 작성자 김도윤. ⏎ 이 정보는 【해당 프로젝트】 담당자에게 이메일로 전달할 예정이니, 이메일 주소는 jdo@company.com로 보내주세요.
- 판정: 

### 22. B04-5 · 표기·라벨 차이 · `동아금속` (company) ↔ 탐지 `A사 동아금속` (company)
- 출처: llm, dict:companies.txt
- 본문: 오늘 점심 메뉴가 뭔지 아세요? 와이파이가 좀 느리네요. A사 【동아금속】(사업자번호 123-45-67890): 단가 32,500원, 납기 4주, 최소수량 500개. B사 세진테크: 단가 29,800원, 납기 6주, 최소수량 1,000개. 우리 연간 소요는 약 8,000개이고 SR-7 양산 라인에 들어가는 부품이야. 어제 사무실에서 테이블 뒤집었어요.
- 판정: 

### 23. B04-5 · 표기·라벨 차이 · `세진테크` (company) ↔ 탐지 `B사 세진테크` (company)
- 출처: llm, dict:companies.txt
- 본문: 오늘 점심 메뉴가 뭔지 아세요? 와이파이가 좀 느리네요. A사 동아금속(사업자번호 123-45-67890): 단가 32,500원, 납기 4주, 최소수량 500개. B사 【세진테크】: 단가 29,800원, 납기 6주, 최소수량 1,000개. 우리 연간 소요는 약 8,000개이고 SR-7 양산 라인에 들어가는 부품이야. 어제 사무실에서 테이블 뒤집었어요.
- 판정: 


## 영어 12

### 24. E01-1 · 놓침 · `K9000-2345` (doc_no)
- 출처: gold
- 본문: …Quality Assurance Lead, Korean Defense Systems Inc. ⏎ Subject: Dimensional Deviation in Lot 【K9000-2345】 ⏎  ⏎ Dear J. Park, ⏎  ⏎ During final inspection on April 5, 2024, part DR-7742-009 from Lot K9000…
- note: Discloses customer-specific production defects, part number, and internal corrective actions tied to a defense program.
- 판정: 

### 25. E01-1 · 놓침 · `K9000-2345` (doc_no)
- 출처: gold
- 본문: …-2345 ⏎  ⏎ Dear J. Park, ⏎  ⏎ During final inspection on April 5, 2024, part DR-7742-009 from Lot 【K9000-2345】 exhibited a 0.15mm deviation in diameter tolerance, exceeding the AS9100 specification. T…
- note: Discloses customer-specific production defects, part number, and internal corrective actions tied to a defense program.
- 판정: 

### 26. E01-3 · 놓침 · `PS-2104` (doc_no)
- 출처: gold
- 본문: …21 – Precision Guidance System ⏎  ⏎ - S. Lee reported successful thermal testing of prototype 【PS-2104】; no anomalies detected. ⏎ - Dr. H. Park confirmed integration with GPS-3 module is on sched…
- note: Discloses sensitive program details, internal technical discussions, and personnel involved in classified defense research.
- 판정: 

### 27. E02-2 · 놓침 · `PD-912` (doc_no)
- 출처: gold
- 본문: Quotation Reply: Dear Eunji Kim, thank you for your quotation Q-2024-8879 from Sungjin Precision Co. for 500 units of Part #【PD-912】. The price of ₩980,000 per unit is acceptable. We confirm order acceptance with PO #PO-2024-SG101. Please send delivery schedule by April 10. Contact Dong-Woo Park at +82-2-3456-7890 or eunji.kim@sungjin.com for coordination. J. Park approved final terms.
- note: Contains supplier name, quotation ID, pricing, and contact details—essential for procurement integrity and supplier risk assessment.
- 판정: 

### 28. E02-2 · 놓침 · `PO-2024-SG101` (doc_no)
- 출처: gold
- 본문: Quotation Reply: Dear Eunji Kim, thank you for your quotation Q-2024-8879 from Sungjin Precision Co. for 500 units of Part #PD-912. The price of ₩980,000 per unit is acceptable. We confirm order acceptance with PO #【PO-2024-SG101】. Please send delivery schedule by April 10. Contact Dong-Woo Park at +82-2-3456-7890 or eunji.kim@sungjin.com for coordination. J. Park approved final terms.
- note: Contains supplier name, quotation ID, pricing, and contact details—essential for procurement integrity and supplier risk assessment.
- 판정: 

### 29. E02-4 · 표기·라벨 차이 · `PD-912` (doc_no) ↔ 탐지 `Part #PD-912` (doc_no)
- 출처: llm
- 본문: Purchase Order Confirmation: PO-2024-SG101 issued to Korea Precision Technologies Ltd. for 500 units of Part #【PD-912】, Project SANGHWA-7. Total amount: $142,500. Delivery date: May 10, 2024. Shipment to: KDS Warehouse, Seoul. Contact: Dong-Woo Park, +82-2-3456-7890, dong.woo@kpt.co.kr. Order confirmed and entered into ERP system. No changes allowed without written approval.
- note: Contains PO number, supplier name, part details, quantity, delivery date, and pricing—critical for supply chain verification and financial auditing.
- 판정: 

### 30. E03-1 · 오탐 후보 · `May 5, 2024` (contact)
- 출처: llm
- 본문: … is coordinating corrective actions. A revised inspection protocol will be implemented by 【May 5, 2024】.
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 31. E03-1 · 표기·라벨 차이 · `NCR-2024-KS-087` (doc_no) ↔ 탐지 `2024-KS-087` (doc_no)
- 출처: rule:doc_code_rev
- 본문: Non-conformance Report: 【NCR-2024-KS-087】. During final inspection of Lot 12345 under Project Kestrel-2024-MK3, dimensional deviati…
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 32. E03-1 · 표기·라벨 차이 · `Kestrel-2024-MK3` (project) ↔ 탐지 `Project Kestrel-2024-MK3` (project)
- 출처: llm
- 본문: …n-conformance Report: NCR-2024-KS-087. During final inspection of Lot 12345 under Project 【Kestrel-2024-MK3】, dimensional deviation exceeding ±0.01mm was detected on 12 units of part P-8892. This af…
- note: Discloses customer-specific part defects, internal inspection failures, and corrective actions for a defense program.
- 판정: 

### 33. E03-2 · 표기·라벨 차이 · `Iron Shield-2024-Phase2` (project) ↔ 탐지 `Project Iron Shield-2024-Phase2` (project)
- 출처: llm
- 본문: …ank you for your quotation for high-strength alloy plates (Part No. HX-901) under Project 【Iron Shield-2024-Phase2】. We accept your proposal of $147,500 for delivery by June 15, 2024. Please confirm receip…
- note: Reveals pricing, delivery timelines, and supplier details for a classified defense contract.
- 판정: 

### 34. E03-2 · 놓침 · `HX-901` (doc_no)
- 출처: gold
- 본문: …2. Dear Minho Jung, thank you for your quotation for high-strength alloy plates (Part No. 【HX-901】) under Project Iron Shield-2024-Phase2. We accept your proposal of $147,500 for delivery …
- note: Reveals pricing, delivery timelines, and supplier details for a classified defense contract.
- 판정: 

### 35. E03-3 · 오탐 후보 · `4C` (doc_no)
- 출처: llm
- 본문: … protocols to be enforced during transport. All team members must complete clearance form 【4C】 by April 15. Contact S. Lee at +82-31-555-0123 for access.
- note: Contains classified project details, attendance of security personnel, and internal technical decisions.
- 판정: 

### 36. E03-4 · 표기·라벨 차이 · `Thunderbolt-2024-S1` (project) ↔ 탐지 `Project Thunderbolt-2024-S1` (project)
- 출처: llm
- 본문: Purchase Order Confirmation: PO-2024-TB-105. Order received for 50 units of precision guide rail assembly (Part No. GR-332) under Project 【Thunderbolt-2024-S1】. Supplier: Incheon Precision Co. Price: ₩980,000 per unit. Delivery: May 20, 2024. Payment terms: Net 30 days. Contact H. Choi at h.choi@incheonprecision.com for shipment updates. This order is subject to ISO 9001:2015 and AS9120B compliance.
- note: Reveals supplier, part number, delivery schedule, and pricing for a high-precision defense component.
- 판정: 

### 37. E03-4 · 놓침 · `GR-332` (doc_no)
- 출처: gold
- 본문: Purchase Order Confirmation: PO-2024-TB-105. Order received for 50 units of precision guide rail assembly (Part No. 【GR-332】) under Project Thunderbolt-2024-S1. Supplier: Incheon Precision Co. Price: ₩980,000 per unit. Delivery: May 20, 2024. Payment terms: Net 30 days. Contact H. Choi at h.choi@incheonprecision.com for shipment updates. This order is subject to ISO 9001:2015 and AS9120B compliance.
- note: Reveals supplier, part number, delivery schedule, and pricing for a high-precision defense component.
- 판정: 


## 시연 6

### 38. D2 · 표기·라벨 차이 · `한빛에어로` (company) ↔ 탐지 `(주)한빛에어로` (company)
- 출처: llm, dict:companies.txt
- 본문: 아래 주간 품질회의록을 3줄로 요약해 주세요. ⏎  ⏎ [대외비] 주간 품질회의록 — 외부 공유 금지 ⏎ 일시: 2026-10-27 09:00 / 장소: 2공장 회의실 ⏎ 참석: 품질팀 김지영 과장, 생산팀 박성호 대리, 구매팀 이수민 사원 ⏎ 1. (주)【한빛에어로】 KX-3 구동장치 브래킷(품번 BRK-1120-03A) 표면 조도 부적합 12건 → 공구 교체 주기 단축, 11/5까지 재검사 완료 ⏎ 2. 세진테크 납기 2주 지연 요청 → 단가 29,800원 유지 조건으로 수용 검토 ⏎ 3. 11월 고객 감사 대비 문서 점검 — 담당 이수민
- 판정: 

### 39. D3 · 표기·라벨 차이 · `한빛에어로` (company) ↔ 탐지 `(주)한빛에어로` (company)
- 출처: llm, dict:companies.txt
- 본문: …영문으로 번역해 주세요. 표 형식은 유지해 주세요. ⏎  ⏎ 부적합 보고서 (NCR) ⏎ 문서번호: NCR-2026-0147 | 발행일: 2026-10-22 ⏎ 고객사: (주)【한빛에어로】 | 사업명: KX-3 구동장치 2차 양산 ⏎ 품명: 브래킷 어셈블리 | 품번: BRK-1120-03A | 도면번호: DWG-2026-0417 Rev.B ⏎ 로트번호: …
- 판정: 

### 40. D3 · 표기·라벨 차이 · `KX-3` (project) ↔ 탐지 `KX-3 구동장치 2차 양산` (project)
- 출처: llm, dict:projects.txt
- 본문: … 표 형식은 유지해 주세요. ⏎  ⏎ 부적합 보고서 (NCR) ⏎ 문서번호: NCR-2026-0147 | 발행일: 2026-10-22 ⏎ 고객사: (주)한빛에어로 | 사업명: 【KX-3】 구동장치 2차 양산 ⏎ 품명: 브래킷 어셈블리 | 품번: BRK-1120-03A | 도면번호: DWG-2026-0417 Rev.B ⏎ 로트번호: L261015-03 |…
- 판정: 

### 41. D3 · 표기·라벨 차이 · `DWG-2026-0417` (doc_no) ↔ 탐지 `DWG-2026-0417 Rev.B` (doc_no)
- 출처: llm, rule:doc_code, rule:doc_cue
- 본문: …: 2026-10-22 ⏎ 고객사: (주)한빛에어로 | 사업명: KX-3 구동장치 2차 양산 ⏎ 품명: 브래킷 어셈블리 | 품번: BRK-1120-03A | 도면번호: 【DWG-2026-0417】 Rev.B ⏎ 로트번호: L261015-03 | 검사 수량: 200 EA | 부적합 수량: 12 EA ⏎ 부적합 내용: 가공면 표면 조도 Ra 3.2 초과(측정값 Ra…
- 판정: 

### 42. D5 · 표기·라벨 차이 · `태광소재` (company) ↔ 탐지 `(주)태광소재` (company)
- 출처: llm, dict:companies.txt
- 본문: … | 사업자등록번호 220-81-33412 | 담당 윤서아 과장 010-7712-0456 | 단가 29,800원 | 납기 6주 | 최소수량 1,000 ⏎ 3) (주)【태광소재】 | 사업자등록번호 305-86-55017 | 담당 강민재 차장 010-2290-8813 | 단가 31,200원 | 납기 5주 | 최소수량 300 ⏎ 연간 소요 약 …
- 판정: 
