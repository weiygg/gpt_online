param(
  [string]$Topics = ".\medical_imaging_ai_lit_agent\config\topics.example.json",
  [string]$OutDir = ".\medical_imaging_ai_lit_agent\outputs",
  [string]$ChatId = "",
  [string]$UserId = "",
  [ValidateSet("bot", "user")]
  [string]$As = "bot",
  [switch]$Send,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "daily_literature_scan.py"
$argsList = @(
  $scriptPath,
  "--topics", $Topics,
  "--outdir", $OutDir
)

if ($ChatId) {
  $argsList += @("--chat-id", $ChatId)
}
if ($UserId) {
  $argsList += @("--user-id", $UserId)
}
if ($As) {
  $argsList += @("--as-identity", $As)
}
if ($Send) {
  $argsList += "--send-feishu"
}
if ($DryRun) {
  $argsList += "--dry-run"
}

python @argsList
