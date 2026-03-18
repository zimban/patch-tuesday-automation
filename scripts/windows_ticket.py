"""
Creates the monthly Windows 10/11 Target Versions Jira ticket.
Triggered on the second Wednesday of the month (day after Patch Tuesday).
N-1 rule: N = current month's B-release; N-1 = previous month's B-release.
"""
import re
import sys
import json
import requests
from datetime import date
from bs4 import BeautifulSoup
from jira_client import (
    create_issue, _adf_doc, _adf_paragraph, _adf_text, _adf_link, _adf_bullet_list
)

ASSIGNEE = "60d388899469280070147812"  # Florenc Malaj
LABELS = ["SLA-Exclusion", "TVM-Corp"]

WIN11_URL = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
WIN10_URL = "https://learn.microsoft.com/en-us/windows/release-health/release-information"

# Windows 11 versions to include (in display order), with EOS status
WIN11_VERSIONS = [
    ("26H1", False),
    ("25H2", False),
    ("24H2", False),
    ("23H2", False),
    ("22H2", True),   # EOS
    ("21H2", True),   # EOS
]

# Windows 10: all EOS except 21H2 LTSC
WIN10_EOS_VERSIONS = ["22H2"]
WIN10_LTSC_VERSION = "21H2"  # LTSC — still supported


def is_second_wednesday(today=None):
    today = today or date.today()
    if today.weekday() != 2:  # Wednesday = 2
        return False
    first_day = today.replace(day=1)
    days_to_first_wed = (2 - first_day.weekday()) % 7
    first_wed_day = 1 + days_to_first_wed
    return today.day == first_wed_day + 7


def fetch_page(url):
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def extract_b_releases_for_version(soup, version_label):
    """
    Find the table for a given version label (e.g. '26H1') and return
    all B-type rows as dicts: {update_type, build, kb, kb_url}
    """
    # Find the header/strong that contains "Version 26H1" or similar
    header = None
    for tag in soup.find_all(["h2", "h3", "strong", "p"]):
        if re.search(rf'\bVersion {re.escape(version_label)}\b', tag.get_text()):
            header = tag
            break
    if not header:
        return []

    # Walk forward to find the next table
    table = header.find_next("table")
    if not table:
        return []

    rows = table.find_all("tr")
    b_releases = []
    for row in rows[1:]:  # Skip header
        cols = row.find_all(["td", "th"])
        if len(cols) < 5:
            continue
        update_type = cols[1].get_text(strip=True)
        build = cols[3].get_text(strip=True)
        kb_anchor = cols[4].find("a")
        kb = kb_anchor.get_text(strip=True) if kb_anchor else ""
        kb_url = kb_anchor.get("href", "") if kb_anchor else ""
        if kb_url and not kb_url.startswith("http"):
            kb_url = "https://support.microsoft.com" + kb_url

        # Only keep B-type (format: YYYY-MM B)
        if re.match(r"\d{4}-\d{2} B$", update_type):
            b_releases.append({"update_type": update_type, "build": build, "kb": kb, "kb_url": kb_url})

    return b_releases  # Newest first as they appear on the page


def get_n_minus_1(b_releases):
    """Return the N-1 entry (index 1) or None if not enough data."""
    if len(b_releases) >= 2:
        return b_releases[1]
    return None


