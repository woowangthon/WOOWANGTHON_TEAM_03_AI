# 집 PC 상시 가동 설치. 관리자 PowerShell 에서 한 번 실행한다. 다시 실행해도 같은 결과(덮어쓴다).
#   powershell -ExecutionPolicy Bypass -File ops\install_always_on.ps1
# 하는 일
#   1) 설정 폴더(%LOCALAPPDATA%\woowang)와 service.env 생성 — 없으면 예시에서 만들고 API 키를 새로 만든다
#   2) 절전(AC) 안 함, 물리 NIC 전원 관리 끔
#   3) Windows 업데이트 일시 중지(-PauseUpdatesUntil, 기본 2026-11-23) + 로그온 중 자동 재부팅 금지
#   4) 시작 폴더의 Ollama 트레이 앱 바로가기를 보관 폴더로 옮김(작업 스케줄러와 겹치지 않게)
#   5) 작업 스케줄러 \Woowang\ 에 3개 등록: Ollama, Model Service(부팅 시, 로그인 불필요, 실패 시 1분 뒤 재시작), Watchdog(5분마다)
#   6) 기존 Ollama·서비스 프로세스를 끝내고 작업으로 다시 띄워 /health·/status 확인
# 되돌리기: uninstall_always_on.ps1. 설치 전 값은 install_state.json 에 적어 둔다.
param(
    [string]$ConfigDir,
    [string]$PauseUpdatesUntil = '2026-11-23',
    [switch]$SkipUpdatePause,
    [switch]$SkipPower,
    [switch]$KeepTrayShortcut
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw '관리자 PowerShell 에서 실행해야 한다 (작업 스케줄러 S4U 등록·전원·업데이트 설정에 필요).' }

