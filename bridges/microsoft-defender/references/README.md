# Microsoft Defender Bridge -- References

Organization-specific context and setup scripts for the Tendril Microsoft Defender bridge.

## Files

| File | Purpose |
|------|---------|
| `setup_defender_bridge.sh` | Automated Entra app registration, API permissions, ARM RBAC, and workspace discovery |

## Institutional Knowledge

Add tenant-specific files here (e.g., workspace IDs, Sentinel rule inventory, custom hunting queries).

These files are accessible via Tendril file transfer:
```bash
transfer_file(source="bridge-microsoft-defender", source_path="/opt/bridge/data/references/<file>", destination="local")
```
