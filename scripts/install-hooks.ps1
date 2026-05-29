param(
    [ValidateSet("all", "antigravity", "claude", "codex", "codexpp", "cursor")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = (Get-Command python).Source
$InstallRoot = Join-Path $env:LOCALAPPDATA "AI Traffic Light Win"
$BinDir = Join-Path $InstallRoot "bin"
$HookCmd = Join-Path $BinDir "ai-traffic-light-win.cmd"

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$Shim = @(
    "@echo off",
    "setlocal",
    "set ""PYTHONPATH=$ProjectRoot;%PYTHONPATH%""",
    """$Python"" -m ai_traffic_light_win.cli %*"
)
Set-Content -LiteralPath $HookCmd -Value $Shim -Encoding ASCII

function Install-Target {
    param(
        [string]$Name,
        [string]$ConfigPath,
        [string]$FragmentPath
    )

    & $Python -m ai_traffic_light_win.hook_merge $Name $ConfigPath $FragmentPath $HookCmd
}

function Install-CodexPlusPlus {
    $UserScriptDir = Join-Path $env:APPDATA "Codex++\user_scripts"
    $UserScriptPath = Join-Path $UserScriptDir "ai-traffic-light-win.js"
    $ConfigPath = Join-Path $env:APPDATA "Codex++\user_scripts.json"

    New-Item -ItemType Directory -Force -Path $UserScriptDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "hooks\codexpp-user-script.js") -Destination $UserScriptPath -Force

    if (Test-Path -LiteralPath $ConfigPath) {
        try {
            $Config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json
        } catch {
            $Config = [pscustomobject]@{}
        }
    } else {
        $Config = [pscustomobject]@{}
    }

    if (-not ($Config.PSObject.Properties.Name -contains "enabled")) {
        $Config | Add-Member -NotePropertyName "enabled" -NotePropertyValue $true
    } else {
        $Config.enabled = $true
    }

    if (-not ($Config.PSObject.Properties.Name -contains "scripts") -or $null -eq $Config.scripts) {
        $Config | Add-Member -NotePropertyName "scripts" -NotePropertyValue ([pscustomobject]@{})
    }

    if (-not ($Config.scripts.PSObject.Properties.Name -contains "user:ai-traffic-light-win.js")) {
        $Config.scripts | Add-Member -NotePropertyName "user:ai-traffic-light-win.js" -NotePropertyValue $true
    } else {
        $Config.scripts."user:ai-traffic-light-win.js" = $true
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ConfigPath) | Out-Null
    $Config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

    Write-Host "Installed Codex++ user script: $UserScriptPath"
}

$env:PYTHONPATH = "$ProjectRoot;$env:PYTHONPATH"

if ($Target -eq "all" -or $Target -eq "claude") {
    Install-Target `
        -Name "claude" `
        -ConfigPath (Join-Path $HOME ".claude\settings.json") `
        -FragmentPath (Join-Path $ProjectRoot "hooks\claude-hooks.fragment.json")
}

if ($Target -eq "all" -or $Target -eq "antigravity") {
    Install-Target `
        -Name "antigravity" `
        -ConfigPath (Join-Path $HOME ".gemini\config\hooks.json") `
        -FragmentPath (Join-Path $ProjectRoot "hooks\antigravity-hooks.fragment.json")
}

if ($Target -eq "all" -or $Target -eq "codex") {
    Install-Target `
        -Name "codex" `
        -ConfigPath (Join-Path $HOME ".codex\hooks.json") `
        -FragmentPath (Join-Path $ProjectRoot "hooks\codex-hooks.fragment.json")

    & $Python -m ai_traffic_light_win.codex_trust --cwd $ProjectRoot
}

if ($Target -eq "all" -or $Target -eq "codexpp") {
    Install-CodexPlusPlus
}

if ($Target -eq "all" -or $Target -eq "cursor") {
    Install-Target `
        -Name "cursor" `
        -ConfigPath (Join-Path $HOME ".cursor\hooks.json") `
        -FragmentPath (Join-Path $ProjectRoot "hooks\cursor-hooks.fragment.json")
}

Write-Host "Installed hook command: $HookCmd"
Write-Host "Restart the target app so hooks take effect."
