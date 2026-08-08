# Autonomous overnight watchdog for LF campaign.
# Decisions (no user input):
# - If final exists -> exit success
# - If campaign lock PID dead OR log silent > 45 min -> kill leftovers, clear stale lock, resume
# - If free disk < 12 GB -> prune sweb.eval images
# - Never modify CommSCM core; only restart resume-safe campaign

$ErrorActionPreference = "Continue"
$root = "C:\Users\BEST BUY COMPUTERS\OneDrive\Desktop\meta ai agent workshop"
Set-Location $root

$final = "results\overnight_lf_campaign_final.json"
$lock = "results\overnight_lf_campaign.lock"
$log = "results\overnight_lf_campaign_run.log"
$hb = "results\overnight_lf_watchdog_hb.txt"
$maxHours = 16
$silentMin = 45
$start = Get-Date

function Write-Hb($msg) {
  $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $msg
  Add-Content -Path $hb -Value $line
  Write-Host $line
}

function Get-LockPid {
  if (-not (Test-Path $lock)) { return $null }
  try { return [int]((Get-Content $lock -Raw).Trim().Split()[0]) } catch { return $null }
}

function Test-PidAlive([int]$procId) {
  try { return $null -ne (Get-Process -Id $procId -ErrorAction Stop) } catch { return $false }
}

function Clear-DockerLeftovers {
  try {
    docker ps -aq 2>$null | ForEach-Object { docker rm -f $_ 2>$null | Out-Null }
  } catch {}
  $free = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
  if ($free -lt 12) {
    Write-Hb "disk low free=$free GB; pruning sweb.eval"
    docker images --format "{{.Repository}}:{{.Tag}}" 2>$null | Select-String "sweb.eval" | ForEach-Object {
      docker rmi -f $_.Line 2>$null | Out-Null
    }
    docker system prune -f 2>$null | Out-Null
  }
}

function Start-Campaign {
  Clear-DockerLeftovers
  if (Test-Path $lock) {
    $old = Get-LockPid
    if ($old -and -not (Test-PidAlive $old)) {
      Remove-Item $lock -Force -ErrorAction SilentlyContinue
    } elseif ($old -and (Test-PidAlive $old)) {
      Write-Hb "campaign already alive pid=$old"
      return
    } else {
      Remove-Item $lock -Force -ErrorAction SilentlyContinue
    }
  }
  # Rotate huge log lightly
  if ((Test-Path $log) -and ((Get-Item $log).Length -gt 80MB)) {
    Move-Item $log ("results\overnight_lf_campaign_run_{0:HHmmss}.bak.log" -f (Get-Date)) -Force -ErrorAction SilentlyContinue
  }
  Write-Hb "starting campaign resume"
  $p = Start-Process -FilePath "python" -ArgumentList "-u","-m","commscm.experiments.part_vi_b_overnight_lf_campaign" `
    -WorkingDirectory $root `
    -RedirectStandardOutput $log `
    -RedirectStandardError "results\overnight_lf_campaign_err.log" `
    -WindowStyle Hidden -PassThru
  Write-Hb "started pid=$($p.Id)"
  Start-Sleep -Seconds 20
}

Write-Hb "WATCHDOG START maxHours=$maxHours silentMin=$silentMin"

while (-not (Test-Path $final)) {
  if (((Get-Date) - $start).TotalHours -gt $maxHours) {
    Write-Hb "WATCHDOG TIMEOUT after ${maxHours}h"
    break
  }

  $lp = Get-LockPid
  $alive = $false
  if ($lp) { $alive = Test-PidAlive $lp }

  $logAgeMin = 9999
  if (Test-Path $log) {
    $logAgeMin = ((Get-Date) - (Get-Item $log).LastWriteTime).TotalMinutes
  }

  $ckMsg = "no_ckpt"
  if (Test-Path "results\overnight_lf_campaign_checkpoint.json") {
    try {
      $ck = Get-Content "results\overnight_lf_campaign_checkpoint.json" -Raw | ConvertFrom-Json
      $ckMsg = "batches=$($ck.batches_done)/13 gold_r1=$($ck.oracle_gold_partial.resolve_at_1_mean)"
    } catch {}
  }

  Write-Hb "alive=$alive pid=$lp log_age_min=$([math]::Round($logAgeMin,1)) $ckMsg free=$([math]::Round((Get-PSDrive C).Free/1GB,1))GB"

  if ((Test-Path $final)) { break }

  if (-not $alive) {
    Write-Hb "campaign dead -> resume"
    Start-Campaign
  } elseif ($logAgeMin -gt $silentMin) {
    Write-Hb "log silent > ${silentMin}m -> kill and resume"
    try { Stop-Process -Id $lp -Force -ErrorAction SilentlyContinue } catch {}
    Get-CimInstance Win32_Process | Where-Object {
      $_.CommandLine -like '*overnight_lf_campaign*' -or $_.CommandLine -like '*run_evaluation_lf*'
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item $lock -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 10
    Start-Campaign
  }

  Start-Sleep -Seconds 180
}

if (Test-Path $final) {
  Write-Hb "DONE final exists"
  Get-Content $final | Out-File -FilePath "results\overnight_lf_watchdog_final_copy.json" -Encoding utf8
} else {
  Write-Hb "EXIT without final"
}
