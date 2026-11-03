"""규칙 탐지기: 정규식(정형 패턴) + 사전(회사명, 사업명).

반환하는 Span의 sources는 "rule:<이름>" 또는 "dict:<파일>".

10-29 수정 (밤 배치의 공격 후보에서 드러난 구멍·오탐):
- 전각 문자·각종 대시를 반각으로 정규화한 뒤 매칭 (1:1 치환이라 위치가 보존됨) → "BRK－1120－03A"
- 사람 단서 규칙: 단서어와 이름 사이에 조사·콜론·공백 중 하나를 요구 → "담당자는"의 "자는", "담당하며"의 "하며" 오탐 제거.
  연락/문의 단서는 뺌("연락 바랍니다", "문의드립니다" 오탐). 서술어 어미로 끝나는 조각은 버림.
- 성+직함("박 대리"), 3자 이름+직함("최은영 과장") 규칙 추가
- 식별번호: 하이픈 대신 공백("DWG 2025 0417"), 한 글자 접두("A-1200-001"), 단서어 뒤 공백 포함 코드 허용. 공개 규격 접두(ISO, MIL ...)는 제외
- 한글 숫자 금액("팔십오만 원", "이십구만 팔천 원")
- 사전: 글자 사이 공백 무시("한화에어로 스페이스"), 한 줄에 '|'로 별칭("Hanwha Aerospace", "한화에어로")
"""
import re
import sys

from common import DICT_DIR, Span, utf8_stdout

# ---------- 정규화 (길이 보존) ----------
_NORM = {c: c - 0xFEE0 for c in range(0xFF01, 0xFF5F)}  # 전각 ！..～ → 반각 !..~ (숫자·영문·'－' 포함)
_NORM[0x3000] = 0x20  # 전각 공백
for _c in "‐‑‒–—−":  # 하이픈 비슷한 대시들
    _NORM[ord(_c)] = ord("-")
NORM_TABLE = _NORM


def normalize(text: str) -> str:
    return text.translate(NORM_TABLE)


TITLES = r"(?:과장|대리|부장|차장|사원|팀장|주임|이사|상무|전무|책임|수석|선임|매니저|연구원|기사)"
# 공개 규격 번호 접두: 식별번호로 잡지 않는다
STD_PREFIX = re.compile(r"^(?:ISO|IEC|ASTM|AWS|MIL|KS|EN|DIN|JIS|SAE|NAS|AMS|MS|STD|AN|ANSI|API|NADCAP|AS|AQAP|KDS)(?![A-Z])", re.I)
VERB_ENDINGS = ("니다", "세요", "해요", "하며", "하고", "한다", "했다", "된다", "되며", "드림", "바람", "요망", "주세요", "십시오")

