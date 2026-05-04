#!/usr/bin/env pwsh
# cli_v2.ps1 - Delphix CD engine healthcheck (PowerShell port)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptVersion = '3.1.0'

function Show-Help {
  Write-Output "Script Version $scriptVersion"
  Write-Output 'Script to generate Delphix CD healthcheck data'
  Write-Output ''
  Write-Output 'Usage:'
  Write-Output '  ./cli_v2.ps1 -d <engine|all> -t <win|unix|both> -b <dxtoolkit_path> -o <output_dir>'
  Write-Output '  [--address <fqdn_or_ip>] [--port <port>] [--protocol <http|https>]'
  Write-Output '  [--password <admin_password>] [--sys-password <sysadmin_password>] [--preserve-output] [-h]'
  Write-Output ''
  Write-Output 'Required dxtoolkit scripts in -b:'
  Write-Output '  dx_config, dx_ctl_network_tests, dx_ctl_bundle, dx_get_analytics,'
  Write-Output '  dx_get_capacity, dx_get_appliance, dx_get_storage_tests, dx_get_config, dx_get_network_tests'
  Write-Output ''
  Write-Output 'Notes:'
  Write-Output '  - Set timeouts to 600 in your dxtools.conf entries for long-running calls.'
}

function Parse-Arguments {
  param([string[]]$RawArgs)

  $opts = [ordered]@{
    DE_READ = ''
    DE_TYPE = ''
    DXLOC = ''
    MAINDIR = ''
    ADDR_OPT = ''
    PORT_OPT = ''
    PROTO_OPT = ''
    ADMIN_PASS_OPT = ''
    SYS_PASS_OPT = ''
    PRESERVE_OUTPUT = $false
    SHOW_HELP = $false
  }

  if (-not $RawArgs -or $RawArgs.Count -eq 0) {
    $opts.SHOW_HELP = $true
    return $opts
  }

  $i = 0
  while ($i -lt $RawArgs.Count) {
    $arg = $RawArgs[$i]
    switch ($arg) {
      '-d' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for -d' }
        $opts.DE_READ = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '-t' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for -t' }
        $opts.DE_TYPE = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '-b' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for -b' }
        $opts.DXLOC = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '-o' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for -o' }
        $opts.MAINDIR = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '--address' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for --address' }
        $opts.ADDR_OPT = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '--port' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for --port' }
        $opts.PORT_OPT = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '--protocol' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for --protocol' }
        $opts.PROTO_OPT = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '--password' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for --password' }
        $opts.ADMIN_PASS_OPT = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '--sys-password' {
        if ($i + 1 -ge $RawArgs.Count) { throw 'Missing value for --sys-password' }
        $opts.SYS_PASS_OPT = $RawArgs[$i + 1]
        $i += 2
        continue
      }
      '--preserve-output' {
        $opts.PRESERVE_OUTPUT = $true
        $i += 1
        continue
      }
      '-h' { $opts.SHOW_HELP = $true; $i += 1; continue }
      '--help' { $opts.SHOW_HELP = $true; $i += 1; continue }
      default {
        throw "Invalid option: $arg"
      }
    }
  }

  return $opts
}

function Require-Tool {
  param(
    [string]$DXLOC,
    [string]$Name
  )

  $exePath = Join-Path $DXLOC ("$Name.exe")
  if (Test-Path -LiteralPath $exePath) {
    return
  }

  throw "Missing $DXLOC/$Name.exe"
}

function Invoke-Tool {
  param(
    [string]$DXLOC,
    [string]$Name,
    [string[]]$ToolArgs,
    [switch]$AllowFailure,
    [string]$StdoutFile
  )

  $exePath = Join-Path $DXLOC ("$Name.exe")

  $exec = $null
  $argsToRun = @()

  if (Test-Path -LiteralPath $exePath) {
    $exec = $exePath
    $argsToRun = $ToolArgs
  }
  else {
    throw "Missing $DXLOC/$Name.exe"
  }

  if ($StdoutFile) {
    & $exec @argsToRun 1> $StdoutFile
  }
  else {
    & $exec @argsToRun
  }

  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0 -and -not $AllowFailure) {
    throw "$Name failed with exit code $exitCode"
  }

  return $exitCode
}

