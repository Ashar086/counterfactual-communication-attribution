# Keep Windows from sleeping / dimming while campaign runs.
# Uses ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED pulse every 30s.
# Stops automatically when overnight_lf_campaign_final.json exists (or maxHours).

$ErrorActionPreference = "Continue"
$root = "C:\Users\BEST BUY COMPUTERS\OneDrive\Desktop\meta ai agent workshop"
Set-Location $root
$final = "results\overnight_lf_campaign_final.json"
$hb = "results\overnight_lf_keepawake_hb.txt"
$maxHours = 16
$start = Get-Date

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeSleep {
  [DllImport("kernel32.dll")]
  public static extern uint SetThreadExecutionState(uint esFlags);
  public const uint ES_CONTINUOUS = 0x80000000;
  public const uint ES_SYSTEM_REQUIRED = 0x00000001;
  public const uint ES_DISPLAY_REQUIRED = 0x00000002;
  public const uint ES_AWAYMODE_REQUIRED = 0x00000040;
}
"@

# Also force current scheme: sleep/hibernate never (AC)
try {
  powercfg /change standby-timeout-ac 0 | Out-Null
  powercfg /change hibernate-timeout-ac 0 | Out-Null
  powercfg /change monitor-timeout-ac 0 | Out-Null
} catch {}

function Write-Hb($msg) {
  $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $msg
  Add-Content -Path $hb -Value $line
}

Write-Hb "KEEP_AWAKE START"
$flags = [NativeSleep]::ES_CONTINUOUS -bor [NativeSleep]::ES_SYSTEM_REQUIRED -bor [NativeSleep]::ES_DISPLAY_REQUIRED -bor [NativeSleep]::ES_AWAYMODE_REQUIRED
[void][NativeSleep]::SetThreadExecutionState($flags)

while (-not (Test-Path $final)) {
  if (((Get-Date) - $start).TotalHours -gt $maxHours) { Write-Hb "KEEP_AWAKE TIMEOUT"; break }
  [void][NativeSleep]::SetThreadExecutionState($flags)
  Start-Sleep -Seconds 30
}

# Clear continuous requirement
[void][NativeSleep]::SetThreadExecutionState([NativeSleep]::ES_CONTINUOUS)
Write-Hb "KEEP_AWAKE STOP"
