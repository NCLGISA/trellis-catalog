---
name: veeam-m365
description: >
  Manage Veeam Backup for Microsoft 365. Backup job management, granular
  Exchange/SharePoint/Teams/OneDrive restore, organization inventory, license monitoring,
  session diagnostics, and storage reporting for any M365 tenant.
compatibility:
  - platform: windows
    arch: amd64
    min_version: "2026.02.21"
metadata:
  author: tendril-project
  version: "3.0.0"
  tendril-bridge: "false"
  skill_scope: "local"
  tags:
    - veeam
    - m365
    - backup
    - exchange
    - sharepoint
    - onedrive
    - teams
    - restore
    - microsoft-365
---

# Veeam Backup for Microsoft 365

Manage Veeam Backup for M365 backup jobs, granular item-level restore, organization
inventory, and health monitoring on any Windows server running VBO v13+.

## Host

Agent: Deploy to any Windows Server running Veeam Backup for Microsoft 365 v13+
Application: Veeam Backup for Microsoft 365 v13.x (Veeam Software Group GmbH)
PowerShell Module: `Veeam.Archiver.PowerShell` v6.0 (220 cmdlets)
Database: PostgreSQL 15 (`VeeamBackup365`)
Services:
  - `Veeam.Archiver.Service` -- Veeam Backup for Microsoft 365 Service
  - `Veeam.Archiver.Proxy` -- Veeam Backup for Microsoft 365 Proxy Service
  - `nats-server` -- NATS messaging (inter-process, port 4222)
  - `postgresql-x64-15` -- PostgreSQL Server 15 (port 5432)
Install: `C:\Program Files\Veeam\Backup365`

## Architecture

Veeam Backup for M365 connects to the Microsoft 365 tenant via the Microsoft Graph API
using an Azure AD application with delegated permissions. Backup data flows from M365
through the local proxy service to object storage (Azure Blob, S3, or local).

```
  M365 Tenant (contoso.onmicrosoft.com)
       |
       | (Graph API -- Exchange, SharePoint, OneDrive, Teams)
       v
  Veeam.Archiver.Service (your-vbo-server)
       |
       +-- Veeam.Archiver.Proxy (configurable threads, local)
       |       |
       |       +-- Object Storage (Azure Blob / S3 / local)
       |
       +-- PostgreSQL 15 (VeeamBackup365 database)
       |
       +-- NATS Server (inter-process messaging)
       |
       +-- Veeam Explorers (Exchange, SharePoint, OneDrive, Teams)
```

## Configuration Template

After deploying the bridge, run `status` and `org-stats` to populate these values
for your environment.

| Setting | Value |
|---------|-------|
| Organization | `<your-tenant>.onmicrosoft.com` |
| Backup Scope | Mailbox + Archive Mailbox + OneDrive (org-level) |
| Job Name | `<your-job-name>` |
| Schedule | `<your-schedule>` |
| Repository | `<your-repo-name>` (Azure Blob / S3 / local) |
| Retention | `<your-retention>` days, snapshot-based |
| Proxy | `<your-vbo-server>` (local), configurable threads |
| License | Subscription, `<total>` seats (`<used>` used), expires `<date>` |

### Tenant Scale

Use `org-stats` to discover your tenant's object counts:

| Object | Count |
|--------|-------|
| Users | -- |
| Groups | -- |
| SharePoint Sites | -- |
| Teams | -- |

## Quick Start

