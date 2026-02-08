"""
NVD (National Vulnerability Database) collector.

Fetches recent high-severity CVEs from the NVD API v2.0.
Surfaces enterprise security pain: what vulnerabilities are actively
being disclosed, what software is affected.

No API key required (5 requests/30 seconds). Optional key for higher limits.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

import requests

from collectors.base import Collector
from config.settings import Config
from models import Item, Source
from storage.db import Storage

log = logging.getLogger(__name__)


class NVDCollector(Collector):
    NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, storage: Storage, config: Config):
        super().__init__(storage)
        self._config = config
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "signal-extract/0.1"
        if config.nvd_api_key:
            self._session.headers["apiKey"] = config.nvd_api_key

    def name(self) -> str:
        return "nvd"

    def collect(self) -> list[Item]:
        state = self.storage.get_collector_state(self.name())
        last_modified = state.get("last_modified", "")

        # Determine time window
        if last_modified:
            start_date = last_modified
        else:
            # First run: look back 7 days
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            start_date = seven_days_ago.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

        items = self._fetch_cves(start_date, end_date)

        # Update state
        self.storage.set_collector_state(self.name(), {
            "last_modified": end_date,
        })

        return items

    def _fetch_cves(self, start_date: str, end_date: str) -> list[Item]:
        """Fetch CVEs modified within the date range."""
        params = {
            "lastModStartDate": start_date,
            "lastModEndDate": end_date,
            "resultsPerPage": min(self._config.nvd_max_results, 50),
        }

        try:
            resp = self._session.get(self.NVD_API, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            log.error(f"NVD API request failed: {e}")
            return []

        vulnerabilities = data.get("vulnerabilities", [])
        log.info(f"NVD returned {len(vulnerabilities)} CVEs")

        items = []
        for vuln in vulnerabilities:
            cve = vuln.get("cve", {})
            item = self._parse_cve(cve)
            if item:
                # Skip if below CVSS threshold
                cvss = item.metadata.get("cvss_score", 0)
                if cvss < self._config.nvd_min_cvss:
                    continue

                # Skip if already collected
                if self.storage.has_item(item.content_hash):
                    continue

                items.append(item)

        return items

    def _parse_cve(self, cve: dict) -> Item | None:
        """Parse a CVE entry into an Item."""
        cve_id = cve.get("id", "")
        if not cve_id:
            return None

        # Get English description
        descriptions = cve.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break
        if not description and descriptions:
            description = descriptions[0].get("value", "")

        # Extract CVSS score (prefer v3.1, fall back to v3.0, then v2.0)
        cvss_score = 0.0
        severity = "UNKNOWN"
        metrics = cve.get("metrics", {})

        for metric_key in ["cvssMetricV31", "cvssMetricV30"]:
            metric_list = metrics.get(metric_key, [])
            if metric_list:
                cvss_data = metric_list[0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore", 0.0)
                severity = cvss_data.get("baseSeverity", "UNKNOWN")
                break

        if cvss_score == 0.0:
            v2_list = metrics.get("cvssMetricV2", [])
            if v2_list:
                cvss_data = v2_list[0].get("cvssData", {})
                cvss_score = cvss_data.get("baseScore", 0.0)
                severity = "HIGH" if cvss_score >= 7.0 else "MEDIUM" if cvss_score >= 4.0 else "LOW"

        # Extract CWE
        cwe_ids = []
        weaknesses = cve.get("weaknesses", [])
        for weakness in weaknesses:
            for desc in weakness.get("description", []):
                if desc.get("lang") == "en" and desc.get("value", "").startswith("CWE-"):
                    cwe_ids.append(desc["value"])

        # Extract affected products (simplified)
        affected_products = []
        configurations = cve.get("configurations", [])
        for config_node in configurations:
            for node in config_node.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    criteria = cpe_match.get("criteria", "")
                    if criteria:
                        # Extract vendor:product from CPE string
                        parts = criteria.split(":")
                        if len(parts) >= 5:
                            affected_products.append(f"{parts[3]}:{parts[4]}")

        url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
        title = f"[{severity}] {cve_id}: {description[:100]}"

        return Item(
            source=Source.NVD_CVE,
            source_id=f"nvd:{cve_id}",
            url=url,
            title=title,
            body=description,
            metadata={
                "cve_id": cve_id,
                "cvss_score": cvss_score,
                "severity": severity,
                "cwe_ids": cwe_ids[:5],
                "affected_products": affected_products[:10],
            },
        )
