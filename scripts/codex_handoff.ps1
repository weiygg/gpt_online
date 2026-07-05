[CmdletBinding()]
param(
    [switch]$InitIfNeeded,
    [Parameter(Mandatory = $false)]
    [string]$RemoteUrl,
    [string]$RemoteName = "origin",
    [string]$Branch = "main",
    [string]$GitUserName,
    [string]$GitUserEmail,
    [string]$CommitMessage = "Codex handoff",
    [switch]$OpenChatGPT,
    [string]$ChatGPTUrl = "https://chatgpt.com/",
    [string]$HandoffMessagePath,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)

    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Get-GitText {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & git @GitArgs 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        return $null
    }

    return (($output -join "`n").Trim())
}

function Normalize-GitHubUrl {
    param([string]$Url)

    if ([string]::IsNullOrWhiteSpace($Url)) {
        return $Url
    }

    try {
        $uri = [Uri]$Url
        if ($uri.Scheme -notin @("http", "https") -or $uri.Host -ne "github.com") {
            return $Url
        }

        $path = (($uri.AbsolutePath -split "/") | Where-Object { $_ }) -join "/"
        if ([string]::IsNullOrWhiteSpace($path)) {
            return $Url
        }

        $builder = [UriBuilder]::new($uri)
        $builder.Path = $path
        return $builder.Uri.AbsoluteUri
    }
    catch {
        return $Url
    }
}

function Convert-RemoteToWebUrl {
    param([string]$Url)

    if ([string]::IsNullOrWhiteSpace($Url)) {
        return $null
    }

    if ($Url -match "^git@github\.com:(?<path>.+?)(\.git)?$") {
        return "https://github.com/$($Matches.path -replace '\.git$', '')"
    }

    try {
        $uri = [Uri](Normalize-GitHubUrl $Url)
        if ($uri.Host -eq "github.com") {
            $path = $uri.AbsolutePath.TrimEnd("/") -replace "\.git$", ""
            return "$($uri.Scheme)://$($uri.Host)$path"
        }
    }
    catch {
        return $null
    }

    return $null
}

Assert-Command git

$repoRoot = Get-GitText rev-parse --show-toplevel
if (-not $repoRoot) {
    if (-not $InitIfNeeded) {
        throw "This folder is not a git repository. Re-run with -InitIfNeeded."
    }

    Invoke-Git init
    $repoRoot = Get-GitText rev-parse --show-toplevel
}

Set-Location -LiteralPath $repoRoot

if ($GitUserName) {
    Invoke-Git config user.name $GitUserName
}

if ($GitUserEmail) {
    Invoke-Git config user.email $GitUserEmail
}

if ($RemoteUrl) {
    $normalizedRemoteUrl = Normalize-GitHubUrl $RemoteUrl
    $currentRemoteUrl = Get-GitText remote get-url $RemoteName

    if ($currentRemoteUrl) {
        if ($currentRemoteUrl -ne $normalizedRemoteUrl) {
            Invoke-Git remote set-url $RemoteName $normalizedRemoteUrl
        }
    }
    else {
        Invoke-Git remote add $RemoteName $normalizedRemoteUrl
    }
}

if ($Branch) {
    $headSha = Get-GitText rev-parse --verify HEAD
    if ($headSha) {
        $currentBranch = Get-GitText branch --show-current
        if ($currentBranch -ne $Branch) {
            $localBranch = Get-GitText rev-parse --verify "refs/heads/$Branch"
            if ($localBranch) {
                Invoke-Git switch $Branch
            }
            else {
                Invoke-Git switch -c $Branch
            }
        }
    }
    else {
        Invoke-Git symbolic-ref HEAD "refs/heads/$Branch"
    }
}

Invoke-Git add -A
$status = Get-GitText status --porcelain

if ($status) {
    Invoke-Git commit -m $CommitMessage
}
else {
    Write-Host "No working tree changes to commit."
}

$commitSha = Get-GitText rev-parse HEAD
if (-not $commitSha) {
    throw "No commit exists after staging. Add at least one file before handoff."
}

$shortSha = Get-GitText rev-parse --short HEAD
$branchName = Get-GitText branch --show-current
if (-not $branchName) {
    $branchName = $Branch
}

$pushStatus = "not attempted"
if (-not $NoPush) {
    try {
        Invoke-Git push -u $RemoteName $branchName
        $pushStatus = "succeeded"
    }
    catch {
        Write-Error @"
GitHub push failed.

The local commit was created, but GitHub rejected the push. On Git for Windows,
refresh credentials with:

  git credential-manager github login

Then re-run this script with the same arguments. Original error:
$($_.Exception.Message)
"@
        throw
    }
}
else {
    $pushStatus = "skipped by -NoPush"
}

$remoteForMessage = Get-GitText remote get-url $RemoteName
$repoWebUrl = Convert-RemoteToWebUrl $remoteForMessage
$branchWebUrl = $null
if ($repoWebUrl -and $branchName) {
    $branchWebUrl = "$repoWebUrl/tree/$branchName"
}

$handoffLines = @(
    "Codex handoff complete.",
    "",
    "Repository: $remoteForMessage",
    "Web URL: $repoWebUrl",
    "Branch: $branchName",
    "Branch URL: $branchWebUrl",
    "Commit: $commitSha",
    "Commit message: $CommitMessage",
    "Push status: $pushStatus",
    "Workspace: $repoRoot",
    "",
    "Please use the authorized GitHub repository access in ChatGPT to inspect this branch and summarize what Codex changed. Focus on changed files, how to run or verify the work, and any risks or follow-up tasks."
)

$handoffMessage = $handoffLines -join "`r`n"

if (-not $HandoffMessagePath) {
    $safeRepoName = (Split-Path -Leaf $repoRoot) -replace "[^A-Za-z0-9_.-]", "_"
    $HandoffMessagePath = Join-Path $env:TEMP "codex_handoff_$safeRepoName.md"
}

Set-Content -LiteralPath $HandoffMessagePath -Value $handoffMessage -Encoding UTF8

try {
    Set-Clipboard -Value $handoffMessage
    Write-Host "Copied ChatGPT handoff message to clipboard."
}
catch {
    Write-Warning "Could not copy handoff message to clipboard: $($_.Exception.Message)"
}

if ($OpenChatGPT) {
    Start-Process $ChatGPTUrl
}

Write-Host ""
Write-Host "Handoff complete."
Write-Host "Repository: $remoteForMessage"
Write-Host "Branch: $branchName"
Write-Host "Commit: $shortSha"
Write-Host "Message file: $HandoffMessagePath"