```powershell
# Server health overview (version, license, services, proxy, jobs)
.\veeam_m365_admin.ps1 -Action status

# List all backup jobs with last run status
.\veeam_m365_admin.ps1 -Action jobs

# Recent sessions for a backup job (last 10)
.\veeam_m365_admin.ps1 -Action sessions -Count 10

# Detailed session log (warnings/errors) for the most recent session
.\veeam_m365_admin.ps1 -Action session-log

# Session log for a specific session ID
.\veeam_m365_admin.ps1 -Action session-log -SessionId "abc-123-def"

# License details and overprovisioning check
.\veeam_m365_admin.ps1 -Action license

# Repository info and retention policies
.\veeam_m365_admin.ps1 -Action repos

# Organization summary (user, group, site, team counts)
.\veeam_m365_admin.ps1 -Action org-stats

# Search for users by name or email
.\veeam_m365_admin.ps1 -Action users -Filter "smith"

# List groups matching a pattern
.\veeam_m365_admin.ps1 -Action groups -Filter "IT"

# List SharePoint sites
.\veeam_m365_admin.ps1 -Action sites

# List Teams
.\veeam_m365_admin.ps1 -Action teams -Filter "helpdesk"

# Protection and storage reports
.\veeam_m365_admin.ps1 -Action protection-report
.\veeam_m365_admin.ps1 -Action storage-report

# Start or stop a backup job
.\veeam_m365_admin.ps1 -Action start-job -Job "Daily Backup"
.\veeam_m365_admin.ps1 -Action stop-job -Job "Daily Backup"

# Enable or disable a job
.\veeam_m365_admin.ps1 -Action enable-job -Job "Daily Backup"
.\veeam_m365_admin.ps1 -Action disable-job -Job "Daily Backup"

# List restore points for a specific user
.\veeam_m365_admin.ps1 -Action restore-points -User "user@example.com"

# Explore a user's Exchange mailbox from backup
.\veeam_m365_admin.ps1 -Action explore-exchange -User "user@example.com"

# Explore SharePoint sites in backup
.\veeam_m365_admin.ps1 -Action explore-sharepoint -User "IT Department"

# Explore Teams in backup
.\veeam_m365_admin.ps1 -Action explore-teams -User "Helpdesk"

# Browse files in a Teams channel (with folder navigation)
.\veeam_m365_admin.ps1 -Action browse-channel-files -User "Engineering" -Filter "General" -Path "Projects/2026"

# Search for files across all teams or within a specific team
.\veeam_m365_admin.ps1 -Action search-teams-files -Filter "filename: report"
.\veeam_m365_admin.ps1 -Action search-teams-files -User "Engineering" -Filter "filename: report"

# Restore a file from Teams backup (default: C:\Temp\veeam-restore)
.\veeam_m365_admin.ps1 -Action restore-teams-file -User "Engineering" -Filter "General" -Path "Projects/2026/RFP" -Job "report"

# Restore multiple files with wildcard pattern (up to 10)
.\veeam_m365_admin.ps1 -Action restore-teams-file -User "Engineering" -Filter "General" -Path "Projects/2026" -Job ".*\.pdf" -Count 10

# Restore file(s) from OneDrive backup (pattern matches multiple files, limited by -Count)
.\veeam_m365_admin.ps1 -Action restore-onedrive-file -User "user@example.com" -Path "Documents/Reports" -Job "quarterly" -Count 5

# Restore file(s) from SharePoint backup
.\veeam_m365_admin.ps1 -Action restore-sharepoint-file -User "IT Department" -Filter "Shared Documents" -Path "Policies" -Job ".*\.pdf" -Count 10

# Custom restore directory
.\veeam_m365_admin.ps1 -Action restore-teams-file -User "Engineering" -Filter "General" -Job "report" -RestoreDir "D:\Restores"
```

## Action Reference

### Health & Status (read-only)

| Action | Parameters | Description |
|--------|-----------|-------------|
| `status` | (none) | Server version, license summary, service states, proxy health, job overview |
| `jobs` | (none) | All backup and copy jobs with last run, status, duration |
| `sessions` | `-Job`, `-Count` | Recent session history for a job (default: last 25) |
| `session-log` | `-SessionId`, `-Job` | Warnings/errors from a session (default: most recent) |
| `license` | (none) | License type, seats, expiry, overprovisioning check |
| `repos` | (none) | Repository name, path, retention type/period |
| `protection-report` | (none) | Mailbox/user protection coverage report |
| `storage-report` | (none) | Storage consumption by repository |

### Organization / Inventory (read-only)

| Action | Parameters | Description |
|--------|-----------|-------------|
| `org-stats` | (none) | User, group, site, team counts for the organization |
| `users` | `-Filter`, `-Count` | List/search organization users by name or email |
| `groups` | `-Filter`, `-Count` | List/search organization groups |
| `sites` | `-Filter`, `-Count` | List SharePoint sites (filter by title or URL) |
| `teams` | `-Filter`, `-Count` | List Teams (filter by display name) |

### Job Management (operational)

| Action | Parameters | Description |
|--------|-----------|-------------|
| `start-job` | `-Job` | Start a backup job by name |
| `stop-job` | `-Job` | Stop a running backup job |
| `enable-job` | `-Job` | Enable a disabled backup job |
| `disable-job` | `-Job` | Disable a backup job |

### Restore Operations (operational)

| Action | Parameters | Description |
|--------|-----------|-------------|
| `restore-points` | `-User`, `-Count` | List restore points for a user/mailbox |
| `explore-exchange` | `-User` | Open Exchange restore session, browse mailbox folders |
| `explore-sharepoint` | `-User` | Open SharePoint restore session, browse sites/libraries |
| `explore-teams` | `-User` | Open Teams restore session, browse teams/channels |

