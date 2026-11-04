# 감시: 5분마다 Ollama(11434)와 모델 서비스(8010)를 확인해 heartbeat.csv 에 한 줄 남기고, 죽어 있으면 작업을 다시 띄우고,
# 모델이 내려가 있으면 예열한다. 작업 스케줄러 'Woowang Watchdog' 가 실행한다(수동 실행도 가능).
# 첫 실패는 WATCHDOG_RETRY_SECONDS 뒤 한 번 더 확인하고 나서야 재시작한다(긴 /analyze 중 잠깐 느린 것을 장애로 오판하지 않게).
param([string]$ConfigDir, [switch]$NoRestart)

. (Join-Path $PSScriptRoot 'common.ps1')
$ConfigDir = Get-OpsConfigDir $ConfigDir
$cfg = Read-OpsConfig $ConfigDir
$actions = @()
$notes = @()

function Restart-OpsTask {
    param([string]$Name, [string]$Kind)
    $task = Get-OpsTask $Name
    if (-not $task) { $script:notes += ("작업 없음:" + $Name); return }
    Stop-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $Name -ErrorAction SilentlyContinue
    $killed = Stop-OpsProcesses $ConfigDir $Kind
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $Name
    Write-OpsLog $ConfigDir 'watchdog.log' ("재시작: {0} (끝낸 프로세스 {1})" -f $Name, $killed)
}

$ollamaOk = Test-OpsOllama $cfg
$serviceOk = Test-OpsService $cfg
if (-not $ollamaOk -or -not $serviceOk) {
    Start-Sleep -Seconds ([int]$cfg.WATCHDOG_RETRY_SECONDS)
    if (-not $ollamaOk) { $ollamaOk = Test-OpsOllama $cfg }
    if (-not $serviceOk) { $serviceOk = Test-OpsService $cfg }
}

if (-not $ollamaOk) {
    $notes += ("ollama 무응답: " + $script:OpsLastHttpError)
    if (-not $NoRestart) {
        Restart-OpsTask $script:OpsTaskOllama 'ollama'
        $actions += 'restart-ollama'
        $ollamaOk = Wait-OpsUntil -Seconds 60 -StepSec 3 -Condition { Test-OpsOllama $cfg }
    }
}
if (-not $serviceOk) {
    $notes += ("service 무응답: " + $script:OpsLastHttpError)
    if (-not $NoRestart) {
        Restart-OpsTask $script:OpsTaskService 'service'
        $actions += 'restart-service'
        $serviceOk = Wait-OpsUntil -Seconds 180 -StepSec 5 -Condition { Test-OpsService $cfg }
    }
}

# 예열: Ollama 만 다시 떴을 때 모델이 비어 있으면 서비스 경로로 한 번 불러 올린다(서비스의 keep_alive 설정이 그대로 적용된다).
$loaded = @()
if ($ollamaOk) {
    $l = Get-OpsLoadedModels $cfg
    if ($null -ne $l) { $loaded = @($l) }
    $missing = Get-OpsMissingModels $loaded
    if ($missing.Count -gt 0 -and $serviceOk -and $cfg.WATCHDOG_WARM -eq '1' -and $cfg.MODEL_API_KEYS) {
        $key = ($cfg.MODEL_API_KEYS -split ',')[0].Trim()
        $hdr = @{ 'X-API-Key' = $key }
        $base = Get-OpsServiceUrl $cfg
        $sample = '예열용 짧은 문장입니다. 담당 김지영 과장(010-0000-0000)에게 연락 바랍니다.'
        $t0 = Get-Date
        $r1 = Invoke-OpsHttp -Url ($base + '/analyze') -Method 'POST' -Body @{ text = $sample } -TimeoutSec 300 -Headers $hdr
        $r2 = Invoke-OpsHttp -Url ($base + '/embed') -Method 'POST' -Body @{ texts = @($sample) } -TimeoutSec 300 -Headers $hdr
        $secs = [int]((Get-Date) - $t0).TotalSeconds
        $ok = ($null -ne $r1) -and ($null -ne $r2)
        $actions += 'warm'
        Write-OpsLog $ConfigDir 'watchdog.log' ("예열: 비어 있던 모델 {0} → {1} ({2}초)" -f ($missing -join ' '), $ok, $secs)
        $l = Get-OpsLoadedModels $cfg
        if ($null -ne $l) { $loaded = @($l) }
    }
}

# heartbeat 한 줄. 며칠 돌린 뒤 status.ps1 이 끊긴 구간(절전·재부팅)과 재시작 횟수를 이 파일로 센다.
$csv = Join-Path $cfg.LOG_DIR 'heartbeat.csv'
if (-not (Test-Path $cfg.LOG_DIR)) { New-Item -ItemType Directory -Path $cfg.LOG_DIR -Force | Out-Null }
if (-not (Test-Path $csv)) { Add-Content -Path $csv -Value 'time,uptime_min,ollama,service,loaded,gpu_used_mib,action,note' -Encoding UTF8 }
$row = @(
    (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),
    (Get-OpsUptimeMinutes),
    ([int]$ollamaOk),
    ([int]$serviceOk),
    ('"' + ($loaded -join ' ') + '"'),
    (Get-OpsGpuUsedMiB),
    ($actions -join '+'),
    ('"' + (($notes -join ' | ') -replace '"', "'") + '"')
) -join ','
Add-Content -Path $csv -Value $row -Encoding UTF8
if ($actions.Count -gt 0 -or $notes.Count -gt 0) {
    Write-OpsLog $ConfigDir 'watchdog.log' ("결과: ollama={0} service={1} action={2} note={3}" -f ([int]$ollamaOk), ([int]$serviceOk), ($actions -join '+'), ($notes -join ' | '))
}
Write-Output $row
