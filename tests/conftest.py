"""pytest 공통 설정. src 모듈은 서로를 최상위 이름으로 import 하므로 src 를 경로 앞에 둔다.
테스트는 Ollama·GPU·외부 API 없이 순수 함수만 다루고 1초 안에 끝난다 (모델 품질은 src/tools 점검 스크립트가 본다)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("MODEL_API_KEYS", "test-key")   # server 모듈 import 때 임시 키 생성·출력을 막는다
os.environ.setdefault("MODEL_WARM_OLLAMA", "0")
