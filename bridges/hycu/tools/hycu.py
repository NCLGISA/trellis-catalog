#!/usr/bin/env python3
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""HYCU Backup & Recovery — Unified CLI.

Reads HYCU_SERVER, HYCU_API_KEY, HYCU_PORT from environment
(auto-injected by Tendril credential vault).

Usage:
    python3 hycu.py <module> <action> [options]

Modules: admin, vms, jobs, policies, targets, events, apps, shares,
         volumegroups, users, archives, windows, reports, credentials,
         validation, webhooks, networks, mounts
"""

import argparse
import json
import sys

from hycu_client import HYCUClient


def die(msg):
    print(json.dumps({"success": False, "error": msg}))
    sys.exit(1)


def out(data, success=True):
    if isinstance(data, dict):
        data["success"] = success
    elif isinstance(data, list):
        data = {"success": success, "count": len(data), "items": data}
    else:
        data = {"success": success, "result": data}
    print(json.dumps(data, indent=2, default=str))


def paginated_list(result):
    """Normalize HYCU paginated response."""
    if isinstance(result, dict) and "entities" in result:
        entities = result["entities"]
        metadata = result.get("metadata", {})
        return {"count": len(entities), "total": metadata.get("totalEntityCount", len(entities)), "items": entities}
    return result


# -----------------------------------------------------------------------
# Module handlers
# -----------------------------------------------------------------------

def run_admin(args, client):
    a = args.action
    if a == "status":
        ctrl = client.get_controller()
        state = client.get_controller_state()
        sw = client.get_software_version()
        lic = client.get_license()
        tz = client.get_timezone()
        sched = client.get_scheduler_state()
        out({"controller": ctrl, "state": state, "software": sw, "license": lic, "timezone": tz, "scheduler": sched})
    elif a == "version":
        out(client.get_software_version())
    elif a == "license":
        out(client.get_license())
    elif a == "clusters":
        out(paginated_list(client.get_clusters()))
    elif a == "encryption":
        out(client.get_encryption_keys())
    elif a == "worker":
        out(client.get_worker())
    elif a == "physical-machines":
        out(paginated_list(client.get_physical_machines()))
    elif a == "logging":
        out(client.get_logging_config())
    elif a == "purge":
        out(client.get_purge_config())
    elif a == "suspend-scheduler":
        out(client.suspend_scheduler())
    elif a == "start-scheduler":
        out(client.start_scheduler())
    else:
        die(f"Unknown admin action: {a}")


def run_vms(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_vms(page_size=getattr(args, "limit", None))))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_vm(args.id))
    elif a == "backups":
        if args.id:
            out(paginated_list(client.list_vm_backups(args.id)))
        else:
            out(paginated_list(client.list_all_vm_backups()))
    elif a == "snapshots":
        if args.id:
            out(paginated_list(client.list_vm_snapshots(args.id)))
        else:
            out(paginated_list(client.list_all_vm_snapshots()))
    elif a == "disks":
        if not args.id:
            die("--id required")
        out(client.get_vm_disks(args.id))
    elif a == "backup":
        if not args.id:
            die("--id required (VM UUID)")
        out(client.run_vm_backup(args.id))
    elif a == "restore-locations":
        if not args.id:
            die("--id required")
        out(client.get_vm_restore_locations(args.id))
    elif a == "backup-metadata":
        if not args.backup_id:
            die("--backup-id required")
        out(client.get_backup_metadata(args.backup_id))
    elif a == "mount-backup":
        if not args.id or not args.backup_id:
            die("--id and --backup-id required")
        out(client.mount_vm_backup(args.id, args.backup_id))
    elif a == "unmount-backup":
        if not args.id or not args.backup_id:
            die("--id and --backup-id required")
        out(client.unmount_vm_backup(args.id, args.backup_id))
    else:
        die(f"Unknown vms action: {a}")


def run_jobs(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_jobs(page_size=getattr(args, "limit", None))))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_job(args.id))
    elif a == "report":
        if not args.id:
            die("--id required")
        out(client.get_job_report(args.id))
    elif a == "kill":
        if not args.id:
            die("--id required")
        out(client.kill_job(args.id))
    elif a == "rerun":
        if not args.id:
            die("--id required")
        out(client.rerun_job(args.id))
    else:
        die(f"Unknown jobs action: {a}")


def run_policies(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_policies()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_policy(args.id))
    elif a == "backupable-count":
        if not args.id:
            die("--id required")
        out(client.get_policy_backupable_count(args.id))
    elif a == "retention-limit":
        out(client.get_retention_limit())
    else:
        die(f"Unknown policies action: {a}")


def run_targets(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_targets()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_target(args.id))
    elif a == "test":
        if not args.id:
            die("--id required")
        out(client.test_target_update(args.id))
    elif a == "benchmark":
        if not args.id:
            die("--id required")
        out(client.benchmark_target(args.id))
    elif a == "activate":
        if not args.id:
            die("--id required")
        out(client.activate_target(args.id))
    elif a == "deactivate":
        if not args.id:
            die("--id required")
        out(client.deactivate_target(args.id))
    elif a == "sync-catalog":
        out(client.sync_target_catalog())
    else:
        die(f"Unknown targets action: {a}")


def run_events(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_events(page_size=getattr(args, "limit", None))))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_event(args.id))
    elif a == "categories":
        out(client.get_event_categories())
    else:
        die(f"Unknown events action: {a}")


def run_apps(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_applications()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_application(args.id))
    elif a == "backups":
        if not args.id:
            die("--id required")
        out(paginated_list(client.list_app_backups(args.id)))
    elif a == "config":
        if not args.id:
            die("--id required")
        out(client.get_app_config(args.id))
    elif a == "discover":
        out(client.run_app_discovery())
    elif a == "clusters":
        out(paginated_list(client.list_app_clusters()))
    else:
        die(f"Unknown apps action: {a}")


def run_shares(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_shares()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_share(args.id))
    elif a == "backups":
        if args.id:
            out(paginated_list(client.list_share_backups(args.id)))
        else:
            out(paginated_list(client.list_all_share_backups()))
    elif a == "browse":
        if not args.backup_id:
            die("--backup-id required")
        out(client.browse_share_backup(args.backup_id))
    else:
        die(f"Unknown shares action: {a}")


def run_volumegroups(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_volume_groups()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_volume_group(args.id))
    elif a == "backups":
        if args.id:
            out(paginated_list(client.list_vg_backups(args.id)))
        else:
            out(paginated_list(client.list_all_vg_backups()))
    else:
        die(f"Unknown volumegroups action: {a}")


def run_users(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_users(page_size=getattr(args, "limit", None))))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_user(args.id))
    elif a == "roles":
        out(client.get_user_roles())
    elif a == "groups":
        if args.id:
            out(client.get_user_groups(args.id))
        else:
            out(paginated_list(client.list_user_groups()))
    elif a == "api-keys":
        out(paginated_list(client.list_api_keys()))
    else:
        die(f"Unknown users action: {a}")


def run_archives(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_archives()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_archive(args.id))
    elif a == "policies":
        if not args.id:
            die("--id required")
        out(client.get_archive_policies(args.id))
    else:
        die(f"Unknown archives action: {a}")


def run_windows(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_backup_windows()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_backup_window(args.id))
    elif a == "policies":
        if not args.id:
            die("--id required")
        out(client.get_backup_window_policies(args.id))
    else:
        die(f"Unknown windows action: {a}")


def run_reports(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_reports()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_report(args.id))
    elif a == "generate":
        if not args.id:
            die("--id required")
        out(client.generate_report_version(args.id))
    elif a == "schedules":
        out(paginated_list(client.list_report_schedules()))
    else:
        die(f"Unknown reports action: {a}")


def run_credentials(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_credential_groups()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_credential_group(args.id) if hasattr(client, "get_credential_group") else {"error": "not available"})
    else:
        die(f"Unknown credentials action: {a}")


def run_validation(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_validation_policies()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_validation_policy(args.id))
    else:
        die(f"Unknown validation action: {a}")


def run_webhooks(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_webhooks()))
    elif a == "detail":
        if not args.id:
            die("--id required")
        out(client.get_webhook(args.id))
    elif a == "ping":
        if not args.name:
            die("--name required")
        out(client.ping_webhook(args.name))
    else:
        die(f"Unknown webhooks action: {a}")


def run_networks(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_networks()))
    elif a == "sites":
        out(paginated_list(client.list_network_sites()))
    else:
        die(f"Unknown networks action: {a}")


def run_mounts(args, client):
    a = args.action
    if a == "list":
        out(paginated_list(client.list_mounts()))
    elif a == "browse":
        if not args.id:
            die("--id required")
        out(client.browse_mount(args.id))
    else:
        die(f"Unknown mounts action: {a}")


# -----------------------------------------------------------------------
# CLI wiring
# -----------------------------------------------------------------------

MODULES = {
    "admin": run_admin,
    "vms": run_vms,
    "jobs": run_jobs,
    "policies": run_policies,
    "targets": run_targets,
    "events": run_events,
    "apps": run_apps,
    "shares": run_shares,
    "volumegroups": run_volumegroups,
    "users": run_users,
    "archives": run_archives,
    "windows": run_windows,
    "reports": run_reports,
    "credentials": run_credentials,
    "validation": run_validation,
    "webhooks": run_webhooks,
    "networks": run_networks,
    "mounts": run_mounts,
}


def main():
    parser = argparse.ArgumentParser(description="HYCU Backup & Recovery CLI")
    parser.add_argument("module", choices=sorted(MODULES.keys()), help="HYCU module")
    parser.add_argument("action", help="Action to perform")
    parser.add_argument("--id", help="Entity UUID")
    parser.add_argument("--backup-id", help="Backup UUID")
    parser.add_argument("--name", help="Entity name")
    parser.add_argument("--limit", type=int, help="Max results to return")

    args = parser.parse_args()

    try:
        client = HYCUClient()
    except SystemExit:
        return

    handler = MODULES[args.module]
    try:
        handler(args, client)
    except Exception as e:
        die(str(e))


if __name__ == "__main__":
    main()
