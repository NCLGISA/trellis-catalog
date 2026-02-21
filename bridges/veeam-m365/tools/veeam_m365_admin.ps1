<#
.SYNOPSIS
    Veeam Backup for Microsoft 365 administration script.
.DESCRIPTION
    Manages VBO backup jobs, restore operations, organization inventory, and
    health monitoring via the Veeam.Archiver.PowerShell module (220 cmdlets).

    Action groups:
      Health/Status (read-only):
        status, jobs, sessions, session-log, license, repos,
        protection-report, storage-report
      Organization/Inventory (read-only):
        org-stats, users, groups, sites, teams
      Job Management (operational):
        start-job, stop-job, enable-job, disable-job
      Restore Operations (operational):
        restore-points, explore-exchange, explore-sharepoint, explore-teams
      File-Level Restore (operational):
        browse-channel-files, search-teams-files, restore-teams-file,
        restore-onedrive-file, restore-sharepoint-file
.PARAMETER Action
    Operation to perform.
.PARAMETER Job
    Backup job name (default: first job found). For restore-teams-file, this
    is the file name pattern to match.
.PARAMETER User
    User email or display name for user-scoped actions. For Teams file
    actions, this is the team display name.
.PARAMETER Filter
    Search filter for users/groups/sites/teams (substring match). For
    browse-channel-files/restore-teams-file, this is the channel name
    (default: General). For search-teams-files, this is the search query.
.PARAMETER Path
    Slash-separated folder path for Teams channel file navigation
    (e.g. "Bids/2026/RFP"). Used by browse-channel-files and
    restore-teams-file.
.PARAMETER Count
    Maximum items to return for list actions (default: 25).
.PARAMETER SessionId
    Session ID for session-log action.
.PARAMETER RestoreDir
    Directory for file restore operations (default: C:\Temp\veeam-restore).
.EXAMPLE
    .\veeam_m365_admin.ps1 -Action status
    .\veeam_m365_admin.ps1 -Action sessions -Count 5
    .\veeam_m365_admin.ps1 -Action session-log -SessionId "abc-123"
    .\veeam_m365_admin.ps1 -Action users -Filter "smith"
    .\veeam_m365_admin.ps1 -Action start-job -Job "Daily Backup"
    .\veeam_m365_admin.ps1 -Action restore-points -User "user@example.com"
    .\veeam_m365_admin.ps1 -Action explore-exchange -User "user@example.com"
    .\veeam_m365_admin.ps1 -Action browse-channel-files -User "Engineering" -Filter "General" -Path "Projects/2026"
    .\veeam_m365_admin.ps1 -Action search-teams-files -Filter "filename: report"
    .\veeam_m365_admin.ps1 -Action search-teams-files -User "Engineering" -Filter "filename: report"
    .\veeam_m365_admin.ps1 -Action restore-teams-file -User "Engineering" -Filter "General" -Path "Projects/2026/RFP" -Job "report"
    .\veeam_m365_admin.ps1 -Action restore-onedrive-file -User "user@example.com" -Path "Documents/Reports" -Job "quarterly"
    .\veeam_m365_admin.ps1 -Action restore-sharepoint-file -User "IT Department" -Filter "Shared Documents" -Path "Policies" -Job ".*\.pdf"
#>
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        'status','jobs','sessions','session-log','license','repos',
        'protection-report','storage-report',
        'org-stats','users','groups','sites','teams',
        'start-job','stop-job','enable-job','disable-job',
        'restore-points','explore-exchange','explore-sharepoint','explore-teams',
        'browse-channel-files','search-teams-files','restore-teams-file',
        'restore-onedrive-file','restore-sharepoint-file'
    )]
    [string]$Action,

    [string]$Job,
    [string]$User,
    [string]$Filter,
    [string]$Path,
    [int]$Count = 25,
    [string]$SessionId,
    [string]$RestoreDir = 'C:\Temp\veeam-restore'
)

$ErrorActionPreference = 'Stop'

Import-Module Veeam.Archiver.PowerShell -ErrorAction Stop

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Resolve-VBOJob {
    param([string]$JobName)
    if ($JobName) {
        $j = Get-VBOJob | Where-Object { $_.Name -eq $JobName }
        if (-not $j) { throw "Job '$JobName' not found. Use -Action jobs to list available jobs." }
        return $j
    }
    return Get-VBOJob | Select-Object -First 1
}

function Resolve-VBOOrganization {
    return Get-VBOOrganization | Select-Object -First 1
}

function Format-Duration {
    param([datetime]$Start, [datetime]$End)
    $span = $End - $Start
    if ($span.TotalHours -ge 1) { return "{0:0}h {1:0}m" -f $span.TotalHours, $span.Minutes }
    if ($span.TotalMinutes -ge 1) { return "{0:0}m {1:0}s" -f $span.TotalMinutes, $span.Seconds }
    return "{0:0}s" -f $span.TotalSeconds
}

