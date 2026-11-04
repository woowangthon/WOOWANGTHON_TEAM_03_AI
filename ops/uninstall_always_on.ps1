# 상시 가동 제거. 관리자 PowerShell 에서 실행한다. install_always_on.ps1 이 바꾼 것을 되돌린다.
#   powershell -ExecutionPolicy Bypass -File ops\uninstall_always_on.ps1
# 되돌리는 것: 작업 3개 제거(프로세스 종료 포함), 시작 폴더 Ollama.lnk 복구, Windows 업데이트 일시 중지·정책 해제, 전원 값 복구.
# 남기는 것: 설정 파일(service.env)과 로그(-RemoveConfig 를 주면 설정 폴더째 삭제).
param([string]$ConfigDir, [switch]$RemoveConfig)

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'common.ps1')
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw '관리자 PowerShell 에서 실행해야 한다.' }
$ConfigDir = Get-OpsConfigDir $ConfigDir
$stateFile = Join-Path $ConfigDir 'install_state.json'
$state = $null
if (Test-Path $stateFile) { $state = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json }

foreach ($name in @($script:OpsTaskWatchdog, $script:OpsTaskService, $script:OpsTaskOllama)) {
    if (Get-OpsTask $name) {
        Stop-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $name -Confirm:$false
        Write-Output ("작업 제거: " + $name)
    }
}
$k1 = Stop-OpsProcesses $ConfigDir 'service'
$k2 = Stop-OpsProcesses $ConfigDir 'ollama'
Write-Output ("프로세스 종료: service {0}, ollama {1}" -f $k1, $k2)

if ($state -and $state.ollama_lnk_backup -and (Test-Path $state.ollama_lnk_backup)) {
    $lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ollama.lnk'
    Move-Item -Path $state.ollama_lnk_backup -Destination $lnk -Force
    Write-Output ("시작 폴더 Ollama.lnk 복구: " + $lnk)
}

$wuKey = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
$auKey = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
if ($state -and $state.PSObject.Properties['wu_pause_before']) {
    foreach ($p in $state.wu_pause_before.PSObject.Properties) {
        if ($null -eq $p.Value) { Remove-ItemProperty -Path $wuKey -Name $p.Name -ErrorAction SilentlyContinue }
        else { Set-ItemProperty -Path $wuKey -Name $p.Name -Value $p.Value -Type String }
    }
    Write-Output 'Windows 업데이트 일시 중지 해제(설치 전 값으로)'
}
if ($state -and $state.PSObject.Properties['wu_policy_before']) {
    if ($null -eq $state.wu_policy_before) { Remove-ItemProperty -Path $auKey -Name 'NoAutoRebootWithLoggedOnUsers' -ErrorAction SilentlyContinue }
    else { Set-ItemProperty -Path $auKey -Name 'NoAutoRebootWithLoggedOnUsers' -Value ([int]$state.wu_policy_before) -Type DWord }
    Write-Output '자동 재부팅 금지 정책 복구'
}
if ($state -and $state.PSObject.Properties['power_before']) {
    $pb = $state.power_before
    powercfg /change standby-timeout-ac ([int]([math]::Max(0, $pb.standby_ac)) / 60) | Out-Null
    powercfg /change hibernate-timeout-ac ([int]([math]::Max(0, $pb.hibernate_ac)) / 60) | Out-Null
    powercfg /change disk-timeout-ac ([int]([math]::Max(0, $pb.disk_ac)) / 60) | Out-Null
    Write-Output ("전원 복구(AC, 초): 절전 {0}, 최대 절전 {1}, 디스크 {2}" -f $pb.standby_ac, $pb.hibernate_ac, $pb.disk_ac)
}
if (Test-Path $stateFile) { Remove-Item $stateFile -Force }
if ($RemoveConfig -and (Test-Path $ConfigDir)) { Remove-Item $ConfigDir -Recurse -Force; Write-Output ("설정 폴더 삭제: " + $ConfigDir) }
Write-Output '끝. Ollama 는 다시 로그인하거나 트레이 앱을 직접 실행해야 뜬다.'
