# Ollama 서버를 전면에서 띄우고 끝날 때까지 기다린다. 작업 스케줄러 'Woowang Ollama' 가 부팅 때 실행한다.
# 트레이 앱(ollama app.exe) 대신 ollama.exe serve 를 직접 돌리므로 자동 업데이트가 없고, 로그인 없이도 뜬다.
# 서버가 끝나면 1 로 종료해 작업 스케줄러의 '실패 시 다시 시작' 이 다시 띄우게 한다.
param([string]$ConfigDir)

. (Join-Path $PSScriptRoot 'common.ps1')
$ConfigDir = Get-OpsConfigDir $ConfigDir
$cfg = Read-OpsConfig $ConfigDir

if (-not (Test-Path $cfg.OLLAMA_EXE)) {
    Write-OpsLog $ConfigDir 'ops.log' ("ollama 시작 실패: 실행 파일 없음 " + $cfg.OLLAMA_EXE)
    exit 1
}

# 이미 떠 있으면(트레이 앱 등) 또 띄우지 않는다. 포트 충돌로 바로 죽고 재시작을 반복하는 것을 막는다.
if (Test-OpsOllama $cfg) {
    Write-OpsLog $ConfigDir 'ops.log' 'ollama 이미 응답 중이라 새로 띄우지 않음 (다른 프로세스가 11434 사용)'
    exit 0
}

Set-OpsProcessEnv $cfg
Remove-OpsOldLogs $ConfigDir 'ollama' ([int]$cfg.LOG_KEEP)
$log = New-OpsLogPath $ConfigDir 'ollama'
Write-OpsLog $ConfigDir 'ops.log' ("ollama 시작: user={0} profile={1} models={2} log={3}" -f $env:USERNAME, $env:USERPROFILE, $cfg.OLLAMA_MODELS, (Split-Path -Leaf $log))

# Ollama 는 로그를 stderr 로 쓴다. stdout 은 거의 비어 있어 .out.log 로 따로 둔다.
$p = Start-Process -FilePath $cfg.OLLAMA_EXE -ArgumentList 'serve' -NoNewWindow -PassThru `
    -RedirectStandardError $log -RedirectStandardOutput ($log -replace '\.log$', '.out.log')
$null = $p.Handle
Set-Content -Path (Join-Path $ConfigDir 'ollama.pid') -Value $p.Id
$p.WaitForExit()
Write-OpsLog $ConfigDir 'ops.log' ("ollama 종료: code={0}" -f $p.ExitCode)
Remove-Item (Join-Path $ConfigDir 'ollama.pid') -Force -ErrorAction SilentlyContinue
exit 1
