# 집 PC 상시 가동 (ops)

집 PC의 Ollama(11434)와 모델 서비스(FastAPI 8010)가 재부팅·절전·Windows 업데이트 뒤에도 사람 개입 없이 떠 있게 하는 스크립트 묶음이다.
모델 코드와 무관하므로 `src/` 가 바뀌어도 그대로 쓴다. 백엔드가 연동하는 동안과 심사 기간(11-15 ~ 11-21)에 켜 둔다.

## 구성

| 작업 스케줄러 (`\Woowang\`) | 언제 | 하는 일 |
|---|---|---|
| Woowang Ollama | 부팅 30초 뒤 | `ollama.exe serve` 를 직접 띄운다(트레이 앱 아님). 죽으면 1분 뒤 재시작 |
| Woowang Model Service | 부팅 45초 뒤 | Ollama 를 최대 120초 기다린 뒤 `src/server.py` 를 띄운다. 죽으면 1분 뒤 재시작 |
| Woowang Watchdog | 부팅 3분 뒤, 이후 5분마다 | 두 서버 응답 확인 → `heartbeat.csv` 기록 → 무응답이면 작업 재시작 → 모델이 내려가 있으면 예열 |

세 작업 모두 **로그인 없이** 사용자 계정으로 돈다(S4U: 암호를 저장하지 않는 "로그온 여부와 관계없이 실행").
서버 둘은 일반 권한, 감시는 작업을 멈추고 띄워야 해서 최고 권한이다.

| 파일 | 역할 |
|---|---|
| `install_always_on.ps1` | 설치(관리자). 설정 파일 생성, 절전·NIC 전원 관리 끔, Windows 업데이트 일시 중지, 작업 3개 등록, 기동 확인 |
| `uninstall_always_on.ps1` | 제거(관리자). 작업 제거, 트레이 앱 바로가기·업데이트·전원 값 복구 |
| `status.ps1` | 상태 보기(일반 권한). 작업·포트·응답·올라온 모델·heartbeat 요약(끊긴 구간·재시작)·전원·업데이트 |
| `restart.ps1` | 코드·설정을 바꾼 뒤 서비스 재시작(관리자). `-Ollama` 면 Ollama 도 |
| `watchdog.ps1` | 감시 본체. 손으로 돌려도 된다(`-NoRestart` 면 확인·기록만) |
| `run_ollama.ps1`, `run_model_service.ps1` | 작업이 실행하는 래퍼. 환경변수를 설정 파일에서 넘기고 로그를 남긴다 |
| `common.ps1` | 공통 함수(설정 읽기, HTTP, 프로세스 정리) |
| `service.env.example` | 설정 파일 예시. 실제 파일은 아래 위치 |

## 설정·로그 위치 (저장소 밖)

- 설정: `%LOCALAPPDATA%\woowang\service.env` — 키(`MODEL_API_KEYS`), 호스트·포트, 경로, Ollama 환경변수. **커밋하지 않는다.**
- 로그: `%LOCALAPPDATA%\woowang\logs\`
  - `heartbeat.csv` 5분마다 한 줄(시각, 부팅 뒤 분, ollama, service, 올라온 모델, GPU 메모리, 조치, 비고)
  - `watchdog.log` 재시작·예열 기록, `ops.log` 서버 시작·종료 기록
  - `ollama_<시각>.log`, `service_<시각>.log` 서버 출력(최근 10개 보관). 원문은 찍히지 않는다(서버 설계)
- 설치 전 값: `%LOCALAPPDATA%\woowang\install_state.json` (제거 때 복구에 쓴다)

## 설치

```powershell
# 관리자 PowerShell, 저장소 루트에서
powershell -ExecutionPolicy Bypass -File ops\install_always_on.ps1
# 선택: -PauseUpdatesUntil 2026-11-23  -SkipUpdatePause  -SkipPower  -KeepTrayShortcut
```

설치가 하는 시스템 변경(전부 `uninstall_always_on.ps1` 로 되돌릴 수 있다):

1. 절전(AC)·최대 절전(AC)·디스크 끄기(AC) 안 함. 물리 NIC "전원 절약을 위해 끄기" 해제
2. Windows 업데이트를 지정일(기본 11-23, 본선 11-21 다음다음 날)까지 일시 중지(설정 앱의 "업데이트 일시 중지"와 같은 값), 로그온 중 자동 재부팅 금지 정책
3. 시작 폴더의 `Ollama.lnk`(트레이 앱 자동 실행)를 보관 폴더로 옮김 — 작업 스케줄러 Ollama 와 포트가 겹치지 않게
4. 작업 3개 등록 후 기존 Ollama·서비스 프로세스를 끝내고 작업으로 다시 띄움

설치 뒤 **재부팅해서 로그인하지 않은 채** 다른 기기나 로그인 후 `status.ps1` 로 `/health` 가 뜨는지 한 번 확인한다.

## 확인

```powershell
powershell -ExecutionPolicy Bypass -File ops\status.ps1          # 최근 7일
powershell -ExecutionPolicy Bypass -File ops\status.ps1 -Days 1
```

- "끊긴 구간" 이 있으면 그 시간에 PC 가 꺼졌거나 잠든 것이다(부팅 뒤 분이 작아지면 재부팅).
- "재시작" 건수가 늘면 `watchdog.log` 와 그 시각의 `service_*.log` 를 본다.
- 트레이 앱(`ollama app.exe`)이 떠 있다는 경고가 나오면 트레이 앱을 종료한다(작업 Ollama 와 겹친다).

## 운영 중 바꾸기

- 코드 갱신: `git pull` 뒤 `ops\restart.ps1` (관리자). 서비스는 시작할 때만 코드를 읽으므로 작업 폴더를 고쳐도 돌아가는 프로세스는 영향이 없다.
- 설정 변경(키, 호스트): `service.env` 수정 뒤 `ops\restart.ps1`.
- Tailscale 로 열 때: `MODEL_HOST=0.0.0.0`(또는 Tailscale IP)로 바꾸고 재시작. 공유기 포트는 열지 않는다. 백엔드에는 Tailscale 주소와 `MODEL_API_KEYS` 값만 전달한다.
- `MODEL_KEEP_ALIVE=-1` 이라 세 모델이 GPU·메모리에 상주한다(첫 요청 14~17초 재로드 방지). 이 PC 로 다른 GPU 작업을 하려면 `30m` 으로 바꾼다.

## 제거

```powershell
powershell -ExecutionPolicy Bypass -File ops\uninstall_always_on.ps1            # 설정·로그는 남김
powershell -ExecutionPolicy Bypass -File ops\uninstall_always_on.ps1 -RemoveConfig
```

## 주의

- 정전 뒤 자동으로 켜지려면 BIOS 의 "AC 전원 복구 시 전원 켜기(Restore on AC Power Loss)" 를 켜야 한다. OS 에서는 못 바꾼다.
- Windows 업데이트 일시 중지는 최대 35일이다. 11-23 이후에는 설정 앱이 다시 업데이트를 받는다.
- S4U 작업은 네트워크 공유(다른 PC 의 폴더)에 접근하지 못한다. 이 서비스는 로컬 파일과 외부 API 만 쓰므로 문제없다.
- `ollama serve` 를 직접 띄우므로 Ollama 자동 업데이트가 돌지 않는다(심사 기간에 버전이 바뀌지 않는다). 올리려면 제거 → 트레이 앱으로 갱신 → 재설치.
