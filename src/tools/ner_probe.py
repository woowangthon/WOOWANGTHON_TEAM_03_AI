"""공개 한국어 NER 모델 로딩·추론 확인 (CPU). 설치 뒤 한 번 돌려 어떤 모델이 뜨는지, 라벨 이름과 속도를 본다.

사용: python src/tools/ner_probe.py [모델ID ...]
"""
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from common import utf8_stdout  # noqa: E402

DEFAULT_MODELS = ["Leo97/KoELECTRA-small-v3-modu-ner", "monologg/koelectra-base-v3-naver-ner", "atonlee/koelectra-ko-pii-ner"]
SENTS = ["안녕하세요, 품질팀 김지영입니다. 검사 기준서 문의에 답변드립니다.",
         "고객사 (주)한빛에어로 KX-3 구동장치 브래킷(품번 BRK-1120-03A) 단가 850,000원, 담당 박성호 대리 010-4821-7736.",
         "Please translate the NCR for Hanbit Aero. Contact: J. Park, Quality Team, Daesung Precision."]


def main():
    utf8_stdout()
    models = sys.argv[1:] or DEFAULT_MODELS
    import torch  # noqa: F401
    from transformers import pipeline
    for mid in models:
        print(f"\n=== {mid}")
        t0 = time.perf_counter()
        try:
            nlp = pipeline("token-classification", model=mid, aggregation_strategy="simple", device=-1)
        except Exception as e:  # 모델 없음, 변환 실패 등
            print(f"  로딩 실패: {type(e).__name__}: {str(e)[:200]}")
            continue
        print(f"  로딩 {time.perf_counter() - t0:.1f}s · 라벨: {sorted(set(v.split('-')[-1] for v in nlp.model.config.id2label.values()))}")
        for s in SENTS:
            t1 = time.perf_counter()
            ents = nlp(s)
            print(f"  {time.perf_counter() - t1 * 1:.3f}s  " + "; ".join(f"{e['word']}[{e['entity_group']} {e['score']:.2f}]" for e in ents))


if __name__ == "__main__":
    main()
