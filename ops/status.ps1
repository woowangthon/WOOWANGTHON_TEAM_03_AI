# 상시 가동 상태 한눈에 보기(읽기 전용, 관리자 불필요). 심사 전·연동 중에 수시로 돌린다.
#   powershell -ExecutionPolicy Bypass -File ops\status.ps1 [-Days 7]
# 보여주는 것: 작업 3개 상태, 포트·프로세스, /health·올라온 모델, heartbeat 요약(끊긴 구간·재시작), 전원·업데이트 설정.
param([string]$ConfigDir, [int]$Days = 7)

. (Join-Path $PSScriptRoot 'common.ps1')
$ConfigDir = Get-OpsConfigDir $ConfigDir
$cfg = Read-OpsConfig $ConfigDir
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Output ("== 설정: {0}" -f (Join-Path $ConfigDir 'service.env'))
$keyLen = 0; if ($cfg.MODEL_API_KEYS) { $keyLen = $cfg.MODEL_API_KEYS.Length }
$ext = '없음'; if ($cfg.ANTHROPIC_API_KEY) { $ext = '있음' }
Write-Output ("   repo={0}  host={1}:{2}  api_key_len={3}  anthropic_key={4}  keep_alive={5}" -f $cfg.REPO_DIR, $cfg.MODEL_HOST, $cfg.MODEL_PORT, $keyLen, $ext, $cfg.MODEL_KEEP_ALIVE)

Write-Output ("== 시스템: 부팅 뒤 {0}분, 사용자 {1}" -f (Get-OpsUptimeMinutes), $env:USERNAME)

Write-Output '== 작업 스케줄러 (\Woowang\)'
foreach ($name in @($script:OpsTaskOllama, $script:OpsTaskService, $script:OpsTaskWatchdog)) {
    $t = Get-OpsTask $name
    if (-not $t) { Write-Output ("   {0,-24} 등록 안 됨" -f $name); continue }
    $info = Get-ScheduledTaskInfo -TaskPath $script:OpsTaskPath -TaskName $name
    Write-Output ("   {0,-24} {1,-8} 마지막 실행 {2}  결과 {3}  다음 {4}" -f $name, $t.State, $info.LastRunTime, $info.LastTaskResult, $info.NextRunTime)
}

