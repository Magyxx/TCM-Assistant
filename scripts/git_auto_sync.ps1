param(
    [string]$Repo = "D:\code\obsidian",
    [int]$DebounceSeconds = 8,
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$GitUserName = "Magyxx",
    [string]$GitUserEmail = "Magyxx@users.noreply.github.com"
)

$ErrorActionPreference = "Stop"
$repoPath = (Resolve-Path -LiteralPath $Repo).Path
$stateDir = Join-Path $repoPath ".auto-sync"
$logPath = Join-Path $stateDir "git-auto-sync.log"
$pidPath = Join-Path $stateDir "git-auto-sync.pid"

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
Set-Content -LiteralPath $pidPath -Value $PID -Encoding UTF8

function Write-SyncLog {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Value "[$stamp] $Message" -Encoding UTF8
}

function Invoke-Git {
    param([string[]]$Args)
    $output = & git -C $repoPath @Args 2>&1
    $exitCode = $LASTEXITCODE
    if ($output) {
        Write-SyncLog ($output -join "`n")
    }
    if ($exitCode -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $exitCode"
    }
}

function Invoke-Sync {
    try {
        Write-SyncLog "sync start"
        Invoke-Git @("fetch", $Remote)
        Invoke-Git @("pull", "--rebase", "--autostash", $Remote, $Branch)
        Invoke-Git @("add", "-A")

        $changes = & git -C $repoPath status --porcelain 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "git status failed: $changes"
        }

        if ($changes) {
            $message = "auto-sync: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
            Invoke-Git @("-c", "user.name=$GitUserName", "-c", "user.email=$GitUserEmail", "commit", "-m", $message)
            Invoke-Git @("push", $Remote, $Branch)
            Write-SyncLog "sync pushed"
        } else {
            Write-SyncLog "sync clean"
        }
    } catch {
        Write-SyncLog "sync failed: $($_.Exception.Message)"
    }
}

$pending = $false
$lastChange = Get-Date

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $repoPath
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.NotifyFilter = [System.IO.NotifyFilters]"FileName, DirectoryName, LastWrite, Size"

$action = {
    $path = $Event.SourceEventArgs.FullPath
    if ($path -like "*\.git\*" -or $path -like "*\.auto-sync\*" -or $path -like "*\.venv\*" -or $path -like "*\__pycache__\*") {
        return
    }
    $script:pending = $true
    $script:lastChange = Get-Date
}

$subscriptions = @()
$subscriptions += Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action
$subscriptions += Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action
$subscriptions += Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action $action
$subscriptions += Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $action

Write-SyncLog "watching $repoPath"
Invoke-Sync

try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($pending -and ((Get-Date) - $lastChange).TotalSeconds -ge $DebounceSeconds) {
            $pending = $false
            Invoke-Sync
        }
    }
} finally {
    foreach ($subscription in $subscriptions) {
        Unregister-Event -SubscriptionId $subscription.Id -ErrorAction SilentlyContinue
    }
    $watcher.Dispose()
    Write-SyncLog "watch stopped"
}