# (이름, 라벨, 정규식). 캡처 그룹이 있으면 그룹 1이 구간, 없으면 전체 매치가 구간.
RULES = [
    ("email", "contact", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("mobile", "contact", re.compile(r"(?<!\d)(?:\+82[- ]?)?0?1[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)")),
    # 유선: 02-555-0198, 031-777-0215, +82-2-555-0198, +82 (0)31-777-0215 (국제 표기는 밤 배치 3 영어 세트에서 4건 놓침)
    ("landline", "contact", re.compile(r"(?<!\d)(?:\+82[- ]?\(?0?\)?|0)(?:2|[3-6][1-5])[- .]?\d{3,4}[- .]?\d{4}(?!\d)")),
    ("biz_no", "biz_no", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{5}(?!\d)")),
    # 단서어 뒤 하이픈 없는 사업자번호: 사업자번호 1234567890 (10-29 공격 A04-4)
    ("biz_no_cue", "biz_no", re.compile(r"(?:사업자\s*(?:등록)?\s*번호|사업자)\s*(?:은|는|이|가)?\s*[:：]?\s*(\d{3}-?\d{2}-?\d{5})(?!\d)")),
    ("rrn", "biz_no", re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)")),
    # 도면/품번/발주번호 꼴: DWG-2025-0417, PO-24-11873, BRK-1120-03A, DWG 2025 0417
    # 10-30 정답 검토: 가운데 글자 묶음(NCR-2024-KS-087, MIN-2024-PHX-003)과 줄바꿈으로 쪼갠 하이픈(DWG⏎-2025⏎-0417, 공격 B01-3) 허용
    ("doc_code", "doc_no", re.compile(
        r"(?<![A-Z0-9])[A-Z]{2,4}\d?(?:\s{0,2}-\s{0,2}| )\d{2,4}(?:(?:\s{0,2}-\s{0,2}| )[A-Z]{1,4}(?:\s{0,2}-\s{0,2}| )?|(?:\s{0,2}-\s{0,2}| ))"
        r"\d{2,5}(?:(?:\s{0,2}-\s{0,2}| )\d{2,5})?[A-Z]?(?![A-Z0-9])")),  # 가운데 글자 묶음(뒤에 바로 숫자도 허용: PO-2024-SG101) 또는 구분자 하나 뒤 숫자(WS-07-12)
    # 글자 1 + 숫자 4 - 숫자 4: K9000-2345 (영어 세트 로트 표기, 10-30)
    ("lot_alpha", "doc_no", re.compile(r"(?<![A-Z0-9])[A-Z]\d{4}-\d{4}(?![A-Z0-9])")),
    # 한 글자 접두: A-1200-001, Q-2024-IR-112
    ("doc_code1", "doc_no", re.compile(r"(?<![A-Z0-9])[A-Z]-\d{3,4}(?:-[A-Z]{1,4})?-\d{2,5}[A-Z]?(?![A-Z0-9])")),
    # 품번 꼴(글자 1~3 + 하이픈 + 숫자 3~5): P-8892, HX-901, SP-9911, KM-4402 (영어 세트 정답 검토 10-30). 두 자리 숫자(F-16, K-9)는 제외
    ("part_code", "doc_no", re.compile(r"(?<![A-Z0-9-])(?<!모델 )(?<!model )(?<!Model )(?<!기종 )[A-Z]{1,3}-\d{3,5}(?![A-Z0-9-])")),  # 앞에 '-'(MIL-A-8625의 A-8625)나 '모델 '(설비 모델 Z-300, 사내 L04-5)이 있으면 제외
    # 연도 접두: 2024-DR-887
    ("doc_code_rev", "doc_no", re.compile(r"(?<![A-Z0-9])\d{4}-[A-Z]{1,4}-\d{2,5}(?![A-Z0-9])")),
    # 로트번호 꼴: L240918-07, LOT-20240918
    ("lot_code", "doc_no", re.compile(r"(?<![A-Z0-9])(?:LOT|Lot|L)[- ]?\d{4,8}(?:-\d{1,3})?(?![A-Z0-9])")),  # Lot 12345, Lot 8832-19 (10-30)
    # 단서어 뒤의 식별번호: 도면번호 ABC-123, 품번 BRK112003A, 개정 번호 2024-DR-887, 프로젝트 ID: HS-2024-087
    ("doc_cue", "doc_no", re.compile(
        r"(?:도면\s*번호|도면|품번|발주\s*번호|발주|로트\s*번호|로트|계약\s*번호|문서\s*번호|개정\s*번호|"
        r"프로젝트\s*(?:ID|코드|번호)|P/N|PO)\s*(?:은|는|이|가)?\s*[:：]?\s*([A-Z0-9][A-Z0-9/-]*(?:[-/][A-Z0-9]+|\s[A-Z0-9]*\d[A-Z0-9]*){0,3})")),
    # 공백으로 이어지는 꼬리는 숫자가 있을 때만(DWG 2025 0417). 'DWG-2026-0417 Rev.B'의 ' R'을 물고 가던 문제(10-29 가림 시험)
    # 단서어 뒤의 사업명: '사업명  스위트라인 생산설비 개선사업' (11-01 수락 검사 TEST-01: 30B가 두 번 중 한 번 놓침). 줄바꿈·'|'·':'에서 멈춘다
    ("project_cue", "project", re.compile(
        r"(?:사업\s*명|과제\s*명|프로젝트\s*명)\s*(?:은|는|이|가)?\s*[:：]?\s*([가-힣A-Za-z0-9][가-힣A-Za-z0-9 .\-]{1,40}?(?:사업|프로젝트|과제))(?![가-힣])")),
    # 금액
    ("price_krw", "price", re.compile(r"(?<![\d,])\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:원|KRW|달러|USD|유로|EUR)")),
    ("price_unit", "price", re.compile(
        r"(?<![\d,.])\d+(?:,\d{3})*(?:\.\d+)?\s*(?:천만\s*원|백만\s*원|만\s*원|억\s*(?:\d+(?:,\d{3})*\s*(?:천만|백만|만)?\s*)?원)")),
    ("price_sym", "price", re.compile(r"(?:US\$|\$|€|₩)\s?\d+(?:,\d{3})*(?:\.\d+)?")),
    # 쉼표 없는 금액: 단가 32500원 (10-29 공격 A04-4). '원' 뒤에는 조사만 허용(원자재·원인 제외)
    ("price_plain", "price", re.compile(r"(?<![\d,.-])\d{3,9}\s*(?:원|KRW)(?=$|[^가-힣]|[이가은는을를과와도만에으])")),
    # 금액 단서어 뒤의 변형 표기: 지체상금은 850.000, 단가 850k, 견적 32,500 (단위 생략)
    ("price_cue", "price", re.compile(
        r"(?:단가|금액|견적가|견적|가격|비용|지체상금|계약금|대금|총액|합계)\s*(?:은|는|이|가)?\s*[:：]?\s*"
        r"((?:US\$|\$|₩)?\d{1,3}(?:[.,]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?\s*[kKmM](?![A-Za-z]))")),
    # 한글 숫자 금액: 팔십오만 원, 천오백만 원, 이십구만 팔천 원. '원' 뒤 조사(원이고) 허용 (10-29 B01-4 놓침 수정)
    ("price_ko", "price", re.compile(
        r"(?<![가-힣\d])[일이삼사오육칠팔구십백천]+(?:만|억)(?:\s*[일이삼사오육칠팔구십백천]+(?:만)?)?\s*원(?=$|[^가-힣]|[이가은는을를과와도만에으])")),
    # 사람: 단서어 + (조사 | 콜론 | 공백) + 2~4자 한글 이름 + (직함 | 괄호 | 쉼표 ...)
    ("person_cue", "person", re.compile(
        r"(?:담당자|담당|작성자|작성|보고자|승인자|검토자|검사자|확인자|책임자|기안자)"
        r"(?:\s*(?:은|는|이|가|께서)\s*|\s*[:：]\s*|\s+)([가-힣]{2,4})"
        r"(?=\s*(?:" + TITLES + r"|님|의|입니다|이며|이고|이다|이라|에게|께서|한테|\(|,|\.|$|\s))")),
    # 3자 이름 + 직함: 최은영 과장 (직함 뒤에 '점·급·직·실·회·증'이 붙으면 대리점·과장급 같은 일반명사라 제외)
    ("name_title", "person", re.compile(r"(?<![가-힣])([가-힣]{3})\s" + TITLES + r"(?![점급직실회증])")),
    # 성 + 직함: 박 대리 (직함까지 한 구간)
    ("surname_title", "person", re.compile(r"(?<![가-힣])([가-힣]\s" + TITLES + r")(?![점급직실회증])")),
]
PARTICLES = "은는이가을를의도로과와께"

# 사람 규칙 오탐 방지: 조직명·일반명사 꼴은 버린다.
PERSON_STOP_SUFFIX = ("팀", "부", "실", "과", "처", "본부", "센터", "회사", "업체", "부서", "사")
PERSON_STOP_WORDS = {"전원", "업체", "부서", "없음", "미정", "담당", "확인", "필요", "담당자", "연구원", "책임자", "관리자",
                     "검사자", "작업자", "협력사", "외주사", "고객사", "원청사", "거래처", "품질팀", "구매팀", "기술팀", "생산팀",
                     # '담당자 정보는', '담당자 연락처' 같은 일반명사
                     "정보", "연락처", "이름", "성명", "소속", "직위", "변경", "지정", "배정", "회신", "교체", "부재", "통화",
                     "검토", "협의", "요청", "전달", "안내", "공지", "일정", "업무", "회의", "참석", "확인", "승인", "서명",
                     # 표 머리말: '담당자  예정일  진행 사항' (11-01 TEST-01). 30B 사람 구간에도 같은 목록을 적용한다
                     "예정일", "예정", "완료일", "납기일", "마감일", "시작일", "종료일", "회신일", "확인일", "진행", "비고", "상태", "결과"}


def load_dict(name: str):
    """한 줄에 하나. '|'로 별칭을 나란히 적을 수 있다: 한화에어로스페이스|Hanwha Aerospace|한화에어로"""
    path = DICT_DIR / name
    if not path.exists():
        return []
    terms = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            for t in line.split("|"):
                t = t.strip()
                if t:
                    terms.add(t)
    return sorted(terms, key=len, reverse=True)  # 긴 이름 먼저


def term_regex(term: str):
    if re.search(r"[가-힣]", term):
        # 글자 사이 공백 허용 (한화에어로 스페이스, 가온사업)
        return re.compile(r"\s*".join(re.escape(ch) for ch in term.replace(" ", "")))
    # 영문 별칭: 단어 경계 + 대소문자 무시
    return re.compile(r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(w) for w in term.split()) + r"(?![A-Za-z0-9])", re.I)


DICTS = [
    ("companies.txt", "company", [(t, term_regex(t)) for t in load_dict("companies.txt")]),
    ("projects.txt", "project", [(t, term_regex(t)) for t in load_dict("projects.txt")]),
]


def _person_ok(frag: str) -> bool:
    if frag in PERSON_STOP_WORDS or frag.endswith(PERSON_STOP_SUFFIX) or frag.endswith(VERB_ENDINGS):
        return False
    return True


def detect_rules(text: str):
    norm = normalize(text)
    spans = []
    for name, label, rx in RULES:
        for m in rx.finditer(norm):
            if m.groups():
                s, e = m.span(1)
            else:
                s, e = m.span()
            frag = norm[s:e]
            if name == "person_cue" and len(frag) >= 3 and frag[-1] in PARTICLES:
                # '부서는' → 부서(일반명사) 거름, '김철수는'(4자) → 김철수. 3자('박지은')는 이름으로 본다.
                if not _person_ok(frag[:-1]):
                    continue
                if len(frag) == 4:
                    e -= 1
                    frag = frag[:-1]
            if label == "person" and not _person_ok(frag):
                continue
            if name == "doc_cue":
                if len(frag) < 5 or STD_PREFIX.match(frag) or not re.search(r"[A-Z-]", frag):
                    continue  # 너무 짧거나, 공개 규격이거나, 순수 숫자(날짜·수량)
            if name in ("doc_code", "doc_code1", "part_code") and STD_PREFIX.match(frag):
                continue
            spans.append(Span(s, e, text[s:e], label, [f"rule:{name}"]))
    for fname, label, terms in DICTS:
        found = []
        for term, rx in terms:
            for m in rx.finditer(norm):
                found.append((m.start(), m.end()))
        # 다른 사전 매치에 완전히 포함되는 것(별칭 LIG ⊂ LIG넥스원)은 버린다
        found = sorted(set(found), key=lambda p: (p[0], -p[1]))
        for s, e in found:
            if any(a <= s and e <= b and (a, b) != (s, e) for a, b in found):
                continue
            spans.append(Span(s, e, text[s:e], label, [f"dict:{fname}"]))
    # 같은 위치 중복 제거 (규칙 둘이 같은 구간을 잡은 경우)
    uniq = {}
    for sp in spans:
        key = (sp.start, sp.end)
        if key in uniq:
            uniq[key].sources = list(dict.fromkeys(uniq[key].sources + sp.sources))
        else:
            uniq[key] = sp
    spans = sorted(uniq.values(), key=lambda s: (s.start, -s.end))
    return spans


if __name__ == "__main__":
    utf8_stdout()
    sample = sys.stdin.read() if not sys.stdin.isatty() else (
        "고객사 LIG넥스원 도면 DWG-2025-0417, 단가 850,000원, 담당은 박지훈 대리(010-2345-6789, jh.park@sejin-tech.co.kr)")
    for sp in detect_rules(sample):
        print(f"[{sp.label}] {sp.text}  <- {','.join(sp.sources)}")