### File-Level Restore (operational)

| Action | Parameters | Description |
|--------|-----------|-------------|
| `browse-channel-files` | `-User` (team), `-Filter` (channel), `-Path` | Browse files/folders in a Teams channel with path navigation |
| `search-teams-files` | `-User` (team, optional), `-Filter` (query) | Search for files across all teams or within a specific team |
| `restore-teams-file` | `-User` (team), `-Filter` (channel), `-Path`, `-Job` (pattern), `-Count`, `-RestoreDir` | Restore files from Teams backup (multi-file via wildcard `-Job`) |
| `restore-onedrive-file` | `-User` (email/name), `-Path`, `-Job` (pattern), `-Count`, `-RestoreDir` | Restore files from OneDrive backup (multi-file via wildcard `-Job`) |
| `restore-sharepoint-file` | `-User` (site), `-Filter` (library), `-Path`, `-Job` (pattern), `-Count`, `-RestoreDir` | Restore files from SharePoint backup (multi-file via wildcard `-Job`) |

## Veeam PowerShell Modules

| Module | Version | Purpose |
|--------|---------|---------|
| `Veeam.Archiver.PowerShell` | 6.0 | VBO main module (220 cmdlets) -- jobs, orgs, repos, sessions |
| `Veeam.Exchange.PowerShell` | 2.0 | Exchange Explorer (VEX* cmdlets) -- mailbox browse/restore |
| `Veeam.SharePoint.PowerShell` | 2.0 | SharePoint/OneDrive Explorer (VESP*/VEOD* cmdlets) |
| `Veeam.Teams.PowerShell` | 2.0 | Teams Explorer (VET* cmdlets) -- team/channel browse/restore |
| `Veeam.ExchangeOnlineManagement` | 1.0.2 | Exchange Online management (internal use by VBO) |

## VBO Cmdlet Categories (220 total)

### Core Operations (VBO*)
- **Jobs**: Get/Add/Set/Remove-VBOJob, Start/Stop/Enable/Disable-VBOJob
- **Copy Jobs**: Get/Add/Set/Remove-VBOCopyJob, Start/Stop/Enable/Disable-VBOCopyJob
- **Sessions**: Get-VBOJobSession, Get-VBORestoreSession, Get-VBODataManagementSession
- **Organizations**: Get/Add/Set/Remove-VBOOrganization, Start-VBOOrganizationSynchronization
- **Org Inventory**: Get-VBOOrganizationUser/Group/Site/Team/GroupMember
- **Repositories**: Get/Add/Set/Remove-VBORepository, Test-VBORepository
- **Object Storage**: Get/Set-VBOObjectStorageRepository (Azure Blob, S3, S3-Compatible)
- **Proxies**: Get/Add/Set/Remove-VBOProxy, Get/Set-VBOProxyPool, Sync/Update-VBOProxy
- **Restore Points**: Get-VBORestorePoint
- **Backup Items**: Get/Add/Remove-VBOBackupItem, Get/Add/Remove-VBOExcludedBackupItem
- **License**: Get/Install/Update/Uninstall-VBOLicense, Get-VBOLicensedUser
- **Reports**: Get-VBOLicenseOverviewReport, Get-VBOMailboxProtectionReport, Get-VBOUserProtectionReport, Get-VBOStorageConsumptionReport
- **Settings**: Get/Set-VBOEmailSettings, Get/Set-VBOSecuritySettings, Get/Set-VBORestAPISettings
- **Data Operations**: Get/Move/Remove-VBOEntityData, Start/Set/Get-VBODataRetrieval
- **Azure/AWS Storage**: Get/Add/Set/Remove-VBOAzureBlobAccount, Get/Add/Set-VBOAmazonS3Account
- **RBAC**: Get/Add/Set/Remove-VBORbacRole, New-VBORbacOperator/RbacRoleItem
- **Server**: Get/Set-VBOServer, Get-VBOServerComponents, Get-VBOVersion, Connect/Disconnect-VBOServer
- **Encryption**: Get/Add/Remove-VBOEncryptionKey

### Exchange Explorer (VEX*)
- Get-VEXDatabase, Get-VEXMailbox, Get-VEXFolder, Get-VEXItem
- Export-VEXItem, Restore-VEXItem, Send-VEXItem
- Start/Stop-VBOExchangeItemRestoreSession

### SharePoint Explorer (VESP*)
- Start-VBOSharePointItemRestoreSession -> Get-VESPOrganization -> Get-VESPSite -> Get-VESPDocumentLibrary -> Get-VESPDocument
- Folder navigation: `Get-VESPDocument -DocumentLibrary $lib -ParentDocument $parentFolder`
- Save to disk: `Save-VESPItem -Document $doc -Path $dir -Force`
- Get-VESPList, Get-VESPItem/ItemVersion/ItemAttachment, Export/Restore/Send-VESPItem

