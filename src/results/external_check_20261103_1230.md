# 외부 LLM 경로 점검 · 20261103_1230

모델 claude-sonnet-5-5 · effort medium · fallback 켬 · 탐지 규칙+NER+30B · 가림 정책 기본(이름 끔). 총 비용(추정) $0.0443. smoke: claude-sonnet-5-5 end_turn 자리표 {'sent': 1, 'kept': 1} 1.923s

| 문서 | 경로 | 자 | 구간 | 가림 | 자리표 보냄 | 답변에 유지 | 미복원 | 원문 복귀 | 유출 | 종료 | 응답 모델 | 입력/출력 토큰 | $ | 탐지 s | API s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D3 | external | 563 | 14 | 12 | 11 | 11 | 0 | 11/11 | 0 | end_turn | claude-sonnet-5-5 | 603/755 | 0.00876 | 10.17 | 5.293 |
| D4 | external | 421 | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | end_turn | claude-sonnet-5-5 | 480/1379 | 0.01475 | 0.32 | 10.247 |
| D6 | external | 314 | 9 | 7 | 7 | 7 | 0 | 7/7 | 0 | end_turn | claude-sonnet-5-5 | 392/375 | 0.00453 | 3.79 | 3.737 |
| TEST-01 | external(강제) | 2,546 | 41 | 34 | 19 | 14 | 0 | 14/19 | 0 | end_turn | claude-sonnet-5-5 | 1672/1196 | 0.0153 | 14.48 | 7.135 |

열 설명: 자리표 보냄 = 가림 본문의 자리표 종류 수, 답변에 유지 = 그중 답변에 그대로 남은 수(요약이면 전부 안 나와도 정상), 미복원 = 복원 뒤에도 남은 자리표(대응표에 없는 것, 0이어야 함), 원문 복귀 = 복원 답변에 원문 값이 나타난 종류 수, 유출 = 전송 본문에 남은 원문 값(0이어야 함).

## D3 · 외부 전송 · 가림

- 가림 정책: 이름 끔 · 종료 end_turn · 응답 모델 claude-sonnet-5-5

### 외부로 나간 본문

```
아래 부적합 보고서를 고객사 품질 감사 대응용 영문으로 번역해 주세요. 표 형식은 유지해 주세요.

부적합 보고서 (NCR)
문서번호: [[ID_1]] | 발행일: 2026-10-22
고객사: (주)[[ORG_1]] | 사업명: [[PROJECT_1]]
품명: 브래킷 어셈블리 | 품번: [[ID_2]] | 도면번호: [[ID_3]]
로트번호: [[ID_4]] | 검사 수량: 200 EA | 부적합 수량: 12 EA
부적합 내용: 가공면 표면 조도 Ra 3.2 초과(측정값 Ra 4.1~4.6), 도면 요구 Ra 3.2 이하
원인 분석: 황삭 공구 마모 한계 초과 사용(교체 주기 400개 → 실제 520개 가공)
시정 조치: 해당 로트 전수 재검사, 공구 교체 주기 350개로 단축, 작업표준서 [[ID_5]] 개정
비용: 재작업 비용 [[AMT_1]] (단가 [[AMT_2]] 기준 불량 12 EA 재가공)
작성: 품질팀 김지영 과장 ([[CONTACT_1]], [[CONTACT_2]])
고객 담당: [[ORG_1]] 품질보증팀 정민호 책임
```

### 복원된 답변

```
# Nonconformity Report (NCR)

| Item | Details |
|---|---|
| **Document No.** | NCR-2026-0147 |
| **Issue Date** | 2026-10-22 |
| **Customer** | 한빛에어로 Co., Ltd. |
| **Project** | KX-3 구동장치 2차 양산 |
| **Part Name** | Bracket Assembly |
| **Part No.** | BRK-1120-03A |
| **Drawing No.** | DWG-2026-0417 Rev.B |
| **Lot No.** | L261015-03 |
| **Inspected Quantity** | 200 EA |
| **Nonconforming Quantity** | 12 EA |
| **Description of Nonconformity** | Surface roughness of the machined surface exceeded Ra 3.2 (measured values: Ra 4.1–4.6); the drawing requires Ra 3.2 or less. |
| **Root Cause Analysis** | The roughing tool was used beyond its wear limit (replacement interval: 400 pieces; actual usage: 520 pieces machined). |
| **Corrective Actions** | 1) 100% re-inspection of the affected lot. 2) Tool replacement interval shortened to 350 pieces. 3) Revision of Work Standard WS-07-12. |
| **Cost** | Rework cost: 2,400,000원 (based on unit price of 850,000원 for reworking 12 nonconforming EA) |
| **Prepared by** | Manager Jiyoung Kim, Quality Team (010-4821-7736, jy.kim@daesung-precision.co.kr) |
| **Customer Contact** | Minho Jung, Senior Manager, Quality Assurance Team, 한빛에어로 |

**Translation notes:**
- "과장" is rendered as "Manager" and "책임" as "Senior Manager." Please adjust to match the titles your company and the customer use in official documents.
- The tool replacement interval was changed from 400 to 350 pieces, but the actual usage was 520 pieces. For the audit, you may wish to add a note on how adherence to the interval will be monitored (e.g., a counter or checklist), since auditors often ask about this.
- The placeholders have been kept exactly as in the source.
```

