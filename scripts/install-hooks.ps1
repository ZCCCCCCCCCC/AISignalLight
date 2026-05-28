param(
    [ValidateSet("all", "antigravity", "claude", "codex", "codexpp", "cursor")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$InstallRoot = Join-Path $env:LOCALAPPDATA "AISignalLight"
$BinDir = Join-Path $InstallRoot "bin"
$HookCmd = Join-Path $BinDir "signal.cmd"

# Copy signal.cmd to install dir
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "signal.cmd") -Destination $HookCmd -Force

# Merge fragment JSON into config, replacing __HOOK_CMD__ placeholder
function ConvertTo-Hashtable($Obj) {
    if ($Obj -is [System.Management.Automation.PSCustomObject]) {
        $hash = @{}
        foreach ($prop in $Obj.psobject.properties) {
            $hash[$prop.Name] = ConvertTo-Hashtable $prop.Value
        }
        return $hash
    } elseif ($Obj -is [array] -or $Obj -is [System.Collections.IList]) {
        return @($Obj | ForEach-Object { ConvertTo-Hashtable $_ })
    }
    return $Obj
}

function Read-Json($Path) {
    if (-not (Test-Path $Path)) { return $null }
    try { 
        $json = Get-Content -Raw -Path $Path | ConvertFrom-Json
        return ConvertTo-Hashtable $json
    }
    catch { $null }
}

function ConvertTo-JsonString($Obj, $Indent = "") {
    $nextIndent = $Indent + "  "
    if ($Obj -is [hashtable] -or $Obj -is [System.Collections.IDictionary] -or $Obj -is [System.Management.Automation.PSCustomObject]) {
        $keys = @()
        if ($Obj -is [System.Management.Automation.PSCustomObject]) {
            $keys = @($Obj.psobject.properties.Name)
        } else {
            $keys = @($Obj.Keys)
        }
        if ($keys.Count -eq 0) { return "{}" }
        $lines = foreach ($k in $keys) {
            $val = if ($Obj -is [System.Management.Automation.PSCustomObject]) { ConvertTo-JsonString $Obj.$k $nextIndent } else { ConvertTo-JsonString $Obj[$k] $nextIndent }
            "`n$nextIndent`"$k`": $val"
        }
        return "{" + ($lines -join ",") + "`n$Indent}"
    } elseif ($Obj -is [array] -or $Obj -is [System.Collections.IList]) {
        if ($Obj.Count -eq 0) { return "[]" }
        $lines = foreach ($item in $Obj) {
            $val = ConvertTo-JsonString $item $nextIndent
            "`n$nextIndent$val"
        }
        return "[" + ($lines -join ",") + "`n$Indent]"
    } elseif ($Obj -is [string]) {
        $escaped = $Obj.Replace('\', '\\').Replace('"', '\"')
        return "`"$escaped`""
    } elseif ($Obj -is [bool]) {
        if ($Obj) { return "true" } else { return "false" }
    } elseif ($null -eq $Obj) {
        return "null"
    } else {
        return $Obj.ToString()
    }
}

function Write-Json($Path, $Data) {
    $dir = Split-Path -Parent $Path
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $json = ConvertTo-JsonString $Data
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Replace-Placeholder($Obj) {
    if ($Obj -is [string]) { return $Obj.Replace("__HOOK_CMD__", $HookCmd) }
    if ($Obj -is [hashtable]) {
        $result = @{}
        foreach ($key in $Obj.Keys) { $result[$key] = Replace-Placeholder $Obj[$key] }
        return $result
    }
    if ($Obj -is [array] -or $Obj -is [System.Collections.IList]) {
        return @($Obj | ForEach-Object { Replace-Placeholder $_ })
    }
    return $Obj
}

function Merge-ClaudeCodex($ConfigPath, $Fragment) {
    $config = Read-Json $ConfigPath
    if (-not $config) { $config = @{} }
    if (-not $config.ContainsKey("hooks")) { $config["hooks"] = @{} }
    $hooks = $config["hooks"]

    foreach ($event in $Fragment.Keys) {
        $existing = if ($hooks.ContainsKey($event)) { $hooks[$event] } else { @() }
        $filtered = @($existing | Where-Object {
            (ConvertTo-Json $_ -Depth 5 -Compress) -notmatch "aisignallight|ai-traffic-light-win"
        })
        $hooks[$event] = $filtered + $Fragment[$event]
    }

    Write-Json $ConfigPath $config
}

function Merge-Cursor($ConfigPath, $Fragment) {
    $config = Read-Json $ConfigPath
    if (-not $config) { $config = @{ version = 1; hooks = @{} } }
    if (-not $config.ContainsKey("version")) { $config["version"] = 1 }
    if (-not $config.ContainsKey("hooks")) { $config["hooks"] = @{} }
    $hooks = $config["hooks"]

    # Remove previously managed keys for events we're about to set
    foreach ($event in $Fragment.Keys) {
        if ($hooks.ContainsKey($event)) { $hooks.Remove($event) }
    }
    # Also clean stale keys from other events
    foreach ($key in @($hooks.Keys)) {
        $items = $hooks[$key]
        if ($items -is [array] -and $items.Count -gt 0) {
            $allManaged = ($items | Where-Object {
                (ConvertTo-Json $_ -Depth 5 -Compress) -match "aisignallight|ai-traffic-light-win"
            }).Count -eq $items.Count
            if ($allManaged) { $hooks.Remove($key) }
        }
    }

    foreach ($event in $Fragment.Keys) { $hooks[$event] = $Fragment[$event] }
    Write-Json $ConfigPath $config
}

function Merge-Antigravity($ConfigPath, $Fragment) {
    $config = Read-Json $ConfigPath
    if (-not $config) { $config = @{} }

    # Remove previously managed keys
    foreach ($key in @($config.Keys)) {
        if ($key -match "aisignallight|ai-traffic-light-win") { $config.Remove($key) }
    }

    foreach ($key in $Fragment.Keys) { $config[$key] = $Fragment[$key] }
    Write-Json $ConfigPath $config
}

function Install-Hooks($TargetName, $ConfigPath, $FragmentRelPath) {
    $FragmentPath = Join-Path $ProjectRoot $FragmentRelPath
    if (-not (Test-Path $FragmentPath)) {
        Write-Host "Fragment not found: $FragmentPath"
        return
    }
    $fragment = Read-Json $FragmentPath
    $fragment = Replace-Placeholder $fragment

    switch ($TargetName) {
        "claude"   { Merge-ClaudeCodex $ConfigPath $fragment }
        "codex"    { Merge-ClaudeCodex $ConfigPath $fragment }
        "cursor"   { Merge-Cursor $ConfigPath $fragment }
        "antigravity" { Merge-Antigravity $ConfigPath $fragment }
    }
    Write-Host "Installed hooks for $TargetName -> $ConfigPath"
}

# ── Claude ──
if ($Target -eq "all" -or $Target -eq "claude") {
    Install-Hooks "claude" (Join-Path $HOME ".claude\settings.json") "hooks\claude-hooks.fragment.json"
}

# ── Antigravity ──
if ($Target -eq "all" -or $Target -eq "antigravity") {
    Install-Hooks "antigravity" (Join-Path $HOME ".gemini\config\hooks.json") "hooks\antigravity-hooks.fragment.json"
}

# ── Codex ──
if ($Target -eq "all" -or $Target -eq "codex") {
    Install-Hooks "codex" (Join-Path $HOME ".codex\hooks.json") "hooks\codex-hooks.fragment.json"
}

# ── Cursor ──
if ($Target -eq "all" -or $Target -eq "cursor") {
    Install-Hooks "cursor" (Join-Path $HOME ".cursor\hooks.json") "hooks\cursor-hooks.fragment.json"
}

# ── Codex++ ──
if ($Target -eq "all" -or $Target -eq "codexpp") {
    $UserScriptDir = Join-Path $env:APPDATA "Codex++\user_scripts"
    $UserScriptPath = Join-Path $UserScriptDir "aisignallight.js"
    New-Item -ItemType Directory -Force -Path $UserScriptDir | Out-Null

    $scriptContent = @"
const http = require('http');
const data = JSON.stringify({ state: process.argv[2] || 'working', source: 'codexpp' });
const req = http.request({ hostname: '127.0.0.1', port: 57422, path: '/state', method: 'POST', headers: { 'Content-Type': 'application/json' } });
req.write(data); req.end();
"@
    Set-Content -LiteralPath $UserScriptPath -Value $scriptContent -Encoding UTF8

    $ConfigPath = Join-Path $env:APPDATA "Codex++\user_scripts.json"
    $config = Read-Json $ConfigPath
    if (-not $config) { $config = @{} }
    $config["enabled"] = $true
    if (-not $config.ContainsKey("scripts")) { $config["scripts"] = @{} }
    $config["scripts"]["user:aisignallight.js"] = $true
    Write-Json $ConfigPath $config

    Write-Host "Installed Codex++ hook: $UserScriptPath"
}

Write-Host ""
Write-Host "Done! Hook command: $HookCmd"
Write-Host "Restart your AI tools for hooks to take effect."