### OneDrive Explorer (VEOD*)
- Start-VEODRestoreSession -> Get-VEODOrganization -> Get-VEODUser -> Get-VEODDocument
- Folder navigation: `Get-VEODDocument -User $user -Recurse` with URL-based path filtering
- Save to disk: `Save-VEODDocument -Document $doc -Path $dir`
- Get-VEODDocumentVersion, Restore-VEODDocument (restore to original), Send-VEODDocument
- Start/Stop-VEODRestoreSession

**Required cmdlet chain** (Get-VESPSite does NOT accept `-Session` directly):
1. `$session = Start-VBOSharePointItemRestoreSession -Organization $org -LatestState`
2. `$vespOrg = Get-VESPOrganization -Session $session`
3. `$sites = Get-VESPSite -Organization $vespOrg`

**Required VEOD cmdlet chain** (Get-VEODUser requires `-Session` AND `-Organization`):
1. `$session = Start-VEODRestoreSession -Organization $org -LatestState`
2. `$veodOrg = Get-VEODOrganization -Session $session`
3. `$user = Get-VEODUser -Session $session -Organization $veodOrg`
4. `$docs = Get-VEODDocument -User $user -Recurse`

### Teams Explorer (VET*)
- Get-VETOrganization, Get-VETTeam, Get-VETTeamMember, Get-VETChannel
- Get-VETPost, Get-VETFile, Get-VETOtherTab
- Export-VETPost, Restore/Save/Send-VETItem
- Start/Stop-VBOTeamsItemRestoreSession

**Required cmdlet chain** (Get-VETTeam does NOT accept `-Session` directly):
1. `$session = Start-VBOTeamsItemRestoreSession -Organization $org -LatestState`
2. `$vetOrg = Get-VETOrganization -Session $session`
3. `$teams = Get-VETTeam -Organization $vetOrg`
4. `$channels = Get-VETChannel -Team $team`
5. `$files = Get-VETFile -Channel $channel` (or `-ParentFile` for subfolder navigation)

**Critical**: `Get-VETFile -ParentFile $folder` also requires `-Channel $channel` to be passed.

## Listening Ports

| Port | Protocol | Process |
|------|----------|---------|
| 4222 | NATS | nats-server (Veeam inter-process messaging) |
| 5432 | PostgreSQL | postgres (VeeamBackup365 database) |
| 9191 | HTTPS | Veeam.Archiver.Service (management console) |

## Installed Veeam Software

| Software | Version |
|----------|---------|
| Veeam Backup for Microsoft 365 | v13.x |
| Veeam Explorer for Microsoft Exchange | v13.x |
| Veeam Explorer for Microsoft SharePoint | v13.x |
| Veeam Explorer for Microsoft Teams | v13.x |

## Common Workflows

### Investigate backup warnings
```powershell
# 1. Check recent sessions
.\veeam_m365_admin.ps1 -Action sessions -Count 5

# 2. Get the session log for the most recent session
.\veeam_m365_admin.ps1 -Action session-log

# 3. Or for a specific session
.\veeam_m365_admin.ps1 -Action session-log -SessionId "<id-from-step-1>"
```

### Check if a specific user is protected
```powershell
.\veeam_m365_admin.ps1 -Action users -Filter "john.doe"
```

### Restore a single email or document
```powershell
# 1. Browse the user's Exchange mailbox from backup
.\veeam_m365_admin.ps1 -Action explore-exchange -User "user@example.com"

# 2. For SharePoint documents
.\veeam_m365_admin.ps1 -Action explore-sharepoint -User "IT Department"

# 3. For Teams data
.\veeam_m365_admin.ps1 -Action explore-teams -User "Helpdesk"
```

### Restore files from Teams backup
```powershell
# 1. Browse channel files to find the target folder
.\veeam_m365_admin.ps1 -Action browse-channel-files -User "Engineering" -Filter "General" -Path "Projects/2026"

# 2. Drill deeper into subfolders as needed
.\veeam_m365_admin.ps1 -Action browse-channel-files -User "Engineering" -Filter "General" -Path "Projects/2026/Proposals/Responses"

# 3. Restore matching file(s) to the restore directory
.\veeam_m365_admin.ps1 -Action restore-teams-file -User "Engineering" -Filter "General" -Path "Projects/2026/Proposals/Responses" -Job "report"

# 4. Restore multiple files with wildcard pattern (up to 10)
.\veeam_m365_admin.ps1 -Action restore-teams-file -User "Engineering" -Filter "General" -Path "Projects/2026" -Job ".*\.pdf" -Count 10

# 5. Pull the restored file(s) locally via Tendril file_pull
#    (use the LocalPath values from the restored[] array in JSON output)
```

