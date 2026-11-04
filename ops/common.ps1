# 운영 스크립트 공통 함수. run_ollama.ps1 · run_model_service.ps1 · watchdog.ps1 · status.ps1 · install/uninstall 이 dot-source 한다.
# Windows PowerShell 5.1 기준(작업 스케줄러가 powershell.exe 로 실행). &&, ??, 삼항 연산자는 쓰지 않는다.
# 설정·로그는 저장소 밖(기본 %LOCALAPPDATA%\woowang)에 둔다. 비밀값(MODEL_API_KEYS, ANTHROPIC_API_KEY)은 로그에 찍지 않는다.

$script:OpsTaskPath = '\Woowang\'
$script:OpsTaskOllama = 'Woowang Ollama'
$script:OpsTaskService = 'Woowang Model Service'
$script:OpsTaskWatchdog = 'Woowang Watchdog'
# 서비스가 쓰는 세 모델. /api/ps 이름은 태그가 붙어 나올 수 있다(tev1-cpu:latest)
$script:OpsModels = @('qwen3:30b-a3b-instruct-2507-q4_K_M', 'tev1-cpu', 'bge-m3-cpu')

function Get-OpsConfigDir {
    param([string]$ConfigDir)
    if ($ConfigDir) { return $ConfigDir }
    $local = [Environment]::GetFolderPath('LocalApplicationData')
    if (-not $local) { $local = Join-Path $env:USERPROFILE 'AppData\Local' }
    return (Join-Path $local 'woowang')
}

function Get-OpsUserEnv {
    # 사용자 환경변수(setx 로 등록한 값). 작업 스케줄러(S4U)에서는 프로필이 안 실려 $env: 에 없을 수 있어 레지스트리에서 직접 읽는다.
    param([string]$Name)
    $v = [Environment]::GetEnvironmentVariable($Name, 'User')
    if ($v) { return $v }
    try {
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $item = Get-ItemProperty -Path "Registry::HKEY_USERS\$sid\Environment" -Name $Name -ErrorAction Stop
        return $item.$Name
    } catch { return $null }
}

function Read-OpsConfig {
    # service.env(KEY=VALUE, # 주석)를 읽어 해시테이블로 돌려준다. 없는 키는 기본값으로 채운다.
    param([string]$ConfigDir)
    $repo = Split-Path -Parent $PSScriptRoot
    $cfg = @{
        REPO_DIR = $repo
        PYTHON_EXE = ''                      # 비면 REPO_DIR\.venv\Scripts\python.exe
        MODEL_HOST = '127.0.0.1'             # 터널로 열 때 0.0.0.0 또는 Tailscale IP
        MODEL_PORT = '8010'
        MODEL_API_KEYS = ''                  # 백엔드가 쓸 X-API-Key (쉼표로 여러 개). 비면 서버가 임시 키를 만든다
        MODEL_KEEP_ALIVE = '-1'              # 요청마다 Ollama 에 넘기는 keep_alive. -1 = 모델을 내리지 않음
        MODEL_LOG_LEVEL = 'info'
        OLLAMA_EXE = ''                      # 비면 %LOCALAPPDATA%\Programs\Ollama\ollama.exe
        OLLAMA_MODELS = ''                   # 비면 %USERPROFILE%\.ollama\models
        OLLAMA_HOST = '127.0.0.1:11434'
        OLLAMA_KEEP_ALIVE = '-1'
        OLLAMA_MAX_LOADED_MODELS = '3'
        OLLAMA_CONTEXT_LENGTH = '8192'
        OLLAMA_NUM_PARALLEL = '1'
        HF_HOME = ''                         # 비면 %USERPROFILE%\.cache\huggingface (NER 모델 캐시)
        HF_OFFLINE = '1'                     # 1 이면 허브 접속 없이 캐시만 쓴다(시작이 빠르고 네트워크 끊겨도 뜬다)
        ANTHROPIC_API_KEY = ''               # 비면 사용자 환경변수(레지스트리)에서 읽는다
        WATCHDOG_RETRY_SECONDS = '20'        # 첫 실패 뒤 재확인까지 대기
        WATCHDOG_WARM = '1'                  # 모델이 내려가 있으면 예열
        LOG_KEEP = '10'                      # ollama_*/service_* 로그 보관 개수
    }
    $file = Join-Path $ConfigDir 'service.env'
    if (Test-Path $file) {
        foreach ($line in (Get-Content $file -Encoding UTF8)) {
            $t = $line.Trim()
            if (-not $t) { continue }
            if ($t.StartsWith('#')) { continue }
            $i = $t.IndexOf('=')
            if ($i -lt 1) { continue }
            $k = $t.Substring(0, $i).Trim()
            $v = $t.Substring($i + 1).Trim()
            if ($v.Length -ge 2) {
                $q = $v.Substring(0, 1)
                if (($q -eq '"' -or $q -eq "'") -and $v.EndsWith($q)) { $v = $v.Substring(1, $v.Length - 2) }
            }
            $cfg[$k] = $v
        }
    }
    if (-not $cfg.PYTHON_EXE) { $cfg.PYTHON_EXE = Join-Path $cfg.REPO_DIR '.venv\Scripts\python.exe' }
    if (-not $cfg.OLLAMA_EXE) {
        $local = [Environment]::GetFolderPath('LocalApplicationData')
        $cfg.OLLAMA_EXE = Join-Path $local 'Programs\Ollama\ollama.exe'
    }
    if (-not $cfg.OLLAMA_MODELS) { $cfg.OLLAMA_MODELS = Join-Path $env:USERPROFILE '.ollama\models' }
    if (-not $cfg.HF_HOME) { $cfg.HF_HOME = Join-Path $env:USERPROFILE '.cache\huggingface' }
    if (-not $cfg.ANTHROPIC_API_KEY) {
        $k = Get-OpsUserEnv 'ANTHROPIC_API_KEY'
        if ($k) { $cfg.ANTHROPIC_API_KEY = $k }
    }
    $cfg.CONFIG_DIR = $ConfigDir
    $cfg.LOG_DIR = Join-Path $ConfigDir 'logs'
    return $cfg
}