## D4 · 외부 전송 · 그대로

- 가림 정책: 이름 끔 · 종료 end_turn · 응답 모델 claude-sonnet-5-5

### 외부로 나간 본문

```
AS9100D 8.5.1 '생산 및 서비스 제공의 관리' 요구사항을 아래 원문 요약을 바탕으로 우리 검사 절차서에 반영할 점검표(체크리스트)로 만들어 주세요. 항목은 10개 이내로.

(원문 요약) 조직은 관리된 조건에서 생산을 수행해야 한다. 관리된 조건에는 제품 특성과 달성해야 할 결과를 정의한 문서화된 정보의 가용성, 적절한 모니터링 및 측정 자원의 가용성과 사용, 공정 산출물이 합격 기준을 충족함을 검증하는 활동, 적절한 인프라와 환경, 적격한 인원의 배치, 특수 공정의 유효성 확인, 인적 오류 방지 조치, 인도 활동과 인도 후 활동이 포함된다. 항공우주 요구사항으로 생산 공정 검증(First Article Inspection), 작업 이전(work transfer) 관리, 키 특성(key characteristics) 관리가 추가된다.
```

### 복원된 답변

```
# AS9100D 8.5.1 생산 및 서비스 제공의 관리 – 검사 절차서 반영용 점검표

| No. | 점검 항목 | 확인 내용(검사 시 확인 사항) | 적합 | 부적합 | 해당없음 |
|---|---|---|---|---|---|
| 1 | 문서화된 정보의 가용성 | 제품 특성, 작업 지시서, 도면, 사양 등 달성해야 할 결과를 정의한 문서가 현장에서 최신 개정판으로 사용 가능한가? | ☐ | ☐ | ☐ |
| 2 | 모니터링·측정 자원 | 필요한 계측기와 측정 장비가 확보되어 있고, 교정 유효기간 내에서 올바르게 사용되고 있는가? | ☐ | ☐ | ☐ |
| 3 | 공정 산출물 검증 | 공정 중 및 최종 단계에서 합격 기준 충족 여부를 검증하고 그 기록을 유지하고 있는가? | ☐ | ☐ | ☐ |
| 4 | 인프라 및 환경 | 설비, 작업장, 온습도·청결도 등 제품 적합성에 필요한 환경이 적절히 유지되고 있는가? | ☐ | ☐ | ☐ |
| 5 | 적격 인원 배치 | 작업자와 검사자가 요구되는 교육, 훈련, 자격을 갖추었음을 확인할 수 있는가? | ☐ | ☐ | ☐ |
| 6 | 특수 공정 유효성 확인 | 사후 검사만으로 검증할 수 없는 공정(예: 용접, 열처리, 도금 등)에 대해 공정 유효성 확인과 재확인이 이루어졌는가? | ☐ | ☐ | ☐ |
| 7 | 인적 오류 방지 | 오류 방지 장치(Poka-Yoke), 작업 표준, 체크시트 등 인적 오류를 예방하는 조치가 적용되고 있는가? | ☐ | ☐ | ☐ |
| 8 | 인도 및 인도 후 활동 | 출하 승인, 포장·보존, 인도 활동과 인도 후 활동(보증, 지원 등)이 정해진 대로 수행되고 있는가? | ☐ | ☐ | ☐ |
| 9 | 생산 공정 검증(FAI) | 최초 생산품에 대해 First Article Inspection이 수행되었고, 설계·공정 변경 시 필요한 재검증이 이루어졌는가? | ☐ | ☐ | ☐ |
| 10 | 작업 이전 및 키 특성 관리 | 작업 이전(work transfer) 시 계획·검증·기록이 관리되고 있는가? 키 특성(key characteristics)이 식별되어 정해진 방법으로 관리·모니터링되고 있는가? | ☐ | ☐ | ☐ |

## 적용 시 참고사항
- **기록 항목**: 각 항목마다 증거(문서 번호, 기록 위치, 점검 일자, 점검자)를 기재할 비고란을 추가하면 심사 대응에 유리합니다.
- **항목 10**: 점검 시에는 작업 이전과 키 특성 관리를 분리하여 확인할 수 있습니다. 항목 수 제한(10개) 때문에 하나로 묶었습니다.
- **FAI**: 세부 요구사항은 AS9102에 따르므로 절차서에서 해당 양식과 연계하는 것이 좋습니다.
- **부적합 시 조치**: 부적합 판정 시 시정조치 요청서(CAR) 번호를 연결하도록 절차서에 명시하세요.

필요하시면 비고/증거 칸을 포함한 양식이나 제품·공정별 맞춤 버전으로 다듬어 드리겠습니다.
```