function Read-Row {
  param(
    [string]$CsvPath,
    [string]$Alias
  )

  if (-not (Test-Path -LiteralPath $CsvPath)) {
    return $null
  }

  $line = Get-Content -LiteralPath $CsvPath | Where-Object { $_ -like "$Alias,*" } | Select-Object -First 1
  if (-not $line) {
    return $null
  }

  $parts = $line.Split(',')
  if ($parts.Count -lt 7) {
    return $null
  }

  return [ordered]@{
    IP = $parts[1]
    PORT = $parts[2]
    USER = $parts[3]
    PASS = $parts[4]
    ENC = $parts[5]
    PROTO = $parts[6]
  }
}

function Get-PathOrEmpty {
  param([string]$Path)
  if (Test-Path -LiteralPath $Path) {
    return (Resolve-Path -LiteralPath $Path).Path
  }
  return ''
}

try {
  $opts = Parse-Arguments -RawArgs $args

  if ($opts.SHOW_HELP) {
    Show-Help
    if ($args.Count -eq 0) { exit 1 }
    exit 0
  }

  if ([string]::IsNullOrWhiteSpace($opts.DE_READ)) { throw 'Missing -d' }
  if ([string]::IsNullOrWhiteSpace($opts.DE_TYPE)) { throw 'Missing -t' }
  if ([string]::IsNullOrWhiteSpace($opts.DXLOC)) { throw 'Missing -b' }
  if ([string]::IsNullOrWhiteSpace($opts.MAINDIR)) { throw 'Missing -o' }

  $dxLocResolved = Resolve-Path -LiteralPath $opts.DXLOC -ErrorAction Stop | Select-Object -ExpandProperty Path
  if (-not (Test-Path -LiteralPath $opts.MAINDIR)) {
    New-Item -ItemType Directory -Path $opts.MAINDIR -Force | Out-Null
  }
  $mainDirResolved = Resolve-Path -LiteralPath $opts.MAINDIR -ErrorAction Stop | Select-Object -ExpandProperty Path

  Write-Output "Script Version $scriptVersion"
  Write-Output "Dxtoolkit Path: $dxLocResolved"

  $requiredTools = @(
    'dx_config',
    'dx_ctl_network_tests',
    'dx_ctl_bundle',
    'dx_get_analytics',
    'dx_get_capacity',
    'dx_get_appliance',
    'dx_get_storage_tests',
    'dx_get_config',
    'dx_get_network_tests'
  )
  foreach ($tool in $requiredTools) {
    Require-Tool -DXLOC $dxLocResolved -Name $tool
  }

  $perfData = Join-Path $mainDirResolved 'analytics'
  $miscDir = Join-Path $mainDirResolved 'misc'

  if (-not $opts.PRESERVE_OUTPUT) {
    if (Test-Path -LiteralPath $perfData) { Remove-Item -LiteralPath $perfData -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $miscDir) { Remove-Item -LiteralPath $miscDir -Recurse -Force -ErrorAction SilentlyContinue }
  }
  New-Item -ItemType Directory -Path $perfData -Force | Out-Null
  New-Item -ItemType Directory -Path $miscDir -Force | Out-Null

  $base = $opts.DE_READ
  if ($base.EndsWith('sys')) {
    $base = $base.Substring(0, $base.Length - 3)
  }
  $sysAlias = "$base" + 'sys'

  $dcc = Join-Path $dxLocResolved 'dxtools.conf'
  $csv = Join-Path $dxLocResolved '.dxconf.csv'
  $backup = ''

  $oldPath = $env:PATH
  $oldConfigSet = $false
  $oldConfig = ''

  if ($null -ne $env:DXTOOLKIT_CONF) {
    $oldConfigSet = $true
    $oldConfig = $env:DXTOOLKIT_CONF
  }

  Push-Location $dxLocResolved
  try {
    if (Test-Path -LiteralPath $dcc) {
      $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_config' -ToolArgs @('-convert', 'tocsv', '-configfile', $dcc, '-csvfile', $csv) -AllowFailure
      if ($code -ne 0) {
        throw 'dx_config tocsv failed'
      }
    }
    else {
      Set-Content -LiteralPath $csv -Value '' -Encoding UTF8
    }

    $adminRow = Read-Row -CsvPath $csv -Alias $base
    $adminIp = if ($adminRow) { $adminRow.IP } else { '' }
    $adminPort = if ($adminRow) { $adminRow.PORT } else { '' }
    $adminPass = if ($adminRow) { $adminRow.PASS } else { '' }
    $adminEnc = if ($adminRow) { $adminRow.ENC } else { '' }
    $adminProto = if ($adminRow) { $adminRow.PROTO } else { '' }

    $useIp = if ($opts.ADDR_OPT) { $opts.ADDR_OPT } elseif ($adminIp) { $adminIp } else { $base }
    $usePort = if ($opts.PORT_OPT) { $opts.PORT_OPT } elseif ($adminPort) { $adminPort } else { '80' }
    $useProto = if ($opts.PROTO_OPT) { $opts.PROTO_OPT } elseif ($adminProto) { $adminProto } else { 'http' }
    $useEnc = if ($adminEnc) { $adminEnc } else { 'false' }

    $hasAdmin = Select-String -Path $csv -Pattern "^$([regex]::Escape($base))," -Quiet
    if (-not $hasAdmin) {
      if ($opts.ADMIN_PASS_OPT) {
        $adminPass = $opts.ADMIN_PASS_OPT
      }
      if (-not $adminPass -and $opts.DE_READ -ne 'all') {
        $secure = Read-Host -Prompt "Admin password for $base" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
          $adminPass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        }
        finally {
          [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
      }
      if (-not $adminPass -and $opts.DE_READ -ne 'all') {
        throw "Missing admin password for $base."
      }
      Add-Content -LiteralPath $csv -Value "$base,$useIp,$usePort,admin,$adminPass,$useEnc,$useProto"
    }

    $hasSys = Select-String -Path $csv -Pattern "^$([regex]::Escape($sysAlias))," -Quiet
    if (-not $hasSys) {
      $sysPass = $opts.SYS_PASS_OPT
      if (-not $sysPass -and $opts.DE_READ -ne 'all') {
        $secure = Read-Host -Prompt "Sysadmin password for $sysAlias" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
          $sysPass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        }
        finally {
          [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
      }
      if (-not $sysPass -and $opts.DE_READ -ne 'all') {
        throw "Missing sysadmin password for $sysAlias."
      }
      Add-Content -LiteralPath $csv -Value "$sysAlias,$useIp,$usePort,sysadmin,$sysPass,$useEnc,$useProto"
    }

    if (Test-Path -LiteralPath $dcc) {
      $backup = "$dcc.orig.$(Get-Date -Format 'yyyy-MM-dd').$PID.bak"
      Copy-Item -LiteralPath $dcc -Destination $backup -Force
    }

    Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_config' -ToolArgs @('-convert', 'todxconf', '-configfile', $dcc, '-csvfile', $csv) | Out-Null

    $de = if ($opts.DE_READ -eq 'all') { @('-all') } else { @('-d', $base) }
    $deSys = if ($opts.DE_READ -eq 'all') { @('-all') } else { @('-d', $sysAlias) }

    $env:PATH = "$dxLocResolved$([IO.Path]::PathSeparator)$($env:PATH)"
    $env:DXTOOLKIT_CONF = $dcc

    Write-Output 'Run a network latency test on all environments'
    $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_ctl_network_tests' -ToolArgs ($de + @('-c', $dcc, '-type', 'latency', '-remoteaddr', 'all')) -AllowFailure
    if ($code -ne 0) {
      Write-Output 'Warning: network latency test did not complete successfully; continuing.'
    }

    Write-Output 'Run a network throughput test on all environments'
    $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_ctl_network_tests' -ToolArgs ($de + @('-c', $dcc, '-type', 'throughput', '-remoteaddr', 'all')) -AllowFailure
    if ($code -ne 0) {
      Write-Output 'Warning: network throughput test did not complete successfully; continuing.'
    }

    $nlFile = Join-Path $miscDir ("$base" + '_NL.csv')
    Write-Output "Gathering network latency results -> $nlFile"
    $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_network_tests' -ToolArgs ($de + @('-configfile', $dcc, '-last', '-type', 'latency', '-remoteaddr', 'all', '-format', 'csv')) -AllowFailure -StdoutFile $nlFile
    if ($code -ne 0) {
      Write-Output "Warning: unable to fetch network latency test results; skipping $nlFile."
    }

    $ntFile = Join-Path $miscDir ("$base" + '_NT.csv')
    Write-Output "Gathering network throughput results -> $ntFile"
    $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_network_tests' -ToolArgs ($de + @('-configfile', $dcc, '-last', '-type', 'throughput', '-remoteaddr', 'all', '-format', 'csv')) -AllowFailure -StdoutFile $ntFile
    if ($code -ne 0) {
      Write-Output "Warning: unable to fetch network throughput test results; skipping $ntFile."
    }

    Write-Output "Gathering analytics ($($opts.DE_TYPE))"
    $argTypes = switch ($opts.DE_TYPE) {
      'win' { 'cpu,disk,iscsi,network' }
      'unix' { 'cpu,disk,nfs,network' }
      'both' { 'cpu,disk,iscsi,nfs,network' }
      default { throw 'Invalid -t (use win|unix|both)' }
    }

    $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_analytics' -ToolArgs ($de + @('-configfile', $dcc, '-i', '60', '-outdir', $perfData, '-type', $argTypes)) -AllowFailure
    if ($code -ne 0) {
      Write-Output 'Warning: analytics completed with partial errors; continuing with remaining collection tasks.'
    }

    $capacityFile = Join-Path $miscDir ("$base" + '_capacity.csv')
    Write-Output "Gathering capacity -> $capacityFile"
    Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_capacity' -ToolArgs ($de + @('-configfile', $dcc, '-unvirt', '-format', 'csv')) -StdoutFile $capacityFile | Out-Null

    $applianceFile = Join-Path $miscDir ("$base" + '_appliance.csv')
    Write-Output "Gathering appliance -> $applianceFile"
    Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_appliance' -ToolArgs ($de + @('-configfile', $dcc, '-format', 'csv')) -StdoutFile $applianceFile | Out-Null

    Write-Output "Gathering IORC (sysadmin) -> $miscDir/"
    $code = Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_storage_tests' -ToolArgs ($deSys + @('-configfile', $dcc, '-testid', 'last', '-iorc', $miscDir)) -AllowFailure
    if ($code -ne 0) {
      Write-Output "Warning: no completed storage test found for $sysAlias; skipping IORC export."
    }

    $configFile = Join-Path $miscDir ("$base" + '_config.csv')
    Write-Output "Gathering system configuration (sysadmin) -> $configFile"
    $tmpConfig = Join-Path $miscDir ("$base" + '_config.tmp.csv')
    Invoke-Tool -DXLOC $dxLocResolved -Name 'dx_get_config' -ToolArgs ($deSys + @('-configfile', $dcc, '-format', 'csv')) -StdoutFile $tmpConfig | Out-Null
    (Get-Content -LiteralPath $tmpConfig) -replace [regex]::Escape($sysAlias), $base | Set-Content -LiteralPath $configFile -Encoding UTF8
    Remove-Item -LiteralPath $tmpConfig -Force -ErrorAction SilentlyContinue

    Write-Output 'Done. Outputs:'
    Get-ChildItem -LiteralPath $perfData -File -ErrorAction SilentlyContinue |
      ForEach-Object { '{0,10} {1}' -f $_.Length, $_.FullName }
    Get-ChildItem -LiteralPath $miscDir -File -ErrorAction SilentlyContinue |
      ForEach-Object { '{0,10} {1}' -f $_.Length, $_.FullName }
  }
  finally {
    Pop-Location

    if ($oldConfigSet) {
      $env:DXTOOLKIT_CONF = $oldConfig
    }
    else {
      Remove-Item Env:DXTOOLKIT_CONF -ErrorAction SilentlyContinue
    }

    $env:PATH = $oldPath

    if ($backup -and (Test-Path -LiteralPath $backup)) {
      Move-Item -LiteralPath $backup -Destination $dcc -Force
    }

    if (Test-Path -LiteralPath $csv) {
      Remove-Item -LiteralPath $csv -Force -ErrorAction SilentlyContinue
    }
  }
}
catch {
  Write-Error $_.Exception.Message
  Show-Help
  exit 1
}