function Resolve-VETPath {
    param(
        [Parameter(Mandatory=$true)]$ChannelRef,
        [Parameter(Mandatory=$true)][object[]]$RootFiles,
        [string]$FolderPath
    )
    if (-not $FolderPath -or $FolderPath -eq '/' -or $FolderPath -eq '') {
        return @{ Files = $RootFiles; CurrentPath = '/' }
    }
    $segments = $FolderPath.Trim('/').Split('/')
    $current = $null
    $traversed = @()
    foreach ($seg in $segments) {
        $candidates = if ($current) { @(Get-VETFile -Channel $ChannelRef -ParentFile $current) } else { $RootFiles }
        $folder = $candidates | Where-Object { $_.IsFolder -and $_.Name -eq $seg } | Select-Object -First 1
        if (-not $folder) { throw "Folder '$seg' not found in path '/$($traversed -join '/')'. Available: $(($candidates | Where-Object { $_.IsFolder } | ForEach-Object { $_.Name }) -join ', ')" }
        $current = $folder
        $traversed += $seg
    }
    $children = @(Get-VETFile -Channel $ChannelRef -ParentFile $current)
    return @{ Files = $children; CurrentPath = "/$($traversed -join '/')" }
}

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

switch ($Action) {

    # -- Health / Status ----------------------------------------------------

    'status' {
        $result = @{}

        $ver = Get-VBOVersion
        $result['version'] = $ver.ToString()

        $lic = Get-VBOLicense
        $daysLeft = [math]::Round(($lic.ExpirationDate - (Get-Date)).TotalDays)
        $result['license'] = @{
            Type           = $lic.Type.ToString()
            TotalSeats     = $lic.TotalNumber
            UsedSeats      = $lic.UsedNumber
            ExpirationDate = $lic.ExpirationDate.ToString('yyyy-MM-dd')
            DaysRemaining  = $daysLeft
            Overprovisioned = $lic.UsedNumber -gt $lic.TotalNumber
        }

        $veeamSvcs = Get-Service -Name 'Veeam.Archiver.*','nats-server','postgresql-x64-15' -ErrorAction SilentlyContinue
        $result['services'] = $veeamSvcs | ForEach-Object {
            @{ Name = $_.DisplayName; Status = $_.Status.ToString() }
        }

        $proxies = Get-VBOProxy
        $result['proxies'] = $proxies | ForEach-Object {
            @{ Hostname = $_.Hostname; State = $_.State.ToString(); Type = $_.Type.ToString(); Threads = $_.ThreadsNumber }
        }

        $org = Resolve-VBOOrganization
        if ($org) {
            $result['organization'] = @{
                Name       = $org.Name
                OfficeName = $org.OfficeName
                Type       = $org.Type.ToString()
                IsBackedUp = $org.IsBackedUp
            }
        }

        $allJobs = Get-VBOJob
        $result['jobs_summary'] = $allJobs | ForEach-Object {
            $lastSession = Get-VBOJobSession -Job $_ | Sort-Object CreationTime -Descending | Select-Object -First 1
            @{
                Name       = $_.Name
                IsEnabled  = $_.IsEnabled
                LastStatus = if ($lastSession) { $lastSession.Status.ToString() } else { 'Never' }
                LastRun    = if ($lastSession) { $lastSession.CreationTime.ToString('yyyy-MM-dd HH:mm') } else { $null }
            }
        }

        $result | ConvertTo-Json -Depth 5
    }

    'jobs' {
        $allJobs = Get-VBOJob
        $copyJobs = Get-VBOCopyJob -ErrorAction SilentlyContinue

        $result = @{ backup_jobs = @(); copy_jobs = @() }

        $result['backup_jobs'] = @($allJobs | ForEach-Object {
            $lastSession = Get-VBOJobSession -Job $_ | Sort-Object CreationTime -Descending | Select-Object -First 1
            @{
                Name        = $_.Name
                IsEnabled   = $_.IsEnabled
                Description = $_.Description
                LastStatus  = if ($lastSession) { $lastSession.Status.ToString() } else { 'Never' }
                LastRun     = if ($lastSession) { $lastSession.CreationTime.ToString('yyyy-MM-dd HH:mm') } else { $null }
                LastEnd     = if ($lastSession -and $lastSession.EndTime.Year -gt 2000) { $lastSession.EndTime.ToString('yyyy-MM-dd HH:mm') } else { $null }
                Duration    = if ($lastSession -and $lastSession.EndTime.Year -gt 2000) { Format-Duration $lastSession.CreationTime $lastSession.EndTime } else { $null }
            }
        })

        if ($copyJobs) {
            $result['copy_jobs'] = @($copyJobs | ForEach-Object {
                @{ Name = $_.Name; IsEnabled = $_.IsEnabled; Description = $_.Description }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'sessions' {
        $j = Resolve-VBOJob -JobName $Job
        $sessions = Get-VBOJobSession -Job $j | Sort-Object CreationTime -Descending | Select-Object -First $Count

        $result = @{
            job_name = $j.Name
            sessions = @($sessions | ForEach-Object {
                @{
                    Id           = $_.Id.ToString()
                    Status       = $_.Status.ToString()
                    CreationTime = $_.CreationTime.ToString('yyyy-MM-dd HH:mm:ss')
                    EndTime      = if ($_.EndTime.Year -gt 2000) { $_.EndTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'Running' }
                    Duration     = if ($_.EndTime.Year -gt 2000) { Format-Duration $_.CreationTime $_.EndTime } else { 'In progress' }
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'session-log' {
        if (-not $SessionId) {
            $j = Resolve-VBOJob -JobName $Job
            $lastSession = Get-VBOJobSession -Job $j | Sort-Object CreationTime -Descending | Select-Object -First 1
            if (-not $lastSession) { throw "No sessions found for job '$($j.Name)'." }
            $SessionId = $lastSession.Id.ToString()
        }

        $j = Resolve-VBOJob -JobName $Job
        $allSessions = Get-VBOJobSession -Job $j
        $session = $allSessions | Where-Object { $_.Id.ToString() -eq $SessionId }
        if (-not $session) { throw "Session '$SessionId' not found." }

        $result = @{
            session_id   = $session.Id.ToString()
            status       = $session.Status.ToString()
            creation     = $session.CreationTime.ToString('yyyy-MM-dd HH:mm:ss')
            end_time     = if ($session.EndTime.Year -gt 2000) { $session.EndTime.ToString('yyyy-MM-dd HH:mm:ss') } else { 'Running' }
        }

        $logProps = $session | Get-Member -MemberType Property | Where-Object { $_.Name -match 'Log|Message|Detail' }
        if ($session.PSObject.Properties['Log']) {
            $result['log'] = $session.Log | ForEach-Object { $_.ToString() }
        }

        $props = @('ProcessedObjects','TransferredData','Statistics')
        foreach ($p in $props) {
            if ($session.PSObject.Properties[$p]) {
                $val = $session.$p
                if ($val) { $result[$p] = $val.ToString() }
            }
        }

        try {
            $tempLog = [System.IO.Path]::GetTempFileName()
            Export-VBOLog -From $session.CreationTime -To $(if ($session.EndTime.Year -gt 2000) { $session.EndTime } else { Get-Date }) -Path $tempLog -ErrorAction SilentlyContinue
            $logContent = Get-Content $tempLog -Tail 200 -ErrorAction SilentlyContinue
            $warnings = $logContent | Where-Object { $_ -match 'Warning|Error|Failed|Throttl' }
            $result['log_warnings_errors'] = @($warnings | Select-Object -First 50)
            Remove-Item $tempLog -Force -ErrorAction SilentlyContinue
        } catch {
            $result['log_export_error'] = $_.Exception.Message
        }

        $result | ConvertTo-Json -Depth 5
    }

    'license' {
        $lic = Get-VBOLicense
        $daysLeft = [math]::Round(($lic.ExpirationDate - (Get-Date)).TotalDays)
        $licensedUsers = Get-VBOLicensedUser -ErrorAction SilentlyContinue

        $result = @{
            type             = $lic.Type.ToString()
            total_seats      = $lic.TotalNumber
            used_seats       = $lic.UsedNumber
            available_seats  = $lic.TotalNumber - $lic.UsedNumber
            expiration_date  = $lic.ExpirationDate.ToString('yyyy-MM-dd')
            days_remaining   = $daysLeft
            overprovisioned  = $lic.UsedNumber -gt $lic.TotalNumber
            overage          = if ($lic.UsedNumber -gt $lic.TotalNumber) { $lic.UsedNumber - $lic.TotalNumber } else { 0 }
            licensed_user_count = if ($licensedUsers) { ($licensedUsers | Measure-Object).Count } else { $null }
        }

        $result | ConvertTo-Json -Depth 5
    }

    'repos' {
        $repos = Get-VBORepository

        $result = @{
            repositories = @($repos | ForEach-Object {
                @{
                    Name            = $_.Name
                    Description     = $_.Description
                    Path            = $_.Path
                    RetentionType   = $_.RetentionType.ToString()
                    RetentionPeriod = $_.RetentionPeriod.ToString()
                    IsOutOfDate     = $_.IsOutOfDate
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'protection-report' {
        $report = Get-VBOMailboxProtectionReport -ErrorAction SilentlyContinue
        $userReport = Get-VBOUserProtectionReport -ErrorAction SilentlyContinue

        $result = @{}
        if ($report) {
            $result['mailbox_protection'] = $report | ForEach-Object {
                $_ | Select-Object * | ConvertTo-Json | ConvertFrom-Json
            }
        }
        if ($userReport) {
            $result['user_protection'] = $userReport | ForEach-Object {
                $_ | Select-Object * | ConvertTo-Json | ConvertFrom-Json
            }
        }

        if (-not $report -and -not $userReport) {
            $lic = Get-VBOLicense
            $org = Resolve-VBOOrganization
            $userCount = (Get-VBOOrganizationUser -Organization $org -ErrorAction SilentlyContinue | Measure-Object).Count
            $result = @{
                organization   = $org.Name
                total_users    = $userCount
                licensed_seats = $lic.TotalNumber
                used_seats     = $lic.UsedNumber
            }
        }

        $result | ConvertTo-Json -Depth 5
    }

    'storage-report' {
        $report = Get-VBOStorageConsumptionReport -ErrorAction SilentlyContinue

        $result = @{}
        if ($report) {
            $result['storage_consumption'] = $report | ForEach-Object {
                $_ | Select-Object * | ConvertTo-Json | ConvertFrom-Json
            }
        }

        $repos = Get-VBORepository
        $result['repositories'] = @($repos | ForEach-Object {
            @{
                Name            = $_.Name
                Path            = $_.Path
                RetentionType   = $_.RetentionType.ToString()
                RetentionPeriod = $_.RetentionPeriod.ToString()
            }
        })

        $result | ConvertTo-Json -Depth 5
    }

    # -- Organization / Inventory -------------------------------------------

    'org-stats' {
        $org = Resolve-VBOOrganization
        $users  = (Get-VBOOrganizationUser  -Organization $org -ErrorAction SilentlyContinue | Measure-Object).Count
        $groups = (Get-VBOOrganizationGroup -Organization $org -ErrorAction SilentlyContinue | Measure-Object).Count
        $sites  = (Get-VBOOrganizationSite  -Organization $org -ErrorAction SilentlyContinue | Measure-Object).Count
        $teams  = (Get-VBOOrganizationTeam  -Organization $org -ErrorAction SilentlyContinue | Measure-Object).Count

        $lic = Get-VBOLicense

        $result = @{
            organization = $org.Name
            office_name  = $org.OfficeName
            type         = $org.Type.ToString()
            is_backed_up = $org.IsBackedUp
            users        = $users
            groups       = $groups
            sites        = $sites
            teams        = $teams
            licensed_seats = $lic.TotalNumber
            used_seats     = $lic.UsedNumber
        }

        $result | ConvertTo-Json -Depth 5
    }

    'users' {
        $org = Resolve-VBOOrganization
        $allUsers = Get-VBOOrganizationUser -Organization $org -ErrorAction SilentlyContinue

        if ($Filter) {
            $allUsers = $allUsers | Where-Object {
                $_.DisplayName -match $Filter -or $_.UserName -match $Filter
            }
        }

        $result = @{
            organization = $org.Name
            filter       = $Filter
            total_matched = ($allUsers | Measure-Object).Count
            users        = @($allUsers | Select-Object -First $Count | ForEach-Object {
                @{
                    DisplayName = $_.DisplayName
                    UserName    = $_.UserName
                    Type        = $_.Type.ToString()
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'groups' {
        $org = Resolve-VBOOrganization
        $allGroups = Get-VBOOrganizationGroup -Organization $org -ErrorAction SilentlyContinue

        if ($Filter) {
            $allGroups = $allGroups | Where-Object { $_.DisplayName -match $Filter }
        }

        $result = @{
            organization  = $org.Name
            filter        = $Filter
            total_matched = ($allGroups | Measure-Object).Count
            groups        = @($allGroups | Select-Object -First $Count | ForEach-Object {
                @{
                    DisplayName = $_.DisplayName
                    Type        = $_.Type.ToString()
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'sites' {
        $org = Resolve-VBOOrganization
        $allSites = Get-VBOOrganizationSite -Organization $org -ErrorAction SilentlyContinue

        if ($Filter) {
            $allSites = $allSites | Where-Object { $_.Title -match $Filter -or $_.URL -match $Filter }
        }

        $result = @{
            organization  = $org.Name
            filter        = $Filter
            total_matched = ($allSites | Measure-Object).Count
            sites         = @($allSites | Select-Object -First $Count | ForEach-Object {
                @{
                    Title = $_.Title
                    URL   = $_.URL
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'teams' {
        $org = Resolve-VBOOrganization
        $allTeams = Get-VBOOrganizationTeam -Organization $org -ErrorAction SilentlyContinue

        if ($Filter) {
            $allTeams = $allTeams | Where-Object { $_.DisplayName -match $Filter }
        }

        $result = @{
            organization  = $org.Name
            filter        = $Filter
            total_matched = ($allTeams | Measure-Object).Count
            teams         = @($allTeams | Select-Object -First $Count | ForEach-Object {
                @{
                    DisplayName = $_.DisplayName
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    # -- Job Management -----------------------------------------------------

    'start-job' {
        $j = Resolve-VBOJob -JobName $Job
        Start-VBOJob -Job $j
        @{ action = 'start-job'; job = $j.Name; result = 'started' } | ConvertTo-Json
    }

    'stop-job' {
        $j = Resolve-VBOJob -JobName $Job
        Stop-VBOJob -Job $j
        @{ action = 'stop-job'; job = $j.Name; result = 'stopped' } | ConvertTo-Json
    }

    'enable-job' {
        $j = Resolve-VBOJob -JobName $Job
        Enable-VBOJob -Job $j
        @{ action = 'enable-job'; job = $j.Name; result = 'enabled' } | ConvertTo-Json
    }

    'disable-job' {
        $j = Resolve-VBOJob -JobName $Job
        Disable-VBOJob -Job $j
        @{ action = 'disable-job'; job = $j.Name; result = 'disabled' } | ConvertTo-Json
    }

    # -- Restore Operations -------------------------------------------------

    'restore-points' {
        if (-not $User) { throw "The -User parameter is required for restore-points. Provide an email or display name." }

        $org = Resolve-VBOOrganization
        $allUsers = Get-VBOOrganizationUser -Organization $org -ErrorAction SilentlyContinue
        $targetUser = $allUsers | Where-Object {
            $_.UserName -eq $User -or $_.DisplayName -eq $User -or $_.UserName -match $User
        } | Select-Object -First 1

        if (-not $targetUser) { throw "User '$User' not found in organization." }

        $restorePoints = Get-VBORestorePoint | Where-Object {
            $_.BackedUpUserDisplayName -eq $targetUser.DisplayName -or
            $_.BackedUpUserName -eq $targetUser.UserName
        } | Sort-Object BackupTime -Descending | Select-Object -First $Count

        if (-not $restorePoints) {
            $restorePoints = Get-VBORestorePoint | Sort-Object BackupTime -Descending | Select-Object -First $Count
        }

        $result = @{
            user           = $targetUser.DisplayName
            user_name      = $targetUser.UserName
            restore_points = @($restorePoints | ForEach-Object {
                @{
                    Id         = if ($_.Id) { $_.Id.ToString() } else { $null }
                    BackupTime = $_.BackupTime.ToString('yyyy-MM-dd HH:mm:ss')
                }
            })
        }

        $result | ConvertTo-Json -Depth 5
    }

    'explore-exchange' {
        if (-not $User) { throw "The -User parameter is required for explore-exchange. Provide an email or display name." }

        $org = Resolve-VBOOrganization
        $allUsers = Get-VBOOrganizationUser -Organization $org -ErrorAction SilentlyContinue
        $targetUser = $allUsers | Where-Object {
            $_.UserName -eq $User -or $_.DisplayName -eq $User -or $_.UserName -match $User
        } | Select-Object -First 1

        if (-not $targetUser) { throw "User '$User' not found in organization." }

        $result = @{ user = $targetUser.DisplayName; user_name = $targetUser.UserName }

        try {
            $session = Start-VBOExchangeItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $databases = Get-VEXDatabase -Session $session
            $result['databases'] = @($databases | ForEach-Object {
                @{ Name = $_.Name; Id = if ($_.Id) { $_.Id.ToString() } else { $null } }
            })

            $mailbox = Get-VEXMailbox -Session $session | Where-Object {
                $_.UserDisplayName -eq $targetUser.DisplayName -or $_.UserName -eq $targetUser.UserName -or $_.UserName -match $User
            } | Select-Object -First 1

            if ($mailbox) {
                $result['mailbox'] = @{ Name = $mailbox.UserDisplayName; Email = $mailbox.UserName }

                $folders = Get-VEXFolder -Mailbox $mailbox
                $result['folders'] = @($folders | Select-Object -First $Count | ForEach-Object {
                    @{ Name = $_.Name; ItemCount = $_.ItemCount; Type = $_.Type.ToString() }
                })
            } else {
                $result['mailbox_note'] = "Mailbox not found in restore data for '$User'. The user may not have Exchange backup data."
            }

            Stop-VBOExchangeItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOExchangeItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    'explore-sharepoint' {
        if (-not $User) { throw "The -User parameter is required for explore-sharepoint. Provide an email, display name, or site URL." }

        $org = Resolve-VBOOrganization

        $result = @{ search = $User }

        try {
            $session = Start-VBOSharePointItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $vespOrg = Get-VESPOrganization -Session $session
            $sites = Get-VESPSite -Organization $vespOrg | Where-Object {
                $_.Name -match $User -or $_.Url -match $User
            } | Select-Object -First $Count

            if (-not $sites) {
                $sites = Get-VESPSite -Organization $vespOrg | Select-Object -First $Count
                $result['note'] = "Filter '$User' matched no sites. Showing first $Count sites."
            }

            $result['sites'] = @($sites | ForEach-Object {
                @{ Name = $_.Name; URL = $_.Url }
            })

            if (($sites | Measure-Object).Count -eq 1) {
                $site = $sites | Select-Object -First 1
                $docLibs = Get-VESPDocumentLibrary -Site $site -ErrorAction SilentlyContinue
                $result['document_libraries'] = @($docLibs | Select-Object -First $Count | ForEach-Object {
                    @{ Name = $_.Name; URL = $_.URL; ItemCount = $_.ItemCount }
                })
            }

            Stop-VBOSharePointItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOSharePointItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    'explore-teams' {
        if (-not $User) { throw "The -User parameter is required for explore-teams. Provide a team name to search for." }

        $org = Resolve-VBOOrganization

        $result = @{ search = $User }

        try {
            $session = Start-VBOTeamsItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $vetOrg = Get-VETOrganization -Session $session
            $allTeams = Get-VETTeam -Organization $vetOrg
            $matchedTeams = $allTeams | Where-Object { $_.DisplayName -match $User }

            if (-not $matchedTeams) {
                $matchedTeams = $allTeams | Select-Object -First $Count
                $result['note'] = "Filter '$User' matched no teams. Showing first $Count teams."
            }

            $result['teams'] = @($matchedTeams | Select-Object -First $Count | ForEach-Object {
                $team = $_
                $channels = Get-VETChannel -Team $team -ErrorAction SilentlyContinue
                @{
                    DisplayName = $team.DisplayName
                    Channels    = @($channels | ForEach-Object { @{ DisplayName = $_.DisplayName; Type = $_.Type.ToString() } })
                }
            })

            Stop-VBOTeamsItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOTeamsItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    # -- File-Level Restore Operations --------------------------------------

    'browse-channel-files' {
        if (-not $User) { throw "The -User parameter is required for browse-channel-files. Provide a team name." }

        $org = Resolve-VBOOrganization
        $channelName = if ($Filter) { $Filter } else { 'General' }

        $result = @{ team = $User; channel = $channelName; path = if ($Path) { $Path } else { '/' } }

        try {
            $session = Start-VBOTeamsItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $vetOrg = Get-VETOrganization -Session $session
            $team = Get-VETTeam -Organization $vetOrg | Where-Object { $_.DisplayName -match $User } | Select-Object -First 1
            if (-not $team) { throw "Team matching '$User' not found." }
            $result['team_resolved'] = $team.DisplayName

            $channel = Get-VETChannel -Team $team | Where-Object { $_.DisplayName -match $channelName } | Select-Object -First 1
            if (-not $channel) { throw "Channel matching '$channelName' not found in team '$($team.DisplayName)'." }
            $result['channel_resolved'] = $channel.DisplayName

            $rootFiles = @(Get-VETFile -Channel $channel)
            $nav = Resolve-VETPath -ChannelRef $channel -RootFiles $rootFiles -FolderPath $Path
            $result['current_path'] = $nav.CurrentPath
            $result['items'] = @($nav.Files | Select-Object -First $Count | ForEach-Object {
                @{
                    Name       = $_.Name
                    IsFolder   = $_.IsFolder
                    Size       = $_.Size
                    Modified   = if ($_.Modified) { $_.Modified.ToString('yyyy-MM-dd HH:mm:ss') } else { $null }
                    ModifiedBy = $_.ModifiedBy
                }
            })

            Stop-VBOTeamsItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOTeamsItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    'search-teams-files' {
        if (-not $Filter) { throw "The -Filter parameter is required for search-teams-files. Provide a search query (e.g. 'filename: report')." }

        $org = Resolve-VBOOrganization

        $result = @{ query = $Filter; team_filter = $User }

        try {
            $session = Start-VBOTeamsItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $vetOrg = Get-VETOrganization -Session $session

            if ($User) {
                $team = Get-VETTeam -Organization $vetOrg | Where-Object { $_.DisplayName -match $User } | Select-Object -First 1
                if (-not $team) { throw "Team matching '$User' not found." }
                $result['team_resolved'] = $team.DisplayName
                $files = Get-VETFile -Team $team -Query $Filter
            } else {
                $files = Get-VETFile -Organization $vetOrg -Query $Filter
            }

            $result['matches'] = @($files | Select-Object -First $Count | ForEach-Object {
                @{
                    Name       = $_.Name
                    IsFolder   = $_.IsFolder
                    Size       = $_.Size
                    Modified   = if ($_.Modified) { $_.Modified.ToString('yyyy-MM-dd HH:mm:ss') } else { $null }
                    ModifiedBy = $_.ModifiedBy
                }
            })
            $result['match_count'] = ($files | Measure-Object).Count

            Stop-VBOTeamsItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOTeamsItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    'restore-teams-file' {
        if (-not $User) { throw "The -User parameter is required for restore-teams-file. Provide a team name." }
        if (-not $Job)  { throw "The -Job parameter is required for restore-teams-file. Provide a file name pattern to match." }

        $org = Resolve-VBOOrganization
        $channelName = if ($Filter) { $Filter } else { 'General' }
        $restoreDir = $RestoreDir

        $result = @{ team = $User; channel = $channelName; path = if ($Path) { $Path } else { '/' }; file_pattern = $Job }

        try {
            $session = Start-VBOTeamsItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $vetOrg = Get-VETOrganization -Session $session
            $team = Get-VETTeam -Organization $vetOrg | Where-Object { $_.DisplayName -match $User } | Select-Object -First 1
            if (-not $team) { throw "Team matching '$User' not found." }
            $result['team_resolved'] = $team.DisplayName

            $channel = Get-VETChannel -Team $team | Where-Object { $_.DisplayName -match $channelName } | Select-Object -First 1
            if (-not $channel) { throw "Channel matching '$channelName' not found in team '$($team.DisplayName)'." }
            $result['channel_resolved'] = $channel.DisplayName

            $rootFiles = @(Get-VETFile -Channel $channel)
            $nav = Resolve-VETPath -ChannelRef $channel -RootFiles $rootFiles -FolderPath $Path
            $matchedFiles = @($nav.Files | Where-Object { -not $_.IsFolder -and $_.Name -match $Job } | Select-Object -First $Count)
            if ($matchedFiles.Count -eq 0) { throw "No file matching '$Job' found at path '$($nav.CurrentPath)'. Available files: $(($nav.Files | Where-Object { -not $_.IsFolder } | ForEach-Object { $_.Name }) -join ', ')" }

            if (-not (Test-Path $restoreDir)) { New-Item -ItemType Directory -Path $restoreDir -Force | Out-Null }

            $restoredItems = @()
            foreach ($targetFile in $matchedFiles) {
                Save-VETItem -File $targetFile -Path $restoreDir -Force
                $baseName = [System.IO.Path]::GetFileNameWithoutExtension($targetFile.Name)
                $savedFile = Get-ChildItem $restoreDir -Filter "$baseName*" -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1
                $restoredPath = if ($savedFile) { $savedFile.FullName } else { Join-Path $restoreDir $targetFile.Name }
                $restoredItems += @{
                    FileName  = if ($savedFile) { $savedFile.Name } else { $targetFile.Name }
                    LocalPath = $restoredPath
                    Size      = if ($savedFile) { $savedFile.Length } else { $targetFile.Size }
                    Exists    = (Test-Path $restoredPath)
                }
            }

            $result['restored'] = $restoredItems
            $result['total_files_restored'] = $restoredItems.Count

            Stop-VBOTeamsItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOTeamsItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    'restore-onedrive-file' {
        if (-not $User) { throw "The -User parameter is required for restore-onedrive-file. Provide a user email or display name." }
        if (-not $Job)  { throw "The -Job parameter is required for restore-onedrive-file. Provide a file name pattern to match." }

        $org = Resolve-VBOOrganization
        $restoreDir = $RestoreDir

        $result = @{ user = $User; path = if ($Path) { $Path } else { '/' }; file_pattern = $Job }

        try {
            $session = Start-VEODRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $veodOrg = Get-VEODOrganization -Session $session
            $veodUser = Get-VEODUser -Session $session -Organization $veodOrg | Where-Object {
                $_.Name -match $User
            } | Select-Object -First 1
            if (-not $veodUser) { throw "OneDrive user matching '$User' not found." }
            $result['user_resolved'] = $veodUser.Name

            $allDocs = @(Get-VEODDocument -User $veodUser -Recurse)

            $pathPrefix = if ($Path -and $Path -ne '/') { $Path.Trim('/') } else { $null }
            $matchedFiles = @($allDocs | Where-Object {
                $_.Name -match $Job -and
                (-not $pathPrefix -or ($_.Url -like "$pathPrefix/*" -and $_.Url.Split('/').Count -eq ($pathPrefix.Split('/').Count + 1)))
            } | Select-Object -First $Count)

            if ($matchedFiles.Count -eq 0) {
                $available = @($allDocs | Where-Object {
                    -not $pathPrefix -or $_.Url -like "$pathPrefix/*"
                } | Select-Object -First 20 | ForEach-Object { $_.Name })
                throw "No file matching '$Job' found at path '$(if ($pathPrefix) { $pathPrefix } else { '/' })'. Available (first 20): $($available -join ', ')"
            }

            if (-not (Test-Path $restoreDir)) { New-Item -ItemType Directory -Path $restoreDir -Force | Out-Null }

            $restoredItems = @()
            foreach ($doc in $matchedFiles) {
                Save-VEODDocument -Document $doc -Path $restoreDir
                $baseName = [System.IO.Path]::GetFileNameWithoutExtension($doc.Name)
                $savedFile = Get-ChildItem $restoreDir -Filter "$baseName*" -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1
                $restoredPath = if ($savedFile) { $savedFile.FullName } else { Join-Path $restoreDir $doc.Name }
                $restoredItems += @{
                    FileName  = if ($savedFile) { $savedFile.Name } else { $doc.Name }
                    LocalPath = $restoredPath
                    Size      = if ($savedFile) { $savedFile.Length } else { 0 }
                    Exists    = (Test-Path $restoredPath)
                    SourceUrl = $doc.Url
                }
            }

            $result['restored'] = $restoredItems
            $result['total_files_restored'] = $restoredItems.Count

            Stop-VEODRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VEODRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }

    'restore-sharepoint-file' {
        if (-not $User) { throw "The -User parameter is required for restore-sharepoint-file. Provide a site name or URL." }
        if (-not $Job)  { throw "The -Job parameter is required for restore-sharepoint-file. Provide a file name pattern to match." }

        $org = Resolve-VBOOrganization
        $libraryName = if ($Filter) { $Filter } else { 'Shared Documents' }
        $restoreDir = $RestoreDir

        $result = @{ site = $User; library = $libraryName; path = if ($Path) { $Path } else { '/' }; file_pattern = $Job }

        try {
            $session = Start-VBOSharePointItemRestoreSession -Organization $org -LatestState
            $result['session_id'] = $session.Id.ToString()

            $vespOrg = Get-VESPOrganization -Session $session
            $site = Get-VESPSite -Organization $vespOrg | Where-Object {
                $_.Name -match $User -or $_.Url -match $User
            } | Select-Object -First 1
            if (-not $site) { throw "SharePoint site matching '$User' not found." }
            $result['site_resolved'] = if ($site.Name) { $site.Name } else { $site.Url }

            $lib = Get-VESPDocumentLibrary -Site $site | Where-Object { $_.Name -match $libraryName } | Select-Object -First 1
            if (-not $lib) { throw "Document library matching '$libraryName' not found." }
            $result['library_resolved'] = $lib.Name

            $rootDocs = @(Get-VESPDocument -DocumentLibrary $lib)

            if ($Path -and $Path -ne '/') {
                $segments = $Path.Trim('/').Split('/')
                $current = $null
                foreach ($seg in $segments) {
                    $candidates = if ($current) { @(Get-VESPDocument -DocumentLibrary $lib -ParentDocument $current) } else { $rootDocs }
                    $folder = $candidates | Where-Object { $_.IsFolder -and $_.Name -eq $seg } | Select-Object -First 1
                    if (-not $folder) { throw "Folder '$seg' not found. Available: $(($candidates | Where-Object { $_.IsFolder } | ForEach-Object { $_.Name }) -join ', ')" }
                    $current = $folder
                }
                $targetDocs = @(Get-VESPDocument -DocumentLibrary $lib -ParentDocument $current)
            } else {
                $targetDocs = $rootDocs
            }

            $matchedFiles = @($targetDocs | Where-Object { -not $_.IsFolder -and $_.Name -match $Job } | Select-Object -First $Count)
            if ($matchedFiles.Count -eq 0) { throw "No file matching '$Job' found. Available: $(($targetDocs | Where-Object { -not $_.IsFolder } | ForEach-Object { $_.Name }) -join ', ')" }

            if (-not (Test-Path $restoreDir)) { New-Item -ItemType Directory -Path $restoreDir -Force | Out-Null }

            $restoredItems = @()
            foreach ($doc in $matchedFiles) {
                Save-VESPItem -Document $doc -Path $restoreDir -Force
                $baseName = [System.IO.Path]::GetFileNameWithoutExtension($doc.Name)
                $savedFile = Get-ChildItem $restoreDir -Filter "$baseName*" -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1
                $restoredPath = if ($savedFile) { $savedFile.FullName } else { Join-Path $restoreDir $doc.Name }
                $restoredItems += @{
                    FileName  = if ($savedFile) { $savedFile.Name } else { $doc.Name }
                    LocalPath = $restoredPath
                    Size      = if ($savedFile) { $savedFile.Length } else { $doc.Size }
                    Exists    = (Test-Path $restoredPath)
                }
            }

            $result['restored'] = $restoredItems
            $result['total_files_restored'] = $restoredItems.Count

            Stop-VBOSharePointItemRestoreSession -Session $session
            $result['session_closed'] = $true
        } catch {
            $result['error'] = $_.Exception.Message
            try { if ($session) { Stop-VBOSharePointItemRestoreSession -Session $session } } catch {}
        }

        $result | ConvertTo-Json -Depth 5
    }
}
