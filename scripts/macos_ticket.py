"""
Creates the macOS Target Versions Jira ticket when Apple releases a new macOS version.
Checks Apple's release page daily; triggers when the latest Tahoe version changes.
N-1 rule: N = most recent general release; N-1 = the release before that.
"""
import re
import sys
import json
import requests
from datetime import date
from bs4 import BeautifulSoup
from jira_client import (
    create_issue, _adf_doc, _adf_paragraph, _adf_text, _adf_link, _adf_bullet_list,
    URGENCY_HIGH_ID
)

ASSIGNEE = "6294e3e09c88e7006fb49b34"  # Pavel Ivanov
LABELS = ["SLA-Exclusion", "TVM-Corp"]

APPLE_LATEST_URL = "https://support.apple.com/en-us/109033"
APPLE_HISTORY_URL = "https://support.apple.com/en-us/100100"

# Versions to include (newest active first), with blocked status
MACOS_VERSIONS = [
    ("macOS Tahoe",   r"26\.\d+(?:\.\d+)?", False),
    ("macOS Sequoia", r"15\.\d+(?:\.\d+)?", False),
    ("macOS Sonoma",  r"14\.\d+(?:\.\d+)?", True),   # Blocked
]


def fetch_page(url):
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def get_latest_tahoe_version(soup):
    """Extract the latest general macOS Tahoe version from the Apple 'latest versions' page."""
    text = soup.get_text()
    idx = text.find("macOS Tahoe")
    if idx < 0:
        return None
    segment = text[idx:idx+200]
    versions = re.findall(r"(26\.\d+(?:\.\d+)?)", segment)
    return versions[0] if versions else None


def get_release_history(soup, version_pattern, limit=5):
    """
    Extract the last N releases for a macOS version from the history page.
    Returns list of version strings, newest first.
    Skips device-specific releases by excluding entries with '(' in the same line.
    """
    text = soup.get_text("\n")
    versions = []
    for line in text.splitlines():
        line = line.strip()
        m = re.search(version_pattern, line)
        if m:
            # Skip device-specific lines (e.g. "26.3.2 (MacBook Neo only)")
            if "only" in line.lower() or "MacBook Neo" in line:
                continue
            v = m.group(0)
            if v not in versions:
                versions.append(v)
        if len(versions) >= limit:
            break
    return versions


def get_n_minus_1(versions):
    """Return N-1 version string, or None if not enough data."""
    return versions[1] if len(versions) >= 2 else None


def build_description(version_data):
    """
    version_data: list of (display_name, n_minus_1_version, blocked)
    """
    blocks = []

    blocks.append(_adf_paragraph(
        _adf_text("Hello,"),
    ))
    blocks.append(_adf_paragraph(
        _adf_link(APPLE_LATEST_URL, APPLE_LATEST_URL),
    ))

    items = []
    for display_name, n1_version, blocked in version_data:
        if blocked:
            items.append([
                _adf_text(f"{display_name}: "),
                _adf_text("⚠️ BLOCK IT ON JAMF", bold=True),
            ])
        else:
            items.append([
                _adf_text(f"{display_name}: "),
                _adf_text("⚠️ ", ),
                _adf_text("N-1", bold=True),
                _adf_text(f" version -> {n1_version} -> To be configured in Jamf"),
            ])

    blocks.append(_adf_bullet_list(items))
    blocks.append(_adf_paragraph(_adf_text("Regards")))

    return _adf_doc(*blocks)


def run():
    state_path = "state.json"
    with open(state_path) as f:
        state = json.load(f)

    print("Fetching Apple latest versions page...")
    soup_latest = fetch_page(APPLE_LATEST_URL)
    latest_tahoe = get_latest_tahoe_version(soup_latest)

    if not latest_tahoe:
        print("ERROR: Could not extract macOS Tahoe version. Aborting.")
        sys.exit(1)

    print(f"Latest macOS Tahoe on Apple page: {latest_tahoe}")
    last_version = state.get("macos_last_version", "")

    if latest_tahoe == last_version:
        print(f"macOS version unchanged ({latest_tahoe}). No ticket needed.")
        return None

    print(f"Version changed: {last_version!r} -> {latest_tahoe!r}. Fetching release history...")
    soup_history = fetch_page(APPLE_HISTORY_URL)

    version_data = []
    for display_name, pattern, blocked in MACOS_VERSIONS:
        if blocked:
            version_data.append((display_name, None, True))
            continue
        history = get_release_history(soup_history, pattern)
        n1 = get_n_minus_1(history)
        if n1:
            print(f"  {display_name}: N-1 = {n1}")
            version_data.append((display_name, n1, False))
        else:
            print(f"  {display_name}: could not determine N-1 (history: {history})")

    today = date.today()
    month_name = today.strftime("%B")
    year = today.strftime("%Y")
    summary = f"{month_name} {year} - MacOS Target Versions"
    description = build_description(version_data)

    print(f"Creating ticket: {summary}")
    key = create_issue(
        summary, description, ASSIGNEE, LABELS,
        extra_fields={"customfield_11763": {"id": URGENCY_HIGH_ID}},
    )
    print(f"Created: {key}")

    state["macos_last_version"] = latest_tahoe
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    return key


if __name__ == "__main__":
    run()
