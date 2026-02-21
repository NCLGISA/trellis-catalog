# Veeam M365 Bridge -- Deployment Reference

## Prerequisites

### Server Requirements

| Requirement | Details |
|-------------|---------|
| OS | Windows Server 2016+ (64-bit) |
| Veeam | Veeam Backup for Microsoft 365 v13+ installed and configured |
| PowerShell | PowerShell 5.1+ or PowerShell 7 (pwsh) |
| Module | `Veeam.Archiver.PowerShell` v6.0+ (ships with VBO v13) |
| Tendril | Tendril agent installed and running as SYSTEM |
| Disk | Restore operations write to `C:\Temp\veeam-restore` by default (configurable via `-RestoreDir`) |

### Veeam Configuration

Before deploying the bridge, ensure the following:

1. **VBO is configured with at least one organization** (M365 tenant connected)
2. **At least one backup job exists** and has completed at least one successful session
3. **The Veeam.Archiver.Service is running** on the target server
4. **PostgreSQL 15 is running** (`postgresql-x64-15` service)
5. **NATS Server is running** (`nats-server` service)

The bridge connects to the local VBO service via `Connect-VBOServer -Server localhost`
using Windows Integrated Authentication. No API keys are needed -- the Tendril agent
runs as SYSTEM and inherits local admin access to the VBO service.

## Azure AD App Registration Permissions

Veeam Backup for M365 uses an Azure AD application to access the Microsoft Graph API.
The app registration must have the following permissions granted as **Application** type
(not Delegated):

### Required Permissions

The VBO setup wizard configures most permissions automatically. However, some permissions
may need to be granted manually if Teams backup/restore encounters errors.

**Critical permission often missing**: `ChannelMember.Read.All`

Without this permission, VBO will fail to process private and shared Teams channels with:
```
Missing application permissions: ChannelMember.Read.All
```

### Granting ChannelMember.Read.All

Use the Microsoft Graph API to grant the permission. You need:
- The **Service Principal ID** of the Veeam app registration
- The **Microsoft Graph Service Principal ID** (resource)
- The **App Role ID** for `ChannelMember.Read.All`

```bash
# 1. Find the Veeam app's service principal
az ad sp list --display-name "Veeam" --query "[].{id:id, appId:appId, displayName:displayName}" -o table

# 2. Find the Microsoft Graph service principal
az ad sp list --filter "appId eq '00000003-0000-0000-c000-000000000000'" --query "[].id" -o tsv

# 3. List available Graph app roles to find ChannelMember.Read.All
az ad sp show --id 00000003-0000-0000-c000-000000000000 --query "appRoles[?value=='ChannelMember.Read.All'].{id:id, value:value}" -o table

# 4. Grant the permission
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/{veeam-sp-id}/appRoleAssignments" \
  --body '{
    "principalId": "{veeam-sp-id}",
    "resourceId": "{graph-sp-id}",
    "appRoleId": "{channelmember-role-id}"
  }'
```

After granting, allow up to 10 minutes for the permission to propagate before retesting.

### Verifying Permissions

```bash
az rest --method GET \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/{veeam-sp-id}/appRoleAssignments" \
  --query "value[].{permission:appRoleId, resource:resourceDisplayName}"
```

## Deployment

### Via Trellis CLI

```bash
# 1. Validate the bridge
trellis validate veeam-m365

# 2. Deploy to the VBO server's Tendril agent
trellis deploy veeam-m365 --target <agent-name>
```

The bridge files are pushed to the Tendril agent's skill directory
(`C:\Program Files\Tendril\skills\veeam-m365\`) via `file_push`.

### Manual Deployment

If deploying without the Trellis CLI:

1. Copy the bridge directory to the Tendril skills path on the VBO server:
   ```
   C:\Program Files\Tendril\skills\veeam-m365\
   ```
2. Ensure the directory structure is:
   ```
   veeam-m365\
     bridge.yaml
     tools\
       veeam_m365_admin.ps1
     skills\
       veeam-m365\
         SKILL.md
   ```
3. Restart the Tendril service: `Restart-Service -Name "Tendril" -Force`
4. Verify the skill appears: call `list_tendril_skills` on the agent

## Post-Deployment Validation

Run these actions in order to confirm the bridge is working:

```powershell
# 1. Check VBO service health
.\veeam_m365_admin.ps1 -Action status

# 2. Verify organization connectivity
.\veeam_m365_admin.ps1 -Action org-stats

# 3. Confirm backup jobs are visible
.\veeam_m365_admin.ps1 -Action jobs

# 4. Test a read-only restore session (Teams)
.\veeam_m365_admin.ps1 -Action explore-teams -User "<any-team-name>"

# 5. Test license visibility
.\veeam_m365_admin.ps1 -Action license
```

## Known Quirks

These behaviors were discovered during production testing and are handled by the script:

| Quirk | Detail |
|-------|--------|
| `Get-VETTeam` requires intermediate step | Cannot pass `-Session` directly; must use `Get-VETOrganization -Session` first |
| `Get-VETFile -ParentFile` requires `-Channel` | Subfolder navigation fails without passing the channel reference |
| `Save-VETItem` appends version suffixes | Restored files may have `(ver.2.0)` in the filename |
| `Get-VEODUser` requires both `-Session` and `-Organization` | Unlike other explorer cmdlets |
| `VEODUser` uses `.Name` property | Not `.DisplayName` or `.UserName` like other Veeam objects |
| `VEODDocument` lacks `.IsFolder` property | Use `Get-VEODDocument -Recurse` with URL-based path filtering |
| `Save-VEODDocument` does not support `-Force` | Unlike `Save-VETItem` and `Save-VESPItem` |
| `VESPSite` uses `.Name` and `.Url` | Not `.Title` or `.URL` (case-sensitive) |
| Search across all teams can timeout | Large tenants with many teams may hit gateway timeouts when using org-wide `Get-VETFile -Query` |
