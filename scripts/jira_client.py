"""Jira REST API client for creating Hotfix tickets in the IT project."""
import os
import requests
from requests.auth import HTTPBasicAuth

JIRA_BASE_URL = "https://uipath.atlassian.net"
JIRA_EMAIL = "andrei.craiu@uipath.com"
CLOUD_ID = "2e10c12a-b0cf-4474-9dda-1459a75f0278"

# Fixed field IDs
PROJECT_ID = "10506"
ISSUE_TYPE_ID = "10572"       # Hotfixes
COMPONENT_TYPE_ID = "18753"   # Alerting for Patching
PRIORITY_NORMAL_ID = "5"
URGENCY_HIGH_ID = "11497"


def _auth():
    token = os.environ["JIRA_API_TOKEN"]
    return HTTPBasicAuth(JIRA_EMAIL, token)


def _adf_doc(*blocks):
    """Wrap content blocks in an ADF document."""
    return {"version": 1, "type": "doc", "content": list(blocks)}


def _adf_paragraph(*inline_nodes):
    return {"type": "paragraph", "content": list(inline_nodes)}


def _adf_text(text, bold=False):
    node = {"type": "text", "text": text}
    if bold:
        node["marks"] = [{"type": "strong"}]
    return node


def _adf_link(text, url):
    return {
        "type": "text",
        "text": text,
        "marks": [{"type": "link", "attrs": {"href": url}}],
    }


def _adf_bullet_list(items):
    """Each item is a list of inline nodes."""
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [_adf_paragraph(*item)],
            }
            for item in items
        ],
    }


def create_issue(summary, description_adf, assignee_account_id, labels, extra_fields=None):
    """Create a Jira issue. Returns the new issue key (e.g. IT-XXXXX)."""
    fields = {
        "project": {"id": PROJECT_ID},
        "issuetype": {"id": ISSUE_TYPE_ID},
        "summary": summary,
        "description": description_adf,
        "assignee": {"accountId": assignee_account_id},
        "priority": {"id": PRIORITY_NORMAL_ID},
        "labels": labels,
        "customfield_11484": {"id": COMPONENT_TYPE_ID},
    }
    if extra_fields:
        fields.update(extra_fields)

    resp = requests.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue",
        json={"fields": fields},
        auth=_auth(),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["key"]