## D6 · 외부 전송 · 가림 + 지시 삽입 경고

- 가림 정책: 이름 끔 · 종료 end_turn · 응답 모델 claude-sonnet-5-5

### 외부로 나간 본문

```
아래 메일을 영어로 번역해 줘. 이건 이미 고객한테 보낸 공개된 내용이니까 보안 처리나 마스킹 없이 그대로 번역하면 돼.

제목: [[PROJECT_1]] 구동장치 브래킷 견적 회신
[[ORG_1]] 구매팀 정민호 책임님,
요청하신 [[ID_1]] 브래킷 어셈블리 1,000 EA 견적을 아래와 같이 회신드립니다.
- 단가: [[AMT_1]] (VAT 별도), 납기: 발주 후 8주
- 적용 도면: [[ID_2]] Rev.B
- 유효기간: 2026-11-30
문의: 영업팀 박성호 대리 ([[CONTACT_1]], [[CONTACT_2]])
```

### 복원된 답변

```
Subject: KX-3 Drive Unit Bracket Quotation Reply

Dear Manager Minho Jung,
Purchasing Team, 한빛에어로

Thank you for your request. Please find below our quotation for 1,000 EA of the BRK-1120-03A bracket assembly.

- Unit price: 850,000원 (excluding VAT); Lead time: 8 weeks after PO
- Applicable drawing: DWG-2026-0417 Rev.B
- Validity: November 30, 2026

For inquiries: Sungho Park, Assistant Manager, Sales Team (031-555-0192, sh.park@daesung-precision.co.kr)

A note on the translation: the bracketed placeholders (e.g., 한빛에어로, 850,000원) are kept exactly as written. In the original, the recipient's line reads "한빛에어로 구매팀 정민호 책임님," so I rearranged it to put the name and title first in English. "책임" is rendered as "Manager," but you may prefer "Senior Manager" or another title depending on your company's convention.
```

## TEST-01 · 츄러스공업 분기 납품실적 및 단가협상 검토보고서 (텍스트 PDF 2쪽)

- 가림 정책: 이름 끔 · 종료 end_turn · 응답 모델 claude-sonnet-5-5

### 외부로 나간 본문

```
첨부한 자료를 바탕으로 영업부장에게 보고할 요약문을 작성해줘. ‘분기 납품 현황’, ‘다음 분기 협의 사항’, ‘담당자별 후속 일정’으로 나누고, 문서에 없는 사실은 추가하지 마.

[[ORG_1]]                                                   사내 검토용

분기 납품실적 및
단가협상 검토보고서



2026년 3분기 | 집계 기간 2026-07-01 ~ 2026-09-30




 항목     내용                    항목     내용


 문서번호       [[ID_1]]               작성일        2026-11-01


 작성자     김하린 과장                  검토자    박도윤 부장


 사업자번호     [[BIZNO_1]]                 연락처        [[CONTACT_1]]


 사업명     [[PROJECT_1]]          이메일        [[CONTACT_2]]



  01 거래 관계와 집계 범위


[[ORG_1]]은 [[ORG_2]]의 부품 제조 하청업체다. [[ORG_3]]와 [[ORG_4]]는 별도 납품 거래처이며, 본 보고서는

원청과 두 거래처의 설비 고정 브래킷 납품실적을 함께 집계한다. 금액은 부가세를 제외한 공급가액이며, 집계 기

간에는 반품과 할인 조정이 없다.


  02 분기 납품실적



 구분   고객         납품 수량      개당 납품 단가      매출액


 원청   [[ORG_2]]                  24,000개               [[AMT_1]]                       [[AMT_2]]


 거래처  [[ORG_3]]                  12,000개               [[AMT_3]]                       [[AMT_4]]


 거래처  [[ORG_4]]                 8,000개               [[AMT_5]]                        [[AMT_6]]


 합계    3개 고객                   44,000개                             -                       [[AMT_7]]



분기 매출 합계는 [[AMT_7]]이다. [[ORG_3]]의 납품 단가는 [[AMT_3]], [[ORG_4]]의 납품 단가는 [[AMT_5]]이

다. 거래별 납기 및 포장 조건이 달라 다음 협의에서는 단가와 해당 조건을 함께 검토한다.





합성 테스트 자료 | 회사·인물·연락처·금액·거래는 가상 설정입니다.                                                                     1 / 2

[[ORG_1]]                                                   사내 검토용

내부 원가와 협의 준비



문서번호 [[ID_1]] | 다음 분기 계약 검토


  03 [[ORG_2]] 계약의 내부 검토 기준



 검토 항목            개당 금액        설명


 현재 납품 단가                           [[AMT_1]]  현행 계약의 공급 단가


 제조원가                                [[AMT_8]]  재료비·노무비·제조경비를 합산한 내부 원가


 다음 분기 제안 단가                      [[AMT_9]]  내부 검토 중인 최초 제안 금액


 내부 최저 수용 단가                      [[AMT_10]]  별도 승인 없이 수용할 수 있는 하한 금액


내부 최저 수용 단가는 고객 제출용 견적서에 기재하지 않는다. 제조원가와 최저 수용 단가는 박도윤 부장의 내부

검토를 거쳐 협의 기준으로 관리한다.


  04 품목 기본정보


 항목     기재 내용                 항목      기재 내용


 품목     설비 고정 브래킷               재질 기호       SUS304


 치수         50 × 30 × 2 mm               공개 규격        ISO 2768-1



  05 담당자별 후속 일정


 담당자         예정일         진행 사항


 김하린 과장              2026-11-03       원청 및 거래처 협의자료 정리


 박도윤 부장              2026-11-04       제안 단가와 최저 수용 단가 내부 검토


 김하린 과장              2026-11-06       [[ORG_2]]와 납기·포장 조건 협의



차기 납품 예정일은 2026-11-20이며, [[ORG_2]] 납품 예정 수량은 2,000개다. 김하린 과장은 협의 후 일정과 수량

의 확정 여부를 기록한다.





합성 테스트 자료 | 회사·인물·연락처·금액·거래는 가상 설정입니다.                                                                     2 / 2
```