$ConfigDir = Get-OpsConfigDir $ConfigDir
$logDir = Join-Path $ConfigDir 'logs'
foreach ($d in @($ConfigDir, $logDir, (Join-Path $ConfigDir 'backup'))) { if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null } }
Start-Transcript -Path (Join-Path $logDir ('install_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))) | Out-Null
$state = @{ installed_at = (Get-Date -Format 's'); config_dir = $ConfigDir }
$stateFile = Join-Path $ConfigDir 'install_state.json'
if (Test-Path $stateFile) {
    # 재설치 때는 처음 설치 전 값을 보존한다(두 번째 설치의 '이전 값'은 이미 바뀐 값이므로)
    $prev = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($k in @('power_before', 'wu_pause_before', 'wu_policy_before', 'ollama_lnk_backup')) {
        if ($prev.PSObject.Properties[$k]) { $state[$k] = $prev.$k }
    }
}

# ---------- 1) 설정 파일 ----------
$envFile = Join-Path $ConfigDir 'service.env'
$repo = Split-Path -Parent $PSScriptRoot
$resolved = @{
    REPO_DIR = $repo
    PYTHON_EXE = (Join-Path $repo '.venv\Scripts\python.exe')
    OLLAMA_EXE = (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe')
    OLLAMA_MODELS = (Join-Path $env:USERPROFILE '.ollama\models')
    HF_HOME = (Join-Path $env:USERPROFILE '.cache\huggingface')
}
# 사용자 환경변수(setx)에 Ollama 값이 있으면 그대로 따른다
foreach ($k in @('OLLAMA_MAX_LOADED_MODELS', 'OLLAMA_CONTEXT_LENGTH', 'OLLAMA_NUM_PARALLEL')) {
    $v = [Environment]::GetEnvironmentVariable($k, 'User')
    if ($v) { $resolved[$k] = $v }
}
$utf8Bom = New-Object Text.UTF8Encoding $true
if (-not (Test-Path $envFile)) {
    $example = Get-Content (Join-Path $PSScriptRoot 'service.env.example') -Raw -Encoding UTF8
    $bytes = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $newKey = 'wk_' + (($bytes | ForEach-Object { $_.ToString('x2') }) -join '')
    $example = $example -replace '(?m)^MODEL_API_KEYS=.*$', ('MODEL_API_KEYS=' + $newKey)
    foreach ($k in $resolved.Keys) { $example = $example -replace ('(?m)^' + $k + '=.*$'), ($k + '=' + $resolved[$k]) }
    [IO.File]::WriteAllText($envFile, $example, $utf8Bom)
    Write-Output ("설정 파일 생성: {0} (MODEL_API_KEYS 를 새로 만들었다. 백엔드 담당에게 이 파일의 값을 안전한 경로로 전달)" -f $envFile)
} else {
    # 있는 파일은 손대지 않고, 경로 키가 비어 있을 때만 채운다
    $text = Get-Content $envFile -Raw -Encoding UTF8
    $added = @()
    foreach ($k in $resolved.Keys) {
        if ($text -notmatch ('(?m)^' + $k + '=\S')) {
            $text = ($text -replace ('(?m)^' + $k + '=\s*$'), '').TrimEnd() + "`r`n" + $k + '=' + $resolved[$k] + "`r`n"
            $added += $k
        }
    }
    if ($added.Count -gt 0) { [IO.File]::WriteAllText($envFile, $text, $utf8Bom); Write-Output ("설정 파일 보완: {0}" -f ($added -join ', ')) }
    Write-Output ("설정 파일 유지: {0}" -f $envFile)
}
$cfg = Read-OpsConfig $ConfigDir
foreach ($need in @($cfg.OLLAMA_EXE, $cfg.PYTHON_EXE, (Join-Path $cfg.REPO_DIR 'src\server.py'), $cfg.OLLAMA_MODELS)) {
    if (-not (Test-Path $need)) { throw ("필요한 경로 없음: " + $need) }
}
if (-not $cfg.ANTHROPIC_API_KEY) { Write-Warning 'ANTHROPIC_API_KEY 를 찾지 못함(service.env 도 사용자 환경변수도 없음). /answer_external 만 503 이 된다.' }

# ---------- 2) 전원 ----------
function Get-PowerAc { param($Sub, $Setting)
    $out = powercfg /query SCHEME_CURRENT $Sub $Setting 2>$null
    $line = ($out | Select-String -Pattern 'AC.*0x[0-9a-fA-F]+' | Select-Object -First 1)
    if ($line) { return [int]('0x' + ($line.Line -replace '.*0x', '')) }
    return -1
}
if (-not $SkipPower) {
    if (-not $state.ContainsKey('power_before')) {
        $state.power_before = @{ standby_ac = (Get-PowerAc 'SUB_SLEEP' 'STANDBYIDLE'); hibernate_ac = (Get-PowerAc 'SUB_SLEEP' 'HIBERNATEIDLE'); disk_ac = (Get-PowerAc 'SUB_DISK' 'DISKIDLE') }
    }
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change hibernate-timeout-ac 0 | Out-Null
    powercfg /change disk-timeout-ac 0 | Out-Null
    Write-Output ("전원: 절전(AC) {0}→0, 최대 절전(AC) {1}→0, 디스크(AC) {2}→0" -f $state.power_before.standby_ac, $state.power_before.hibernate_ac, $state.power_before.disk_ac)
    foreach ($nic in (Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' })) {
        try { Disable-NetAdapterPowerManagement -Name $nic.Name -NoRestart -ErrorAction Stop; Write-Output ("NIC 전원 관리 끔: " + $nic.Name) }
        catch { Write-Warning ("NIC 전원 관리 설정 실패({0}): {1}" -f $nic.Name, $_.Exception.Message) }
    }
} else { Write-Output '전원 설정 건너뜀(-SkipPower)' }

# ---------- 3) Windows 업데이트 ----------
$wuKey = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
$auKey = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
if (-not $SkipUpdatePause) {
    $until = [datetime]::ParseExact($PauseUpdatesUntil, 'yyyy-MM-dd', $null)
    if (($until - (Get-Date)).TotalDays -gt 35) { throw 'Windows 업데이트 일시 중지는 최대 35일이다. -PauseUpdatesUntil 을 줄여라.' }
    if (-not (Test-Path $wuKey)) { New-Item -Path $wuKey -Force | Out-Null }
    if (-not $state.ContainsKey('wu_pause_before')) {
        $cur = Get-ItemProperty $wuKey -ErrorAction SilentlyContinue
        $before = @{}
        foreach ($n in @('PauseFeatureUpdatesStartTime', 'PauseFeatureUpdatesEndTime', 'PauseQualityUpdatesStartTime', 'PauseQualityUpdatesEndTime', 'PauseUpdatesStartTime', 'PauseUpdatesExpiryTime')) {
            if ($cur -and $cur.PSObject.Properties[$n]) { $before[$n] = $cur.$n } else { $before[$n] = $null }
        }
        $state.wu_pause_before = $before
    }
    $startUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $endUtc = $until.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    foreach ($n in @('PauseFeatureUpdatesStartTime', 'PauseQualityUpdatesStartTime', 'PauseUpdatesStartTime')) { Set-ItemProperty -Path $wuKey -Name $n -Value $startUtc -Type String }
    foreach ($n in @('PauseFeatureUpdatesEndTime', 'PauseQualityUpdatesEndTime', 'PauseUpdatesExpiryTime')) { Set-ItemProperty -Path $wuKey -Name $n -Value $endUtc -Type String }
    if (-not (Test-Path $auKey)) { New-Item -Path $auKey -Force | Out-Null }
    if (-not $state.ContainsKey('wu_policy_before')) {
        $p = Get-ItemProperty $auKey -ErrorAction SilentlyContinue
        if ($p -and $p.PSObject.Properties['NoAutoRebootWithLoggedOnUsers']) { $state.wu_policy_before = $p.NoAutoRebootWithLoggedOnUsers } else { $state.wu_policy_before = $null }
    }
    Set-ItemProperty -Path $auKey -Name 'NoAutoRebootWithLoggedOnUsers' -Value 1 -Type DWord
    Write-Output ("Windows 업데이트: {0} 까지 일시 중지, 로그온 중 자동 재부팅 금지" -f $until.ToString('yyyy-MM-dd'))
} else { Write-Output 'Windows 업데이트 설정 건너뜀(-SkipUpdatePause)' }

# ---------- 4) 트레이 앱 바로가기 ----------
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ollama.lnk'
if (-not $KeepTrayShortcut -and (Test-Path $lnk)) {
    $backup = Join-Path $ConfigDir 'backup\Ollama.lnk'
    Move-Item -Path $lnk -Destination $backup -Force
    $state.ollama_lnk_backup = $backup
    Write-Output ("시작 폴더 Ollama.lnk → {0} (제거 스크립트가 되돌린다)" -f $backup)
}

# ---------- 5) 작업 스케줄러 ----------
$user = "$env:USERDOMAIN\$env:USERNAME"
$ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$common = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File'
function New-OpsAction { param($Script)
    $arg = '{0} "{1}" -ConfigDir "{2}"' -f $common, (Join-Path $PSScriptRoot $Script), $ConfigDir
    return (New-ScheduledTaskAction -Execute $ps -Argument $arg -WorkingDirectory $PSScriptRoot)
}
# ExecutionTimeLimit 0 = 무제한(기본 3일이면 서버가 3일마다 죽는다). 실패하면 1분 뒤 다시 시작, 최대 30회(그 뒤는 감시가 띄운다).
$settingsServer = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 30 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$settingsServer.ExecutionTimeLimit = 'PT0S'   # 일부 버전은 New-TimeSpan 0 을 무시하고 3일을 남긴다
$settingsWatch = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
# S4U: 암호 저장 없이 '사용자 로그온 여부와 관계없이 실행'. 서버 둘은 일반 권한, 감시는 작업을 멈추고 띄워야 해서 최고 권한.
$principalLimited = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
$principalHighest = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Highest

$trigOllama = New-ScheduledTaskTrigger -AtStartup; $trigOllama.Delay = 'PT30S'
$trigService = New-ScheduledTaskTrigger -AtStartup; $trigService.Delay = 'PT45S'
$trigWatchBoot = New-ScheduledTaskTrigger -AtStartup; $trigWatchBoot.Delay = 'PT3M'
$trigWatchRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)

foreach ($name in @($script:OpsTaskOllama, $script:OpsTaskService, $script:OpsTaskWatchdog)) {
    if (Get-OpsTask $name) { Stop-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $name -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $name -Confirm:$false }
}
Register-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $script:OpsTaskOllama -Action (New-OpsAction 'run_ollama.ps1') -Trigger $trigOllama -Principal $principalLimited -Settings $settingsServer -Description '집 PC Ollama 서버(11434). 부팅 시 로그인 없이 시작, 죽으면 1분 뒤 재시작' | Out-Null
Register-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $script:OpsTaskService -Action (New-OpsAction 'run_model_service.ps1') -Trigger $trigService -Principal $principalLimited -Settings $settingsServer -Description '집 PC 모델 서비스(FastAPI 8010). 부팅 시 로그인 없이 시작, 죽으면 1분 뒤 재시작' | Out-Null
Register-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $script:OpsTaskWatchdog -Action (New-OpsAction 'watchdog.ps1') -Trigger @($trigWatchBoot, $trigWatchRepeat) -Principal $principalHighest -Settings $settingsWatch -Description '5분마다 Ollama·모델 서비스 확인, heartbeat 기록, 죽으면 재시작, 모델 예열' | Out-Null
foreach ($name in @($script:OpsTaskOllama, $script:OpsTaskService, $script:OpsTaskWatchdog)) {
    $t = Get-OpsTask $name
    Write-Output ("작업 등록: {0} (실행 시간 제한 {1}, 사용자 {2}/{3})" -f $name, $t.Settings.ExecutionTimeLimit, $t.Principal.UserId, $t.Principal.LogonType)
}

# ---------- 6) 기동 ----------
Write-Output '기존 Ollama(트레이 앱 포함)·서비스 프로세스를 끝내고 작업으로 다시 띄운다'
Get-Process 'ollama app' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$k1 = Stop-OpsProcesses $ConfigDir 'ollama'
$k2 = Stop-OpsProcesses $ConfigDir 'service'
Get-Process 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Start-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $script:OpsTaskOllama
$ollamaUp = Wait-OpsUntil -Seconds 60 -StepSec 2 -Condition { Test-OpsOllama $cfg }
Write-Output ("Ollama 응답: {0}" -f $ollamaUp)
Start-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $script:OpsTaskService
$svcUp = Wait-OpsUntil -Seconds 180 -StepSec 3 -Condition { Test-OpsService $cfg }
Write-Output ("모델 서비스 /health: {0}" -f $svcUp)
if ($svcUp -and $cfg.MODEL_API_KEYS) {
    $key = ($cfg.MODEL_API_KEYS -split ',')[0].Trim()
    $warmDone = Wait-OpsUntil -Seconds 120 -StepSec 5 -Condition {
        $s = Invoke-OpsHttp -Url ((Get-OpsServiceUrl $cfg) + '/status') -TimeoutSec 10 -Headers @{ 'X-API-Key' = $key }
        ($null -ne $s) -and ($s.warm.PSObject.Properties.Count -ge 3)
    }
    $st = Invoke-OpsHttp -Url ((Get-OpsServiceUrl $cfg) + '/status') -TimeoutSec 10 -Headers @{ 'X-API-Key' = $key }
    if ($st) { Write-Output ("/status: NER {0}, 외부키 {1}, 예열 {2}, 올라온 모델 {3}" -f $st.ner_ready, $st.external.key, ($st.warm | ConvertTo-Json -Compress), (@($st.ollama.loaded | ForEach-Object { $_.name }) -join ' ')) }
}
Start-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $script:OpsTaskWatchdog

[IO.File]::WriteAllText($stateFile, ($state | ConvertTo-Json -Depth 5), $utf8Bom)
Write-Output ("설치 상태 기록: {0}" -f $stateFile)
Write-Output '끝. 확인: powershell -ExecutionPolicy Bypass -File ops\status.ps1'
Write-Output '재부팅 뒤 로그인하지 말고 다른 기기에서(또는 로그인 뒤 status.ps1 로) /health 가 뜨는지 한 번 확인할 것.'
Stop-Transcript | Out-Null
