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

"""HYCU Backup & Recovery — Python API Client.

Wraps the HYCU REST API v1.0 for use by the CLI and health-check tools.
Authenticates via per-operator API key (Bearer token).

Environment variables (injected by Tendril credential vault):
    HYCU_SERVER   — HYCU controller IP or hostname (e.g. hycu.example.com)
    HYCU_API_KEY  — Per-operator API key generated in the HYCU UI
    HYCU_PORT     — Optional, defaults to 8443
"""

import json
import os
import sys
import urllib3

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HYCUClient:
    def __init__(self, server=None, api_key=None, port=None):
        self.server = server or os.environ.get("HYCU_SERVER", "")
        self.api_key = api_key or os.environ.get("HYCU_API_KEY", "")
        self.port = port or os.environ.get("HYCU_PORT", "8443")
        if not self.server:
            _die("HYCU_SERVER not set.")
        if not self.api_key:
            _die("HYCU_API_KEY not set.")
        self.base = f"https://{self.server}:{self.port}/rest/v1.0"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path, params=None):
        r = requests.get(
            f"{self.base}{path}",
            headers=self._headers(),
            params=params,
            verify=False,
            timeout=30,
        )
        r.raise_for_status()
        return r.json() if r.text else {}

    def _post(self, path, data=None, params=None):
        r = requests.post(
            f"{self.base}{path}",
            headers=self._headers(),
            json=data,
            params=params,
            verify=False,
            timeout=120,
        )
        r.raise_for_status()
        return r.json() if r.text else {}

    def _patch(self, path, data=None):
        r = requests.patch(
            f"{self.base}{path}",
            headers=self._headers(),
            json=data,
            verify=False,
            timeout=30,
        )
        r.raise_for_status()
        return r.json() if r.text else {}

    def _delete(self, path):
        r = requests.delete(
            f"{self.base}{path}",
            headers=self._headers(),
            verify=False,
            timeout=30,
        )
        r.raise_for_status()
        return r.json() if r.text else {}

    # ------------------------------------------------------------------
    # Administration
    # ------------------------------------------------------------------

    def get_controller(self):
        return self._get("/administration/controller")

    def get_controller_state(self):
        return self._get("/administration/controller/state")

    def get_software_version(self):
        return self._get("/administration/software")

    def get_license(self):
        return self._get("/administration/license")

    def get_hostname(self):
        return self._get("/administration/hostname")

    def get_timezone(self):
        return self._get("/administration/timezone")

    def get_scheduler_state(self):
        return self._get("/administration/scheduler")

    def get_suspend_mode(self):
        return self._get("/administration/suspendMode")

    def get_recovery_mode(self):
        return self._get("/administration/recoveryMode")

    def get_encryption_keys(self):
        return self._get("/administration/encryption")

    def get_logging_config(self):
        return self._get("/administration/logging")

    def get_purge_config(self):
        return self._get("/administration/purge")

    def get_worker(self):
        return self._get("/administration/worker")

    def get_controller_mode(self):
        return self._get("/administration/mode")

    def get_clusters(self):
        return self._get("/administration/clusters")

    def get_cluster_vlans(self, cluster_uuid):
        return self._get(f"/administration/clusters/{cluster_uuid}/vlans")

    def get_cluster_containers(self, cluster_uuid):
        return self._get(f"/administration/clusters/{cluster_uuid}/containers")

    def get_physical_machines(self):
        return self._get("/administration/physicalmachines")

    def suspend_scheduler(self):
        return self._post("/administration/scheduler/standby")

    def start_scheduler(self):
        return self._post("/administration/scheduler/start")

    # ------------------------------------------------------------------
    # VMs
    # ------------------------------------------------------------------

    def list_vms(self, page_size=None):
        params = {}
        if page_size:
            params["pageSize"] = page_size
        return self._get("/vms", params=params)

    def get_vm(self, vm_uuid):
        return self._get(f"/vms/{vm_uuid}")

    def list_vm_backups(self, vm_uuid):
        return self._get(f"/vms/{vm_uuid}/backups")

    def get_vm_backup(self, vm_uuid, backup_uuid):
        return self._get(f"/vms/{vm_uuid}/backup/{backup_uuid}")

    def list_vm_snapshots(self, vm_uuid):
        return self._get(f"/vms/{vm_uuid}/snapshots")

    def get_vm_snapshot(self, vm_uuid, snapshot_uuid):
        return self._get(f"/vms/{vm_uuid}/snapshots/{snapshot_uuid}")

    def get_vm_disks(self, vm_uuid):
        return self._get(f"/vms/{vm_uuid}/disks")

    def get_vm_restore_locations(self, vm_uuid):
        return self._get(f"/vms/{vm_uuid}/restoreLocations")

    def list_all_vm_backups(self):
        return self._get("/vms/backups")

    def list_all_vm_snapshots(self):
        return self._get("/vms/snapshots")

    def get_backup_metadata(self, backup_uuid):
        return self._get(f"/vms/backup/{backup_uuid}/metadata")

    def get_backup_disks(self, backup_uuid):
        return self._get(f"/vms/backup/{backup_uuid}/disks")

    def run_vm_backup(self, vm_uuids):
        return self._post("/vms/backup", data=vm_uuids if isinstance(vm_uuids, list) else [vm_uuids])

    def run_vm_restore(self, restore_data):
        return self._post("/vms/restore", data=restore_data)

    def run_vm_archive(self, archive_data):
        return self._post("/vms/archive", data=archive_data)

    def run_vm_export(self, export_data):
        return self._post("/vms/export", data=export_data)

    def delete_vm_backup(self, vm_uuid, backup_uuid):
        return self._delete(f"/vms/{vm_uuid}/backup/{backup_uuid}")

    def mount_vm_backup(self, vm_uuid, backup_uuid):
        return self._post(f"/vms/{vm_uuid}/backups/{backup_uuid}/mount")

    def unmount_vm_backup(self, vm_uuid, backup_uuid):
        return self._delete(f"/vms/{vm_uuid}/backups/{backup_uuid}/mount")

    def mount_vm_snapshot(self, vm_uuid, snapshot_uuid):
        return self._post(f"/vms/{vm_uuid}/snapshots/{snapshot_uuid}/mount")

    def unmount_vm_snapshot(self, vm_uuid, snapshot_uuid):
        return self._delete(f"/vms/{vm_uuid}/snapshots/{snapshot_uuid}/mount")

    def configure_vm(self, vm_uuid, config_data):
        return self._post(f"/vms/{vm_uuid}/configure", data=config_data)

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def list_jobs(self, page_size=None):
        params = {}
        if page_size:
            params["pageSize"] = page_size
        return self._get("/jobs", params=params)

    def get_job(self, job_uuid):
        return self._get(f"/jobs/{job_uuid}")

    def get_job_report(self, job_uuid):
        return self._get(f"/jobs/{job_uuid}/report")

    def get_sub_job(self, job_uuid, sub_job_uuid):
        return self._get(f"/jobs/{job_uuid}/{sub_job_uuid}")

    def kill_job(self, job_uuid):
        return self._delete(f"/jobs/{job_uuid}")

    def rerun_job(self, job_uuid):
        return self._post(f"/jobs/{job_uuid}")

    def kill_multiple_jobs(self, job_uuids):
        return self._post("/jobs/multiple", data=job_uuids)

    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------

    def list_policies(self):
        return self._get("/policies")

    def get_policy(self, policy_uuid):
        return self._get(f"/policies/{policy_uuid}")

    def get_policy_backupable_count(self, policy_uuid):
        return self._get(f"/policies/{policy_uuid}/backupable")

    def create_policy(self, policy_data):
        return self._post("/policies", data=policy_data)

    def update_policy(self, policy_uuid, policy_data):
        return self._patch(f"/policies/{policy_uuid}", data=policy_data)

    def delete_policy(self, policy_uuid):
        return self._delete(f"/policies/{policy_uuid}")

    def assign_policy(self, policy_uuid, assign_data):
        return self._post(f"/policies/{policy_uuid}/assign", data=assign_data)

    def unassign_policy(self, unassign_data):
        return self._post("/policies/unassign", data=unassign_data)

    def get_retention_limit(self):
        return self._get("/policies/retentionLimit")

    # ------------------------------------------------------------------
    # Targets (backup storage)
    # ------------------------------------------------------------------

    def list_targets(self):
        return self._get("/targets")

    def get_target(self, target_uuid):
        return self._get(f"/targets/{target_uuid}")

    def add_target(self, target_data):
        return self._post("/targets", data=target_data)

    def update_target(self, target_uuid, target_data):
        return self._patch(f"/targets/{target_uuid}", data=target_data)

    def delete_target(self, target_uuid):
        return self._delete(f"/targets/{target_uuid}")

    def test_target(self, target_data):
        return self._post("/targets/test", data=target_data)

    def test_target_update(self, target_uuid):
        return self._post(f"/targets/test/{target_uuid}")

    def benchmark_target(self, target_uuid):
        return self._post(f"/targets/benchmark/{target_uuid}")

    def activate_target(self, target_uuid):
        return self._post(f"/targets/{target_uuid}/activate")

    def deactivate_target(self, target_uuid):
        return self._post(f"/targets/{target_uuid}/deactivate")

    def get_restore_locations(self, backup_uuid):
        return self._get(f"/targets/restoreLocations/{backup_uuid}")

    def sync_target_catalog(self):
        return self._get("/targets/synchronizeTargetCatalog")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def list_events(self, page_size=None):
        params = {}
        if page_size:
            params["pageSize"] = page_size
        return self._get("/events", params=params)

    def get_event(self, event_uuid):
        return self._get(f"/events/{event_uuid}")

    def get_event_categories(self):
        return self._get("/events/eventCategories")

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------

    def list_applications(self):
        return self._get("/applications")

    def get_application(self, app_uuid):
        return self._get(f"/applications/{app_uuid}")

    def list_app_backups(self, app_uuid):
        return self._get(f"/applications/{app_uuid}/backup")

    def get_app_backup(self, app_uuid, backup_uuid):
        return self._get(f"/applications/{app_uuid}/backup/{backup_uuid}")

    def get_app_config(self, app_uuid):
        return self._get(f"/applications/{app_uuid}/configure")

    def set_app_config(self, app_uuid, config_data):
        return self._post(f"/applications/{app_uuid}/configure", data=config_data)

    def run_app_discovery(self):
        return self._post("/applications/discovery")

    def restore_app_backup(self, backup_uuid, restore_data=None):
        return self._post(f"/applications/restore/{backup_uuid}", data=restore_data)

    def delete_app_backup(self, app_uuid, backup_uuid):
        return self._delete(f"/applications/{app_uuid}/backup/{backup_uuid}")

    def list_app_clusters(self):
        return self._get("/applications/cluster")

    def get_app_cluster(self, cluster_uuid):
        return self._get(f"/applications/cluster/{cluster_uuid}")

    # ------------------------------------------------------------------
    # Shares (file share protection)
    # ------------------------------------------------------------------

    def list_shares(self):
        return self._get("/shares")

    def get_share(self, share_uuid):
        return self._get(f"/shares/{share_uuid}")

    def list_share_backups(self, share_uuid):
        return self._get(f"/shares/{share_uuid}/backups")

    def list_all_share_backups(self):
        return self._get("/shares/backups")

    def run_share_backup(self, share_data):
        return self._post("/shares/backup", data=share_data)

    def run_share_archive(self, archive_data):
        return self._post("/shares/archive", data=archive_data)

    def run_share_export(self, export_data):
        return self._post("/shares/export", data=export_data)

    def delete_share_backup(self, share_uuid, backup_uuid):
        return self._delete(f"/shares/{share_uuid}/backup/{backup_uuid}")

    def update_share_config(self, share_uuid, config_data):
        return self._patch(f"/shares/{share_uuid}/config", data=config_data)

    def restore_share_items(self, backup_uuid, restore_data):
        return self._post(f"/shares/backup/{backup_uuid}/restoreShareItems", data=restore_data)

    def browse_share_backup(self, backup_uuid):
        return self._get(f"/shares/backup/{backup_uuid}/browseShare")

    def download_share_items(self, backup_uuid, download_data):
        return self._post(f"/shares/backup/{backup_uuid}/download", data=download_data)

    # ------------------------------------------------------------------
    # Volume Groups
    # ------------------------------------------------------------------

    def list_volume_groups(self):
        return self._get("/volumegroups")

    def get_volume_group(self, vg_uuid):
        return self._get(f"/volumegroups/{vg_uuid}")

    def list_vg_backups(self, vg_uuid):
        return self._get(f"/volumegroups/{vg_uuid}/backups")

    def get_vg_backup(self, vg_uuid, backup_uuid):
        return self._get(f"/volumegroups/{vg_uuid}/backup/{backup_uuid}")

    def list_all_vg_backups(self):
        return self._get("/volumegroups/backups")

    def delete_vg_backup(self, vg_uuid, backup_uuid):
        return self._delete(f"/volumegroups/{vg_uuid}/backup/{backup_uuid}")

    # ------------------------------------------------------------------
    # Schedules (trigger backup/archive jobs)
    # ------------------------------------------------------------------

    def run_scheduled_backup(self, data):
        return self._post("/schedules/backup", data=data)

    def run_scheduled_archive(self, data):
        return self._post("/schedules/archive", data=data)

    def run_scheduled_app_backup(self, data):
        return self._post("/schedules/backupApp", data=data)

    def run_scheduled_app_archive(self, data):
        return self._post("/schedules/archiveApp", data=data)

    def run_scheduled_share_backup(self, data):
        return self._post("/schedules/backupShare", data=data)

    def run_scheduled_share_archive(self, data):
        return self._post("/schedules/archiveShare", data=data)

    def run_scheduled_vg_backup(self, data):
        return self._post("/schedules/backupVolumeGroup", data=data)

    def run_scheduled_vg_archive(self, data):
        return self._post("/schedules/archiveVolumeGroup", data=data)

    # ------------------------------------------------------------------
    # Users & Groups
    # ------------------------------------------------------------------

    def list_users(self, page_size=None):
        params = {}
        if page_size:
            params["pageSize"] = page_size
        return self._get("/users", params=params)

    def get_user(self, user_uuid):
        return self._get(f"/users/{user_uuid}")

    def get_user_roles(self):
        return self._get("/users/allroles")

    def get_user_groups(self, user_uuid):
        return self._get(f"/users/{user_uuid}/groups")

    def list_user_groups(self):
        return self._get("/usergroups")

    def get_user_group(self, group_uuid):
        return self._get(f"/usergroups/{group_uuid}")

    # ------------------------------------------------------------------
    # API Keys
    # ------------------------------------------------------------------

    def list_api_keys(self):
        return self._get("/apiKeys")

    def create_api_key(self, key_data):
        return self._post("/apiKeys", data=key_data)

    def revoke_api_key(self, key_uuid):
        return self._delete(f"/apiKeys/{key_uuid}")

    # ------------------------------------------------------------------
    # Archives
    # ------------------------------------------------------------------

    def list_archives(self):
        return self._get("/archives")

    def get_archive(self, archive_uuid):
        return self._get(f"/archives/{archive_uuid}")

    def get_archive_policies(self, archive_uuid):
        return self._get(f"/archives/{archive_uuid}/policies")

    def create_archive(self, archive_data):
        return self._post("/archives", data=archive_data)

    def update_archive(self, archive_uuid, archive_data):
        return self._patch(f"/archives/{archive_uuid}", data=archive_data)

    def delete_archive(self, archive_uuid):
        return self._delete(f"/archives/{archive_uuid}")

    # ------------------------------------------------------------------
    # Backup Windows
    # ------------------------------------------------------------------

    def list_backup_windows(self):
        return self._get("/backupwindows")

    def get_backup_window(self, window_uuid):
        return self._get(f"/backupwindows/{window_uuid}")

    def get_backup_window_policies(self, window_uuid):
        return self._get(f"/backupwindows/{window_uuid}/policies")

    def create_backup_window(self, window_data):
        return self._post("/backupwindows", data=window_data)

    def update_backup_window(self, window_uuid, window_data):
        return self._patch(f"/backupwindows/{window_uuid}", data=window_data)

    def delete_backup_window(self, window_uuid):
        return self._delete(f"/backupwindows/{window_uuid}")

    # ------------------------------------------------------------------
    # Restore Points
    # ------------------------------------------------------------------

    def list_restore_points(self):
        return self._get("/restorepoints")

    def expire_restore_points(self, data):
        return self._post("/restorepoints/expire", data=data)

    def edit_restore_point_retention(self, data):
        return self._post("/restorepoints/edit", data=data)

    # ------------------------------------------------------------------
    # Credential Groups
    # ------------------------------------------------------------------

    def list_credential_groups(self):
        return self._get("/credentialgroups")

    def create_credential_group(self, cred_data):
        return self._post("/credentialgroups", data=cred_data)

    def update_credential_group(self, cred_uuid, cred_data):
        return self._patch(f"/credentialgroups/{cred_uuid}", data=cred_data)

    def delete_credential_group(self, cred_uuid):
        return self._delete(f"/credentialgroups/{cred_uuid}")

    def assign_cred_to_vms(self, cred_uuid, vm_data):
        return self._post(f"/credentialgroups/{cred_uuid}/assign", data=vm_data)

    # ------------------------------------------------------------------
    # Validation Policies
    # ------------------------------------------------------------------

    def list_validation_policies(self):
        return self._get("/validationPolicies")

    def get_validation_policy(self, policy_uuid):
        return self._get(f"/validationPolicies/{policy_uuid}")

    def create_validation_policy(self, policy_data):
        return self._post("/validationPolicies", data=policy_data)

    def update_validation_policy(self, policy_uuid, policy_data):
        return self._patch(f"/validationPolicies/{policy_uuid}", data=policy_data)

    def delete_validation_policy(self, policy_uuid):
        return self._delete(f"/validationPolicies/{policy_uuid}")

    def assign_validation_policy(self, policy_uuid, assign_data):
        return self._post(f"/validationPolicies/{policy_uuid}/assign", data=assign_data)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def list_reports(self):
        return self._get("/reporting/reports")

    def get_report(self, report_uuid):
        return self._get(f"/reporting/reports/{report_uuid}")

    def generate_report_version(self, report_uuid):
        return self._post(f"/reporting/reports/{report_uuid}/version")

    def list_report_schedules(self):
        return self._get("/reporting/reports/scheduled")

    def schedule_report(self, report_uuid, schedule_data):
        return self._post(f"/reporting/reports/{report_uuid}/schedule", data=schedule_data)

    def clone_report(self, report_uuid):
        return self._post(f"/reporting/reports/{report_uuid}/clone")

    def delete_report(self, report_uuid):
        return self._delete(f"/reporting/reports/{report_uuid}")

    # ------------------------------------------------------------------
    # Active Directory
    # ------------------------------------------------------------------

    def list_active_directories(self):
        return self._get("/ads")

    def get_active_directory(self, ad_uuid):
        return self._get(f"/ads/{ad_uuid}")

    def verify_ad_credentials(self, ad_uuid):
        return self._post(f"/ads/{ad_uuid}/verify")

    # ------------------------------------------------------------------
    # Cloud Accounts
    # ------------------------------------------------------------------

    def list_cloud_accounts(self):
        return self._get("/cloudAccounts")

    def get_cloud_account(self, account_uuid):
        return self._get(f"/cloudAccounts/{account_uuid}")

    # ------------------------------------------------------------------
    # Networks
    # ------------------------------------------------------------------

    def list_networks(self):
        return self._get("/networks")

    def list_network_sites(self):
        return self._get("/networks/sites")

    def get_network_site(self, site_uuid):
        return self._get(f"/networks/sites/{site_uuid}")

    # ------------------------------------------------------------------
    # SMTP / Notifications
    # ------------------------------------------------------------------

    def get_smtp_settings(self):
        return self._get("/smtp")

    def list_notifications(self):
        return self._get("/notification")

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def list_webhooks(self):
        return self._get("/webhooks")

    def get_webhook(self, webhook_uuid):
        return self._get(f"/webhooks/{webhook_uuid}")

    def create_webhook(self, webhook_data):
        return self._post("/webhooks", data=webhook_data)

    def update_webhook(self, webhook_uuid, webhook_data):
        return self._patch(f"/webhooks/{webhook_uuid}", data=webhook_data)

    def delete_webhook(self, webhook_uuid):
        return self._delete(f"/webhooks/{webhook_uuid}")

    def ping_webhook(self, webhook_name):
        return self._post(f"/webhooks/{webhook_name}/ping")

    # ------------------------------------------------------------------
    # SSH
    # ------------------------------------------------------------------

    def get_ssh_keys(self):
        return self._get("/ssh/keys")

    def get_ssh_lock_state(self):
        return self._get("/ssh/lock")

    # ------------------------------------------------------------------
    # Certificates
    # ------------------------------------------------------------------

    def list_certificates(self):
        return self._get("/certificate")

    # ------------------------------------------------------------------
    # Upgrade / Hotfixes
    # ------------------------------------------------------------------

    def list_hotfixes(self):
        return self._get("/upgrade/hotfixes")

    def get_hotfix_info(self, hotfix_name):
        return self._get(f"/upgrade/hotfixes/{hotfix_name}/info")

    def get_upgrade_images(self):
        return self._get("/upgrade/images")

    # ------------------------------------------------------------------
    # Mounts (file-level restore)
    # ------------------------------------------------------------------

    def list_mounts(self):
        return self._get("/mounts")

    def get_mount(self, mount_uuid):
        return self._get(f"/mounts/{mount_uuid}")

    def browse_mount(self, mount_uuid):
        return self._get(f"/mounts/{mount_uuid}/browse")

    def restore_mount_items(self, mount_uuid, restore_data):
        return self._post(f"/mounts/{mount_uuid}/restoreitems", data=restore_data)

    # ------------------------------------------------------------------
    # Identity Providers
    # ------------------------------------------------------------------

    def list_identity_providers(self):
        return self._get("/idprovider")

    def get_identity_provider(self, idp_uuid):
        return self._get(f"/idprovider/{idp_uuid}")

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def get_telemetry(self):
        return self._get("/telemetry")

    # ------------------------------------------------------------------
    # Instances (HYCU instances)
    # ------------------------------------------------------------------

    def list_instances(self):
        return self._get("/instances")


def _die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)