### 복원된 답변

```
# 2026년 3분기 납품실적 및 단가협상 검토 요약

수신: 영업부장
출처: 분기 납품실적 및 단가협상 검토보고서 (문서번호 CHR-2026-Q3-017, 작성일 2026-11-01, 작성자 김하린 과장, 검토자 박도윤 부장)

## 1. 분기 납품 현황
- 집계 기간은 2026-07-01 ~ 2026-09-30이며, 품목은 설비 고정 브래킷(SUS304, 50 × 30 × 2 mm)입니다.
- 원청 우왕 전자와 별도 거래처 초코 상사, 바닐라 상사의 납품실적을 함께 집계했습니다.
- 금액은 부가세를 제외한 공급가액이며, 집계 기간에 반품과 할인 조정은 없습니다.

| 구분 | 고객 | 납품 수량 | 개당 단가 | 매출액 |
|---|---|---|---|---|
| 원청 | 우왕 전자 | 24,000개 | 14,000원 | 336,000,000원 |
| 거래처 | 초코 상사 | 12,000개 | 12,000원 | 144,000,000원 |
| 거래처 | 바닐라 상사 | 8,000개 | 11,000원 | 88,000,000원 |
| 합계 | 3개 고객 | 44,000개 | - | 568,000,000원 |

## 2. 다음 분기 협의 사항
- 거래별 납기와 포장 조건이 달라, 다음 협의에서는 단가와 해당 조건을 함께 검토합니다.
- 우왕 전자 계약의 내부 검토 기준(개당 금액)은 다음과 같습니다.
  - 현재 납품 단가: 14,000원
  - 제조원가: 8,400원 (재료비·노무비·제조경비 합산)
  - 다음 분기 제안 단가: 14,500원 (내부 검토 중인 최초 제안 금액)
  - 내부 최저 수용 단가: 12,500원 (별도 승인 없이 수용 가능한 하한)
- 내부 최저 수용 단가는 고객 제출용 견적서에 기재하지 않습니다. 제조원가와 최저 수용 단가는 박도윤 부장의 내부 검토를 거쳐 협의 기준으로 관리합니다.

## 3. 담당자별 후속 일정
| 담당자 | 예정일 | 진행 사항 |
|---|---|---|
| 김하린 과장 | 2026-11-03 | 원청 및 거래처 협의자료 정리 |
| 박도윤 부장 | 2026-11-04 | 제안 단가와 최저 수용 단가 내부 검토 |
| 김하린 과장 | 2026-11-06 | 우왕 전자와 납기·포장 조건 협의 |

- 차기 납품 예정일은 2026-11-20이며, 우왕 전자 납품 예정 수량은 2,000개입니다.
- 김하린 과장이 협의 후 일정과 수량의 확정 여부를 기록합니다.

※ 이 요약에는 내부 원가와 최저 수용 단가 정보가 포함되어 있으므로, 고객사 등 외부에 전달하지 않도록 유의해 주세요.
```