### Restore files from OneDrive backup
```powershell
# 1. Restore a user's file by email and path
.\veeam_m365_admin.ps1 -Action restore-onedrive-file -User "user@example.com" -Path "Documents/Reports" -Job "quarterly"

# 2. Restore all PDFs from a OneDrive folder (up to 20)
.\veeam_m365_admin.ps1 -Action restore-onedrive-file -User "jane.smith" -Path "Documents" -Job ".*\.pdf" -Count 20

# 3. Pull the restored file(s) locally via Tendril file_pull
```

### Restore files from SharePoint backup
```powershell
# 1. Restore files from a SharePoint site's document library
.\veeam_m365_admin.ps1 -Action restore-sharepoint-file -User "IT Department" -Filter "Shared Documents" -Path "Policies" -Job "policy"

# 2. Restore multiple files with regex pattern
.\veeam_m365_admin.ps1 -Action restore-sharepoint-file -User "HR" -Filter "Documents" -Path "Employee Handbook" -Job ".*\.docx" -Count 10

# 3. Pull the restored file(s) locally via Tendril file_pull
```

### License capacity check
```powershell
.\veeam_m365_admin.ps1 -Action license
# Check the overprovisioned flag and overage count
```

## Troubleshooting

- **Session shows Warning status**: Usually caused by M365 Graph API throttling (HTTP 429),
  individual mailbox access failures (disabled accounts, litigation hold), or OneDrive sync
  failures for specific users. Use `session-log` to identify the specific warnings.
- **"Missing application permissions: ChannelMember.Read.All"**: The Veeam Azure AD app
  registration requires `ChannelMember.Read.All` (Application type) to process private and
  shared Teams channels. Grant via Microsoft Graph API:
  `az rest --method POST --uri "https://graph.microsoft.com/v1.0/servicePrincipals/{sp-id}/appRoleAssignments" --body '{"principalId":"{sp-id}","resourceId":"{graph-sp-id}","appRoleId":"{role-id}"}'`.
  See `references/README.md` for the full permission grant procedure.
- **License overprovisioned**: Veeam continues to back up when over-licensed but flags
  compliance warnings. Review with the `license` action and plan seat reconciliation.
- **Module import fails**: The `Veeam.Archiver.PowerShell` module requires PowerShell 5.1+.
  PowerShell 7 (pwsh) is also compatible.
- **Restore session timeout**: Exchange/SharePoint/Teams restore sessions may take 30-60
  seconds to initialize depending on repository size. Use a longer Tendril timeout (120s+).
- **File browsing is slow for large channels**: Teams file browsing reads from object storage,
  which can be slow for channels with many files. Use `-Count` to limit results and
  navigate with `-Path` to drill into specific folders instead of listing everything.
- **VETFile property names**: Use `Name`, `Size`, `Modified`, `ModifiedBy`, `IsFolder`, and
  `Version`. Properties like `DisplayName` or `SizeBytes` do not exist on VETFile objects.
- **VEODUser property names**: Use `.Name` (not `.DisplayName` or `.UserName`).
  `VEODDocument` objects lack an `IsFolder` property; use `Get-VEODDocument -Recurse`
  with URL-based path filtering instead of `-ParentDocument` traversal.
- **Save-VETItem appends version suffixes**: Restored files may have `(ver.2.0)` appended
  to the filename. The script handles this by matching on the base filename.
- **Save-VEODDocument does not support -Force**: Unlike `Save-VETItem` and `Save-VESPItem`,
  the OneDrive save cmdlet does not accept the `-Force` flag.
- **PostgreSQL connection errors**: Check `postgresql-x64-15` service status. The VBO service
  connects via localhost:5432.
- **Proxy offline**: Check `Veeam.Archiver.Proxy` service. Restart with:
  `Restart-Service 'Veeam.Archiver.Proxy'`
- **NATS not running**: The `nats-server` service must be running for VBO inter-process
  communication. Restart with: `Restart-Service 'nats-server'`
- **If the skill does not appear in `list_tendril_skills`**: Restart the Tendril service:
  `Restart-Service -Name "Tendril" -Force`

## Related Software

| Software | Purpose |
|----------|---------|
| PostgreSQL 15 | VBO database backend |
| NATS Server | VBO inter-process messaging |
