# 코드나 설정을 바꾼 뒤 서비스(또는 Ollama)를 다시 띄운다. 관리자 PowerShell 에서 실행한다.
#   powershell -ExecutionPolicy Bypass -File ops\restart.ps1            # 모델 서비스만
#   powershell -ExecutionPolicy Bypass -File ops\restart.ps1 -Ollama    # Ollama 와 모델 서비스 둘 다
# 작업 스케줄러의 '끝내기'는 래퍼만 끝내고 python/ollama 자식을 남길 수 있어, 프로세스까지 정리한 뒤 작업을 다시 시작한다.
param([string]$ConfigDir, [switch]$Ollama)

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'common.ps1')
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ConfigDir = Get-OpsConfigDir $ConfigDir
$cfg = Read-OpsConfig $ConfigDir

function Restart-One { param([string]$Name, [string]$Kind)
    if (-not (Get-OpsTask $Name)) { Write-Output ("작업 없음: " + $Name); return }
    Stop-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $Name -ErrorAction SilentlyContinue
    $killed = Stop-OpsProcesses $ConfigDir $Kind
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $Name
    Write-OpsLog $ConfigDir 'watchdog.log' ("수동 재시작: {0} (끝낸 프로세스 {1})" -f $Name, $killed)
    Write-Output ("다시 시작: {0} (끝낸 프로세스 {1})" -f $Name, $killed)
}

if ($Ollama) {
    Restart-One $script:OpsTaskService 'service'
    Restart-One $script:OpsTaskOllama 'ollama'
    Write-Output ("Ollama 응답: {0}" -f (Wait-OpsUntil -Seconds 60 -StepSec 2 -Condition { Test-OpsOllama $cfg }))
} else {
    Restart-One $script:OpsTaskService 'service'
}
Write-Output ("모델 서비스 /health: {0}" -f (Wait-OpsUntil -Seconds 180 -StepSec 3 -Condition { Test-OpsService $cfg }))
