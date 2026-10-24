# Cairn installer for PowerShell.
# Detects the system, then installs everything in your own folder: no administrator rights.
#
#   irm https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.ps1 | iex
#
# Optional variables: CAIRN_HOME (default %USERPROFILE%\Cairn), CAIRN_LLM (default qwen3:8b),
# CAIRN_WHISPER_REPO (speech model), CAIRN_REF (branch or tag to install).
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'

function Say($m) { Write-Host "`n==> $m" }
function Fail($m) { throw "Error: $m" }
function Opt($name, $default) { $v = [Environment]::GetEnvironmentVariable($name); if ([string]::IsNullOrEmpty($v)) { $default } else { $v } }

$Repo = 'yanickimhof/cairn_pocket_ai'
$Ref = Opt 'CAIRN_REF' 'main'
$CairnHome = Opt 'CAIRN_HOME' (Join-Path $env:USERPROFILE 'Cairn')
$Llm = Opt 'CAIRN_LLM' 'qwen3:8b'
$OllamaAddr = '127.0.0.1:11434'
$WhisperRepo = Opt 'CAIRN_WHISPER_REPO' 'deepdml/faster-whisper-large-v3-turbo-ct2'
if ($env:CAIRN_ALLOW_TEST_MODELS -ne '1') {
  if ($WhisperRepo -match '(?i)whisper-(tiny|base)') { throw "The speech model $WhisperRepo is too small to give reliable notes. Use the default or a small/medium/large model." }
  if ($Llm -match '(?i):(0\.\d+|1|1\.\d+|2)b') { throw "The language model $Llm is too small to give useful summaries. Use qwen3:4b or larger." }
}

# 1. Detect the system
if (-not [Environment]::Is64BitOperatingSystem) { Fail 'A 64-bit system is required.' }
Say "System detected: Windows $([Environment]::OSVersion.Version), speech engine: faster-whisper"

foreach ($d in 'Audio', 'Texts', 'Exports', 'models', 'bin') { New-Item -ItemType Directory -Force -Path (Join-Path $CairnHome $d) | Out-Null }

# 2. Get the project files (already present if you cloned the repository)
$Here = $PSScriptRoot
if ([string]::IsNullOrEmpty($Here) -or -not (Test-Path (Join-Path $Here 'requirements'))) {
  Say "Downloading Cairn ($Ref)"
  $Here = Join-Path $CairnHome 'src'
  $Tmp = Join-Path ([IO.Path]::GetTempPath()) ("cairn-" + [Guid]::NewGuid())
  New-Item -ItemType Directory -Path $Tmp | Out-Null
  Invoke-WebRequest -UseBasicParsing -Uri "https://codeload.github.com/$Repo/zip/$Ref" -OutFile (Join-Path $Tmp 'src.zip')
  Expand-Archive -Path (Join-Path $Tmp 'src.zip') -DestinationPath $Tmp
  if (Test-Path $Here) { Remove-Item -Recurse -Force $Here }
  Move-Item -Path (Get-ChildItem -Directory $Tmp | Select-Object -First 1).FullName -Destination $Here
  Remove-Item -Recurse -Force $Tmp
}
$Req = Join-Path $Here 'requirements\faster-windows.txt'
if (-not (Test-Path $Req)) { Fail 'Missing requirements\faster-windows.txt in the downloaded files.' }
if (-not (Test-Path (Join-Path $Here 'cairn'))) { Fail 'Missing the cairn application folder in the downloaded files.' }

# 3. Python tooling, kept inside the Cairn folder
$env:UV_PYTHON_INSTALL_DIR = Join-Path $CairnHome 'python'
$env:UV_CACHE_DIR = Join-Path $CairnHome '.cache\uv'
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCmd) { $Uv = $uvCmd.Source } else {
  Say "Installing uv (Python manager) in $CairnHome\bin"
  $env:UV_UNMANAGED_INSTALL = Join-Path $CairnHome 'bin'
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  $Uv = Join-Path $CairnHome 'bin\uv.exe'
}
if (-not (Test-Path $Uv)) { Fail 'uv could not be installed.' }

Say 'Creating the isolated Python environment'
& $Uv venv --python 3.11 (Join-Path $CairnHome '.venv')
if ($LASTEXITCODE -ne 0) { Fail 'Python environment creation failed.' }
$Py = Join-Path $CairnHome '.venv\Scripts\python.exe'
Say 'Installing the speech engine (versions and hashes pinned)'
& $Uv pip install --python $Py --require-hashes -r $Req
if ($LASTEXITCODE -ne 0) { Fail 'Speech engine installation failed.' }

# 4. Local model server (Ollama)
function Find-Ollama {
  $c = Get-Command ollama -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $p = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
  if (Test-Path $p) { return $p }
  $p = Join-Path $CairnHome 'bin\ollama\ollama.exe'
  if (Test-Path $p) { return $p }
  return $null
}
$Ollama = Find-Ollama
if (-not $Ollama) {
  Say 'Downloading Ollama (official build, kept in your Cairn folder)'
  $Zip = Join-Path ([IO.Path]::GetTempPath()) 'ollama-windows-amd64.zip'
  Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip' -OutFile $Zip
  $OllamaDir = Join-Path $CairnHome 'bin\ollama'
  if (Test-Path $OllamaDir) { Remove-Item -Recurse -Force $OllamaDir }
  Expand-Archive -Path $Zip -DestinationPath $OllamaDir -Force
  Remove-Item -Force $Zip
  $sig = Get-AuthenticodeSignature (Join-Path $OllamaDir 'ollama.exe')
  if ($sig.Status -ne 'Valid') { Fail 'The Ollama signature is invalid, installation stopped.' }
  $Ollama = Join-Path $OllamaDir 'ollama.exe'
}
if (-not $Ollama) { Fail 'Ollama could not be set up.' }

