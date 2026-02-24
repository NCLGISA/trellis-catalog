#!/usr/bin/env python3
"""Splunk REST API client.

Handles bearer-token authentication and provides methods for search jobs,
saved searches, fired alerts, index inventory, and server info via the
Splunk REST API (port 8089).  Works with both Splunk Cloud and Splunk
Enterprise (on-prem).

Environment:
    SPLUNK_URL          Search head URL (e.g. https://yourorg.splunkcloud.com:8089
                        or https://splunk.internal:8089)
    SPLUNK_TOKEN        Bearer authentication token from Settings > Tokens
    SPLUNK_VERIFY_TLS   Set to "false" for on-prem instances with self-signed
                        certificates (default: true)
"""

import json
import os
import sys
import time

import requests

SPLUNK_URL = os.environ.get("SPLUNK_URL", "").rstrip("/")
SPLUNK_TOKEN = os.environ.get("SPLUNK_TOKEN", "")
SPLUNK_VERIFY_TLS = os.environ.get("SPLUNK_VERIFY_TLS", "true").lower() not in ("false", "0", "no")


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


class SplunkClient:
    """REST client for Splunk Cloud and Splunk Enterprise APIs."""

    def __init__(self):
        if not SPLUNK_URL:
            die("SPLUNK_URL must be set (e.g. https://yourorg.splunkcloud.com:8089 or https://splunk.internal:8089).")
        if not SPLUNK_TOKEN:
            die("SPLUNK_TOKEN must be set (bearer token from Settings > Tokens).")

        self.base_url = SPLUNK_URL
        self.session = requests.Session()
        self.session.verify = SPLUNK_VERIFY_TLS
        self.session.headers.update({
            "Authorization": f"Bearer {SPLUNK_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded",
        })

        if not SPLUNK_VERIFY_TLS:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # -- HTTP helpers -------------------------------------------------------

    def get(self, path, params=None, timeout=30):
        params = dict(params or {})
        params.setdefault("output_mode", "json")
        url = f"{self.base_url}/services/{path.lstrip('/')}"
        r = self.session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def post(self, path, data=None, timeout=30):
        data = dict(data or {})
        data.setdefault("output_mode", "json")
        url = f"{self.base_url}/services/{path.lstrip('/')}"
        r = self.session.post(url, data=data, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def delete(self, path, timeout=30):
        url = f"{self.base_url}/services/{path.lstrip('/')}"
        r = self.session.delete(url, params={"output_mode": "json"}, timeout=timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return {"status": "deleted"}

    # ===== Server Info =====================================================

    def server_info(self):
        data = self.get("server/info")
        entries = data.get("entry", [])
        if entries:
            return entries[0].get("content", {})
        return data

    def server_health(self):
        data = self.get("server/health/splunkd/details")
        entries = data.get("entry", [])
        if entries:
            return entries[0].get("content", {})
        return data

    # ===== Search Jobs =====================================================

    def search(self, spl, earliest=None, latest=None, max_count=10000,
               exec_mode="normal", timeout_secs=300, poll_interval=2):
        """Submit a search and optionally wait for results.

        For exec_mode='oneshot', blocks and returns results directly.
        For exec_mode='normal', submits the job and polls until done or timeout.
        Returns a dict with 'sid', 'status', and 'results' (if complete).
        """
        if exec_mode == "oneshot":
            return self._oneshot(spl, earliest, latest, max_count)

        sid = self._create_job(spl, earliest, latest, max_count)
        return self._poll_job(sid, timeout_secs, poll_interval)

    def _oneshot(self, spl, earliest=None, latest=None, max_count=100):
        params = {
            "search": spl if spl.strip().startswith("|") else f"search {spl}",
            "exec_mode": "oneshot",
            "count": max_count,
            "output_mode": "json",
        }
        if earliest:
            params["earliest_time"] = earliest
        if latest:
            params["latest_time"] = latest

        url = f"{self.base_url}/services/search/jobs"
        r = self.session.post(url, data=params, timeout=120)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        return {
            "mode": "oneshot",
            "result_count": len(results),
            "results": results,
        }

    def _create_job(self, spl, earliest=None, latest=None, max_count=10000):
        params = {
            "search": spl if spl.strip().startswith("|") else f"search {spl}",
            "max_count": max_count,
            "output_mode": "json",
        }
        if earliest:
            params["earliest_time"] = earliest
        if latest:
            params["latest_time"] = latest

        data = self.post("search/jobs", data=params)
        return data.get("sid", "")

    def _poll_job(self, sid, timeout_secs=300, poll_interval=2):
        deadline = time.time() + timeout_secs
        while time.time() < deadline:
            status = self.job_status(sid)
            content = status.get("content", status)
            if content.get("isDone"):
                results = self.job_results(sid)
                return {
                    "sid": sid,
                    "status": "done",
                    "result_count": content.get("resultCount", 0),
                    "results": results,
                }
            dispatch_state = content.get("dispatchState", "unknown")
            if dispatch_state == "FAILED":
                msgs = content.get("messages", [])
                return {"sid": sid, "status": "failed", "messages": msgs}
            time.sleep(poll_interval)

        return {"sid": sid, "status": "timeout", "message": f"Job did not complete within {timeout_secs}s. Poll with: jobs status --sid {sid}"}

    def job_status(self, sid):
        data = self.get(f"search/jobs/{sid}")
        entries = data.get("entry", [])
        if entries:
            return entries[0]
        return data

    def job_results(self, sid, count=0, offset=0):
        params = {"output_mode": "json"}
        if count:
            params["count"] = count
        if offset:
            params["offset"] = offset
        url = f"{self.base_url}/services/search/jobs/{sid}/results"
        r = self.session.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])

    def list_jobs(self, count=20):
        data = self.get("search/jobs", params={"count": count})
        entries = data.get("entry", [])
        return [
            {
                "sid": e.get("content", {}).get("sid", e.get("name", "")),
                "label": e.get("content", {}).get("label", ""),
                "dispatchState": e.get("content", {}).get("dispatchState", ""),
                "isDone": e.get("content", {}).get("isDone", False),
                "resultCount": e.get("content", {}).get("resultCount", 0),
                "runDuration": e.get("content", {}).get("runDuration", 0),
                "earliestTime": e.get("content", {}).get("earliestTime", ""),
                "latestTime": e.get("content", {}).get("latestTime", ""),
            }
            for e in entries
        ]

    def cancel_job(self, sid):
        return self.post(f"search/jobs/{sid}/control", data={"action": "cancel"})

    # ===== Saved Searches ==================================================

    def saved_searches(self, count=50):
        data = self.get("saved/searches", params={
            "count": count,
            "listDefaultActionArgs": False,
        })
        entries = data.get("entry", [])
        return [
            {
                "name": e.get("name", ""),
                "search": e.get("content", {}).get("search", ""),
                "is_scheduled": e.get("content", {}).get("is_scheduled", "0"),
                "disabled": e.get("content", {}).get("disabled", "0"),
                "cron_schedule": e.get("content", {}).get("cron_schedule", ""),
                "next_scheduled_time": e.get("content", {}).get("next_scheduled_time", ""),
                "alert_type": e.get("content", {}).get("alert_type", ""),
                "actions": e.get("content", {}).get("actions", ""),
            }
            for e in entries
        ]

    def saved_search_detail(self, name):
        data = self.get(f"saved/searches/{requests.utils.quote(name, safe='')}")
        entries = data.get("entry", [])
        if entries:
            return entries[0].get("content", {})
        return data

    def dispatch_saved_search(self, name, earliest=None, latest=None):
        params = {}
        if earliest:
            params["dispatch.earliest_time"] = earliest
        if latest:
            params["dispatch.latest_time"] = latest
        data = self.post(
            f"saved/searches/{requests.utils.quote(name, safe='')}/dispatch",
            data=params,
        )
        return data.get("sid", str(data))

    # ===== Indexes =========================================================

    def indexes(self, count=100):
        data = self.get("data/indexes", params={"count": count})
        entries = data.get("entry", [])
        return [
            {
                "name": e.get("name", ""),
                "totalEventCount": e.get("content", {}).get("totalEventCount", "0"),
                "currentDBSizeMB": e.get("content", {}).get("currentDBSizeMB", 0),
                "maxTotalDataSizeMB": e.get("content", {}).get("maxTotalDataSizeMB", 0),
                "minTime": e.get("content", {}).get("minTime", ""),
                "maxTime": e.get("content", {}).get("maxTime", ""),
                "datatype": e.get("content", {}).get("datatype", "event"),
                "disabled": e.get("content", {}).get("disabled", False),
            }
            for e in entries
        ]

    # ===== Fired Alerts ====================================================

    def fired_alerts(self, count=50):
        data = self.get("alerts/fired_alerts", params={"count": count})
        entries = data.get("entry", [])
        return [
            {
                "name": e.get("name", ""),
                "triggered_alerts": e.get("content", {}).get("triggered_alert_count", 0),
            }
            for e in entries
        ]

    # ===== Current User ====================================================

    def current_user(self):
        data = self.get("authentication/current-context")
        entries = data.get("entry", [])
        if entries:
            return entries[0].get("content", {})
        return data


def _main():
    import argparse
    parser = argparse.ArgumentParser(prog="splunk_client.py")
    parser.add_argument("command", choices=["test", "info", "indexes"])
    args = parser.parse_args()
    client = SplunkClient()
    if args.command == "test":
        info = client.server_info()
        print(json.dumps({
            "success": True,
            "server_name": info.get("serverName", ""),
            "version": info.get("version", ""),
        }, indent=2))
    elif args.command == "info":
        print(json.dumps(client.server_info(), indent=2))
    elif args.command == "indexes":
        print(json.dumps(client.indexes(), indent=2))


if __name__ == "__main__":
    _main()
