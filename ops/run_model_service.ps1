# 모델 서비스(src/server.py, FastAPI 8010)를 띄우고 끝날 때까지 기다린다. 작업 스케줄러 'Woowang Model Service' 가 부팅 때 실행한다.
# 키·경로는 service.env 에서 읽어 환경변수로 넘긴다(저장소·로그에 키를 남기지 않는다).
# Ollama 를 최대 120초 기다리되, 안 떠도 서비스는 축소 모드(degraded)로 띄운다. 서버가 끝나면 1 로 종료해 재시작되게 한다.
param([string]$ConfigDir)

. (Join-Path $PSScriptRoot 'common.ps1')
$ConfigDir = Get-OpsConfigDir $ConfigDir
$cfg = Read-OpsConfig $ConfigDir

$server = Join-Path $cfg.REPO_DIR 'src\server.py'
foreach ($need in @($cfg.PYTHON_EXE, $server)) {
    if (-not (Test-Path $need)) {
        Write-OpsLog $ConfigDir 'ops.log' ("service 시작 실패: 파일 없음 " + $need)
        exit 1
    }
}
if (Test-OpsService $cfg -TimeoutSec 3) {
    Write-OpsLog $ConfigDir 'ops.log' ("service 이미 응답 중이라 새로 띄우지 않음 (" + (Get-OpsServiceUrl $cfg) + ")")
    exit 0
}

Set-OpsProcessEnv $cfg
$ollamaUp = Wait-OpsUntil -Seconds 120 -StepSec 3 -Condition { Test-OpsOllama $cfg }
if (-not $ollamaUp) { Write-OpsLog $ConfigDir 'ops.log' 'service: Ollama 가 120초 안에 안 떠서 축소 모드로 시작' }

Remove-OpsOldLogs $ConfigDir 'service' ([int]$cfg.LOG_KEEP)
$log = New-OpsLogPath $ConfigDir 'service'
$keyState = 'service.env 키 없음(서버가 임시 키 생성)'
if ($cfg.MODEL_API_KEYS) { $keyState = 'service.env 키 사용' }
$extState = '없음'
if ($cfg.ANTHROPIC_API_KEY) { $extState = '있음' }
Write-OpsLog $ConfigDir 'ops.log' ("service 시작: {0}:{1} user={2} repo={3} api_key={4} anthropic_key={5} log={6}" -f `
    $cfg.MODEL_HOST, $cfg.MODEL_PORT, $env:USERNAME, $cfg.REPO_DIR, $keyState, $extState, (Split-Path -Leaf $log))

$pyArgs = @('-X', 'utf8', ('"' + $server + '"'), '--host', $cfg.MODEL_HOST, '--port', $cfg.MODEL_PORT, '--log-level', $cfg.MODEL_LOG_LEVEL)
$p = Start-Process -FilePath $cfg.PYTHON_EXE -ArgumentList $pyArgs -WorkingDirectory $cfg.REPO_DIR -NoNewWindow -PassThru `
    -RedirectStandardError $log -RedirectStandardOutput ($log -replace '\.log$', '.out.log')
$null = $p.Handle
Set-Content -Path (Join-Path $ConfigDir 'service.pid') -Value $p.Id
$p.WaitForExit()
Write-OpsLog $ConfigDir 'ops.log' ("service 종료: code={0}" -f $p.ExitCode)
Remove-Item (Join-Path $ConfigDir 'service.pid') -Force -ErrorAction SilentlyContinue
exit 1