$env:OLLAMA_HOST = $OllamaAddr
function Server-Up { try { Invoke-RestMethod "http://$OllamaAddr/api/version" -TimeoutSec 2 | Out-Null; $true } catch { $false } }
$Started = $null
if (-not (Server-Up)) {
  Say 'Starting the local model server (127.0.0.1 only)'
  $Started = Start-Process -FilePath $Ollama -ArgumentList 'serve' -WindowStyle Hidden -PassThru
  for ($i = 0; $i -lt 60 -and -not (Server-Up); $i++) { Start-Sleep -Seconds 1 }
  if (-not (Server-Up)) { Fail 'The model server did not start.' }
}
Say "Downloading the language model: $Llm"
& $Ollama pull $Llm
if ($LASTEXITCODE -ne 0) { Fail 'Language model download failed.' }

# 5. Speech model
Say "Downloading the speech model: $WhisperRepo"
$ModelDir = Join-Path $CairnHome 'models\whisper'
& $Py -c "import sys; from huggingface_hub import snapshot_download as d; d(sys.argv[1], local_dir=sys.argv[2])" $WhisperRepo $ModelDir
if ($LASTEXITCODE -ne 0) { Fail 'Speech model download failed.' }

# 6. Settings: everything stays local
$Lines = @(
  "`$env:CAIRN_HOME = '$CairnHome'",
  "`$env:CAIRN_ENGINE = 'faster'",
  "`$env:CAIRN_WHISPER_MODEL = '$ModelDir'",
  "`$env:CAIRN_LLM = '$Llm'",
  "`$env:OLLAMA_HOST = '$OllamaAddr'",
  "`$env:HF_HUB_OFFLINE = '1'",
  "`$env:DO_NOT_TRACK = '1'"
)
Set-Content -Path (Join-Path $CairnHome 'env.ps1') -Value $Lines -Encoding UTF8

# 7. The application: configuration and launchers
$ConfigPy = @'
import json, sys
home, engine, model, repo, llm, host, ollama, app = sys.argv[1:9]
config = {"engine": engine, "whisper_model": model, "whisper_repo": repo, "llm": llm, "ollama_host": host, "ollama_bin": ollama, "app_dir": app}
with open(home + "/config.json", "w") as handle:
    json.dump(config, handle, indent=2)
'@
$ConfigFile = Join-Path ([IO.Path]::GetTempPath()) 'cairn-config.py'
[IO.File]::WriteAllText($ConfigFile, $ConfigPy, (New-Object Text.UTF8Encoding $false))
& $Py $ConfigFile $CairnHome $ModelDir $WhisperRepo $Llm $OllamaAddr $Ollama $Here
Remove-Item -Force $ConfigFile
if ($LASTEXITCODE -ne 0) { Fail 'Could not write the configuration.' }
$Cmd = "@echo off`r`nchcp 65001 >nul`r`nset `"CAIRN_HOME=$CairnHome`"`r`nset `"PYTHONPATH=$Here`"`r`nset `"PATH=$CairnHome\bin;%PATH%`"`r`n`"$Py`" -m cairn %*`r`npause`r`n"
[IO.File]::WriteAllText((Join-Path $CairnHome 'Cairn.cmd'), $Cmd, (New-Object Text.UTF8Encoding $false))
try {
  $Link = Join-Path ([Environment]::GetFolderPath('Programs')) 'Cairn.lnk'
  $Shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($Link)
  $Shortcut.TargetPath = Join-Path $CairnHome 'Cairn.cmd'
  $Shortcut.WorkingDirectory = $CairnHome
  $Shortcut.Save()
} catch { Write-Host 'Start menu shortcut not created.' }

# 8. Self test: one short audio file and one question, all local
Say 'Running the self test'
$env:CAIRN_HOME = $CairnHome; $env:CAIRN_ENGINE = 'faster'; $env:CAIRN_WHISPER_MODEL = $ModelDir
$env:CAIRN_LLM = $Llm; $env:HF_HUB_OFFLINE = '1'; $env:DO_NOT_TRACK = '1'
& $Py (Join-Path $Here 'scripts\selftest.py')
if ($LASTEXITCODE -ne 0) { Fail 'The self test failed.' }
$env:PYTHONPATH = $Here
& $Py -c 'import cairn.server'
if ($LASTEXITCODE -ne 0) { Fail 'The application could not be loaded.' }
if ($Started) { Stop-Process -Id $Started.Id -ErrorAction SilentlyContinue }

Say 'Done. Cairn is ready.'
Write-Host "`nStart Cairn: open Cairn from the Start menu, or double-click Cairn.cmd in $CairnHome"
