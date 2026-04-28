# Patch Tuesday Automation

Automatically creates Jira Hotfix tickets in the UiPath IT project after Microsoft Patch Tuesday and Apple macOS releases.

## What it does

### Windows 10/11 Target Versions
- Runs on the **second Wednesday of each month** (day after Patch Tuesday)
- Fetches the latest B-type builds from Microsoft's release health pages
- Applies the **N-1 rule**: uses the previous month's B-release as the minimum compliant version
- Creates a Jira ticket assigned with Intune configuration guidance

### macOS Target Versions
- Runs **daily** and checks Apple's release page for new macOS versions
- Tracks **Tahoe and Sequoia independently** — triggers a ticket whenever either version changes
- Applies the N-1 rule per active macOS version
- Creates a Jira ticket with Jamf configuration guidance

## How it works

```
GitHub Actions (daily 10:00 UTC)
        │
        ├── Windows job
        │     ├── Is today the 2nd Wednesday? → No → skip
        │     └── Yes → fetch Microsoft pages → calculate N-1 → create Jira ticket
        │
        └── macOS job (runs after Windows)
              ├── Fetch Apple latest versions page
              ├── Compare Tahoe + Sequoia against state.json
              ├── Both unchanged → skip
              └── Either changed → fetch release history → calculate N-1 → create Jira ticket
```

State is persisted in `state.json` (committed back to this repo after each ticket creation) to prevent duplicate tickets.

## Jira ticket details

| Field | Windows | macOS |
|---|---|---|
| Project | IT | IT |
| Issue type | Hotfixes | Hotfixes |
| Priority | Normal | Normal |
| Labels | `SLA-Exclusion`, `TVM-Corp` | `SLA-Exclusion`, `TVM-Corp` |
| Component | Alerting for Patching | Alerting for Patching |

## Reference sources

- Windows 11: https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information
- Windows 10: https://learn.microsoft.com/en-us/windows/release-health/release-information
- macOS latest: https://support.apple.com/en-us/109033
- macOS history: https://support.apple.com/en-us/100100

## Setup

### Prerequisites
- GitHub repository with Actions enabled
- Atlassian API token (generate at https://id.atlassian.com/manage-api-tokens)

### Configuration
Add the following secret in **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `JIRA_API_TOKEN` | Your Atlassian API token |

The Jira email and instance URL are hardcoded in `scripts/jira_client.py`.

## Repository structure

```
├── .github/workflows/
│   └── patch-tuesday.yml     # Scheduled workflow (daily 10:00 UTC)
├── scripts/
│   ├── jira_client.py        # Jira REST API helper + ADF builder
│   ├── windows_ticket.py     # Windows N-1 logic + ticket creation
│   └── macos_ticket.py       # macOS version detection + ticket creation
├── requirements.txt
└── state.json                # Tracks last created Windows month + last seen Tahoe and Sequoia versions
```

## Maintenance

- **Jira API token expires** → generate a new one and update the `JIRA_API_TOKEN` secret
- **New Windows version released** → add it to `WIN11_VERSIONS` in `windows_ticket.py`
- **macOS version goes EOS** → update `MACOS_VERSIONS` in `macos_ticket.py`
- **Manual trigger** → Actions tab → *Patch Tuesday Automation* → *Run workflow*