function Get-OpsServiceUrl {
    param($Cfg)
    $h = $Cfg.MODEL_HOST
    if ($h -eq '0.0.0.0' -or -not $h) { $h = '127.0.0.1' }
    return "http://$h`:$($Cfg.MODEL_PORT)"
}

function Get-OpsOllamaUrl {
    param($Cfg)
    return "http://$($Cfg.OLLAMA_HOST)"
}

function Set-OpsProcessEnv {
    # 자식 프로세스(ollama.exe, python.exe)가 볼 환경변수. 프로필 환경에 기대지 않고 설정 파일 값으로 전부 지정한다.
    param($Cfg)
    $env:OLLAMA_HOST = $Cfg.OLLAMA_HOST
    $env:OLLAMA_MODELS = $Cfg.OLLAMA_MODELS
    $env:OLLAMA_KEEP_ALIVE = $Cfg.OLLAMA_KEEP_ALIVE
    $env:OLLAMA_MAX_LOADED_MODELS = $Cfg.OLLAMA_MAX_LOADED_MODELS
    $env:OLLAMA_CONTEXT_LENGTH = $Cfg.OLLAMA_CONTEXT_LENGTH
    $env:OLLAMA_NUM_PARALLEL = $Cfg.OLLAMA_NUM_PARALLEL
    $env:HF_HOME = $Cfg.HF_HOME
    if ($Cfg.HF_OFFLINE -eq '1') { $env:HF_HUB_OFFLINE = '1'; $env:TRANSFORMERS_OFFLINE = '1' }
    $env:MODEL_KEEP_ALIVE = $Cfg.MODEL_KEEP_ALIVE
    if ($Cfg.MODEL_API_KEYS) { $env:MODEL_API_KEYS = $Cfg.MODEL_API_KEYS }
    if ($Cfg.ANTHROPIC_API_KEY) { $env:ANTHROPIC_API_KEY = $Cfg.ANTHROPIC_API_KEY }
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUNBUFFERED = '1'
}

function Write-OpsLog {
    # logs\<File> 에 시각과 함께 한 줄 추가. 로그 폴더가 없으면 만든다.
    param([string]$ConfigDir, [string]$File, [string]$Message)
    $dir = Join-Path $ConfigDir 'logs'
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path (Join-Path $dir $File) -Value $line -Encoding UTF8
}

function New-OpsLogPath {
    param([string]$ConfigDir, [string]$Prefix)
    $dir = Join-Path $ConfigDir 'logs'
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    return (Join-Path $dir ('{0}_{1}.log' -f $Prefix, (Get-Date -Format 'yyyyMMdd_HHmmss')))
}

