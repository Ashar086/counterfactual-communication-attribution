# Overnight LF campaign watchdog
# Restarts the batched campaign if it exits non-zero, until final artifact exists.
$ErrorActionPreference = "Continue"
$root = "C:\Users\BEST BUY COMPUTERS\OneDrive\Desktop\meta ai agent workshop"
Set-Location $root
$final = "results\overnight_lf_campaign_final.json"
$log = "results\overnight_lf_campaign.log"
$attempt = 0
while (-not (Test-Path $final)) {
  $attempt++
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path $log -Value "`n==== WATCHDOG start attempt=$attempt at $stamp ====`n"
  Write-Host "WATCHDOG attempt=$attempt starting campaign"
  python -u -m commscm.experiments.part_vi_b_overnight_lf_campaign 2>&1 | Tee-Object -FilePath $log -Append
  $code = $LASTEXITCODE
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path $log -Value "`n==== WATCHDOG exit code=$code at $stamp ====`n"
  if (Test-Path $final) { break }
  # Brief backoff then resume (campaign is resume-safe)
  Start-Sleep -Seconds 30
  # Clear stuck containers
  docker ps -aq | ForEach-Object { docker rm -f $_ 2>$null }
}
Write-Host "WATCHDOG done; final exists"