def build_description(win11_data, win10_ltsc_data):
    """Build the ADF description for the ticket."""
    blocks = []

    # --- Windows 10 section ---
    blocks.append(_adf_paragraph(
        _adf_text("⚠️ "),
        _adf_text("Windows 10 -> N-1", bold=True),
        _adf_text(" version -> To be configured on Intune"),
    ))

    win10_items = []
    # All standard versions are EOS
    for v in WIN10_EOS_VERSIONS:
        win10_items.append([
            _adf_text(f"{v} → "),
            _adf_text("End of servicing 2025-10-14 (To be blocked in Intune)", bold=True),
        ])
    # LTSC exception
    if win10_ltsc_data:
        entry = win10_ltsc_data
        win10_items.append([
            _adf_text(f"{WIN10_LTSC_VERSION} LTSC - "),
            _adf_link(entry["kb"], entry["kb_url"]),
            _adf_text(" (OS Build "),
            _adf_text(entry["build"], bold=True),
            _adf_text(")"),
        ])
    blocks.append(_adf_bullet_list(win10_items))

    # --- Windows 11 section ---
    blocks.append(_adf_paragraph(
        _adf_text("⚠️ "),
        _adf_text("Windows 11 -> N-1", bold=True),
        _adf_text(" version -> To be configured on Intune"),
    ))

    win11_items = []
    for version, is_eos in WIN11_VERSIONS:
        if is_eos:
            win11_items.append([
                _adf_text(f"{version} → "),
                _adf_text("End of servicing (To be blocked in Intune)", bold=True),
            ])
        elif version in win11_data and win11_data[version]:
            entry = win11_data[version]
            win11_items.append([
                _adf_text(f"{version} - "),
                _adf_link(entry["kb"], entry["kb_url"]),
                _adf_text(" (OS Build "),
                _adf_text(entry["build"], bold=True),
                _adf_text(")"),
            ])
    blocks.append(_adf_bullet_list(win11_items))

    # --- Reference links ---
    blocks.append(_adf_paragraph(
        _adf_text("For additional information, please refer to: "),
        _adf_link(
            "https://learn.microsoft.com/en-us/windows/release-health/release-information",
            "https://learn.microsoft.com/en-us/windows/release-health/release-information",
        ),
    ))
    blocks.append(_adf_paragraph(
        _adf_text("For additional information, please refer to: "),
        _adf_link(
            "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information",
            "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information",
        ),
    ))

    return _adf_doc(*blocks)


def run():
    today = date.today()

    if not is_second_wednesday(today):
        print(f"Today ({today}) is not the second Wednesday. Skipping Windows ticket.")
        return None

    state_path = "state.json"
    with open(state_path) as f:
        state = json.load(f)

    current_month = today.strftime("%Y-%m")
    if state.get("windows_last_created_month") == current_month:
        print(f"Windows ticket already created for {current_month}. Skipping.")
        return None

    print(f"Second Wednesday confirmed. Fetching Windows release data...")

    soup11 = fetch_page(WIN11_URL)
    soup10 = fetch_page(WIN10_URL)

    # Collect N-1 for each Windows 11 version
    win11_data = {}
    for version, is_eos in WIN11_VERSIONS:
        if is_eos:
            continue
        releases = extract_b_releases_for_version(soup11, version)
        n_minus_1 = get_n_minus_1(releases)
        if n_minus_1:
            win11_data[version] = n_minus_1
            print(f"  Win11 {version}: N-1 = {n_minus_1['build']} ({n_minus_1['kb']})")
        else:
            print(f"  Win11 {version}: could not determine N-1 (only {len(releases)} B-releases found)")

    # Windows 10 21H2 LTSC N-1
    win10_ltsc_releases = extract_b_releases_for_version(soup10, WIN10_LTSC_VERSION)
    win10_ltsc_n1 = get_n_minus_1(win10_ltsc_releases)
    if win10_ltsc_n1:
        print(f"  Win10 21H2 LTSC: N-1 = {win10_ltsc_n1['build']} ({win10_ltsc_n1['kb']})")

    month_name = today.strftime("%B")
    year = today.strftime("%Y")
    summary = f"{month_name} {year} - Windows 10/11 Target versions"
    description = build_description(win11_data, win10_ltsc_n1)

    print(f"Creating ticket: {summary}")
    key = create_issue(summary, description, ASSIGNEE, LABELS)
    print(f"Created: {key}")

    state["windows_last_created_month"] = current_month
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    return key


if __name__ == "__main__":
    result = run()
    sys.exit(0 if result is not None or not is_second_wednesday() else 1)