function Remove-OpsOldLogs {
    param([string]$ConfigDir, [string]$Prefix, [int]$Keep)
    $dir = Join-Path $ConfigDir 'logs'
    if (-not (Test-Path $dir)) { return }
    $files = Get-ChildItem -Path $dir -Filter ("{0}_*.log" -f $Prefix) | Sort-Object LastWriteTime -Descending
    if ($files.Count -gt $Keep) {
        $files | Select-Object -Skip $Keep | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-OpsHttp {
    # 작은 JSON HTTP 호출. Invoke-WebRequest 는 프로필 없는 세션(S4U)에서 IE 엔진 오류가 날 수 있어 .NET 을 직접 쓴다.
    # 성공하면 파싱한 객체, 실패하면 $null (오류 메시지는 $script:OpsLastHttpError).
    param([string]$Url, [string]$Method = 'GET', $Body = $null, [int]$TimeoutSec = 10, [hashtable]$Headers = @{})
    $script:OpsLastHttpError = ''
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.Method = $Method
        $req.Timeout = $TimeoutSec * 1000
        $req.ReadWriteTimeout = $TimeoutSec * 1000
        $req.Proxy = $null
        foreach ($k in $Headers.Keys) { $req.Headers.Add($k, $Headers[$k]) }
        if ($null -ne $Body) {
            $json = $Body | ConvertTo-Json -Depth 8 -Compress
            $bytes = [Text.Encoding]::UTF8.GetBytes($json)
            $req.ContentType = 'application/json'
            $req.ContentLength = $bytes.Length
            $s = $req.GetRequestStream(); $s.Write($bytes, 0, $bytes.Length); $s.Close()
        }
        $resp = $req.GetResponse()
        $reader = New-Object IO.StreamReader($resp.GetResponseStream(), [Text.Encoding]::UTF8)
        $text = $reader.ReadToEnd(); $reader.Close(); $resp.Close()
        if (-not $text) { return @{} }
        return ($text | ConvertFrom-Json)
    } catch {
        $script:OpsLastHttpError = $_.Exception.Message
        return $null
    }
}

function Test-OpsOllama {
    param($Cfg, [int]$TimeoutSec = 5)
    $r = Invoke-OpsHttp -Url ((Get-OpsOllamaUrl $Cfg) + '/api/version') -TimeoutSec $TimeoutSec
    return ($null -ne $r)
}

function Test-OpsService {
    param($Cfg, [int]$TimeoutSec = 10)
    $r = Invoke-OpsHttp -Url ((Get-OpsServiceUrl $Cfg) + '/health') -TimeoutSec $TimeoutSec
    if ($null -eq $r) { return $false }
    return [bool]$r.ok
}

function Get-OpsLoadedModels {
    # Ollama 에 올라와 있는 모델 이름 목록(태그 포함). Ollama 가 죽어 있으면 $null.
    param($Cfg)
    $r = Invoke-OpsHttp -Url ((Get-OpsOllamaUrl $Cfg) + '/api/ps') -TimeoutSec 5
    if ($null -eq $r) { return $null }
    $names = @()
    foreach ($m in @($r.models)) { if ($m.name) { $names += [string]$m.name } }
    return $names
}

function Get-OpsMissingModels {
    param([string[]]$Loaded)
    $missing = @()
    foreach ($m in $script:OpsModels) {
        $hit = $false
        foreach ($n in $Loaded) { if ($n -eq $m -or $n -eq ($m + ':latest')) { $hit = $true } }
        if (-not $hit) { $missing += $m }
    }
    return $missing
}

function Wait-OpsUntil {
    # 조건이 참이 될 때까지 Seconds 동안 기다린다. 참이면 $true.
    param([scriptblock]$Condition, [int]$Seconds, [int]$StepSec = 2)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) { return $true }
        Start-Sleep -Seconds $StepSec
    }
    return (& $Condition)
}

function Get-OpsProcessesByPattern {
    # 명령줄로 우리 프로세스를 찾는다. Kind: ollama = 'ollama.exe serve', service = 'src\server.py'
    param([string]$Kind)
    if ($Kind -eq 'ollama') { $pat = 'ollama(\.exe)?"?\s+serve' } else { $pat = 'src[\\/]server\.py' }
    $list = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match $pat) })
    return ,$list   # 쉼표: 원소가 하나여도 배열로 돌려준다(아니면 CimInstance 하나로 풀려 .Count 가 비어 보인다)
}

function Stop-OpsProcesses {
    # pid 파일과 명령줄 패턴으로 Ollama 서버 또는 모델 서비스를 끝낸다. 끝낸 프로세스 수를 돌려준다.
    # 작업 스케줄러의 '작업 끝내기'는 래퍼(powershell.exe)만 끝내고 자식은 남길 수 있어 직접 정리한다.
    param([string]$ConfigDir, [string]$Kind)
    $count = 0
    $pidFile = Join-Path $ConfigDir ($Kind + '.pid')
    if (Test-Path $pidFile) {
        $procId = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($procId -match '^\d+$') {
            $p = Get-Process -Id ([int]$procId) -ErrorAction SilentlyContinue
            if ($p) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue; $count++ }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    foreach ($p in (Get-OpsProcessesByPattern $Kind)) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        $count++
    }
    return $count
}

function Get-OpsTask {
    param([string]$Name)
    return (Get-ScheduledTask -TaskPath $script:OpsTaskPath -TaskName $Name -ErrorAction SilentlyContinue)
}

function Get-OpsUptimeMinutes {
    try {
        $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
        return [int]((Get-Date) - $boot).TotalMinutes
    } catch { return -1 }
}

function Get-OpsGpuUsedMiB {
    # nvidia-smi 가 없거나 실패하면 빈 문자열
    try {
        $out = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null
        if ($out) { return ([string]$out).Trim() }
    } catch {}
    return ''
}