Write-Output '== 프로세스·포트'
$listen = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in @(11434, [int]$cfg.MODEL_PORT) }
foreach ($c in $listen) {
    $pname = (Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Write-Output ("   {0}:{1}  pid {2} ({3})" -f $c.LocalAddress, $c.LocalPort, $c.OwningProcess, $pname)
}
if (-not $listen) { Write-Output '   11434/8010 리슨 없음' }
$tray = Get-Process 'ollama app' -ErrorAction SilentlyContinue
if ($tray) { Write-Output '   주의: 트레이 앱(ollama app.exe)이 떠 있음 — 작업 스케줄러 Ollama 와 겹칠 수 있음' }

Write-Output '== 응답'
$ollamaOk = Test-OpsOllama $cfg
$svcOk = Test-OpsService $cfg
Write-Output ("   Ollama /api/version: {0}" -f $ollamaOk)
Write-Output ("   서비스 /health:     {0}" -f $svcOk)
if ($ollamaOk) {
    $loaded = Get-OpsLoadedModels $cfg
    $missing = Get-OpsMissingModels @($loaded)
    Write-Output ("   올라온 모델: {0}" -f ($loaded -join ', '))
    if ($missing.Count -gt 0) { Write-Output ("   내려가 있는 모델: {0}" -f ($missing -join ', ')) }
}
if ($svcOk -and $cfg.MODEL_API_KEYS) {
    $key = ($cfg.MODEL_API_KEYS -split ',')[0].Trim()
    $st = Invoke-OpsHttp -Url ((Get-OpsServiceUrl $cfg) + '/status') -TimeoutSec 10 -Headers @{ 'X-API-Key' = $key }
    if ($st) {
        $warm = ($st.warm | ConvertTo-Json -Compress)
        Write-Output ("   /status: uptime {0}s, 요청 {1}, 오류 {2}, NER {3}, 외부키 {4}, 예열 {5}" -f $st.uptime_s, $st.requests, $st.errors, $st.ner_ready, $st.external.key, $warm)
    }
}
$gpu = Get-OpsGpuUsedMiB
if ($gpu) { Write-Output ("   GPU 사용 메모리: {0} MiB" -f $gpu) }

Write-Output ("== heartbeat (최근 {0}일)" -f $Days)
$csv = Join-Path $cfg.LOG_DIR 'heartbeat.csv'
if (Test-Path $csv) {
    $since = (Get-Date).AddDays(-$Days)
    $rows = @(Import-Csv $csv | Where-Object { [datetime]$_.time -ge $since })
    if ($rows.Count -gt 0) {
        $down = @($rows | Where-Object { $_.ollama -ne '1' -or $_.service -ne '1' })
        $restarts = @($rows | Where-Object { $_.action -match 'restart' })
        $warms = @($rows | Where-Object { $_.action -match 'warm' })
        Write-Output ("   기록 {0}건: {1} ~ {2}" -f $rows.Count, $rows[0].time, $rows[-1].time)
        Write-Output ("   무응답 기록 {0}건, 재시작 {1}건, 예열 {2}건" -f $down.Count, $restarts.Count, $warms.Count)
        $gaps = @()
        for ($i = 1; $i -lt $rows.Count; $i++) {
            $a = [datetime]$rows[$i - 1].time; $b = [datetime]$rows[$i].time
            $m = [int]($b - $a).TotalMinutes
            if ($m -gt 7) { $gaps += ("{0} → {1} ({2}분, 부팅 뒤 {3}분)" -f $a.ToString('MM-dd HH:mm'), $b.ToString('MM-dd HH:mm'), $m, $rows[$i].uptime_min) }
        }
        if ($gaps.Count -gt 0) {
            Write-Output ("   끊긴 구간 {0}곳 (7분 초과: 절전·재부팅·감시 작업 중단 의심):" -f $gaps.Count)
            foreach ($g in $gaps) { Write-Output ("     - " + $g) }
        } else { Write-Output '   끊긴 구간 없음' }
        foreach ($d in ($down | Select-Object -Last 5)) { Write-Output ("     무응답: {0} ollama={1} service={2} {3} {4}" -f $d.time, $d.ollama, $d.service, $d.action, $d.note) }
    } else { Write-Output '   기간 안 기록 없음' }
} else { Write-Output '   heartbeat.csv 없음 (감시 작업이 아직 안 돌았음)' }

Write-Output '== 전원·업데이트'
function Get-PowerAc { param($Sub, $Setting)
    $out = powercfg /query SCHEME_CURRENT $Sub $Setting 2>$null
    $line = ($out | Select-String -Pattern 'AC.*0x[0-9a-fA-F]+' | Select-Object -First 1)
    if ($line) { return [int]('0x' + ($line.Line -replace '.*0x', '')) }
    return -1
}
$standby = Get-PowerAc 'SUB_SLEEP' 'STANDBYIDLE'
$hib = Get-PowerAc 'SUB_SLEEP' 'HIBERNATEIDLE'
Write-Output ("   절전(AC) {0}초, 최대 절전(AC) {1}초  (0 = 안 함)" -f $standby, $hib)
$wu = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -ErrorAction SilentlyContinue
if ($wu -and $wu.PauseUpdatesExpiryTime) { Write-Output ("   Windows 업데이트 일시 중지 만료: {0}" -f $wu.PauseUpdatesExpiryTime) } else { Write-Output '   Windows 업데이트 일시 중지 없음' }
$pol = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
if ($pol -and $pol.NoAutoRebootWithLoggedOnUsers -eq 1) { Write-Output '   로그온 중 자동 재부팅 금지: 켜짐' } else { Write-Output '   로그온 중 자동 재부팅 금지: 꺼짐' }
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ollama.lnk'
if (Test-Path $lnk) { Write-Output '   시작 폴더 Ollama.lnk 있음 (로그인 때 트레이 앱이 또 뜸)' } else { Write-Output '   시작 폴더 Ollama.lnk 없음' }
Write-Output ("== 로그: {0}" -f $cfg.LOG_DIR)
