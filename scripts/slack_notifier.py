#!/usr/bin/env python3
"""
Send Slack notification with weekly scan summary.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
import requests

SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')


def send_slack_message(summary):
    """Send formatted Slack message with scan results."""
    
    total = summary.get('total_evaluated', 0)
    issues = summary.get('issues_created', 0)
    ready = summary.get('ready_to_merge', 0)
    review = summary.get('needs_review', 0)
    date = summary.get('date', datetime.now().isoformat())
    
    # Format date nicely
    date_obj = datetime.fromisoformat(date)
    date_str = date_obj.strftime('%B %d, %Y')
    
    # Build Slack message using blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔍 Weekly Alt Clouds Scan",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Scan Date:* {date_str}"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Evaluated*\n{total} candidates"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Issues Created*\n{issues} issues"
                }
            ]
        }
    ]
    
    # Add breakdown if there are issues
    if issues > 0:
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*✅ Ready to Merge*\n{ready} services (3/3 score)"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*⚠️ Needs Review*\n{review} services (2/3 score)"
                }
            ]
        })
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<https://github.com/datum-cloud/awesome-alt-clouds/issues?q=is%3Aissue+is%3Aopen+label%3Aautomation|View all issues on GitHub>"
            }
        })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No new candidates found this week._"
            }
        })
    
    # Add footer
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Automated by awesome-alt-clouds monitor"
            }
        ]
    })
    
    # Send to Slack
    payload = {
        "blocks": blocks
    }
    
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    
    if response.status_code == 200:
        print("✅ Slack notification sent successfully")
    else:
        print(f"❌ Failed to send Slack notification: {response.status_code}")
        print(response.text)


def main():
    # Find latest summary file
    eval_dir = Path('data/evaluations')
    if not eval_dir.exists():
        print("No evaluations directory found")
        return
    
    summary_files = sorted(eval_dir.glob('summary-*.json'))
    if not summary_files:
        print("No summary files found")
        # Create empty summary
        summary = {
            'date': datetime.now().isoformat(),
            'total_evaluated': 0,
            'issues_created': 0,
            'ready_to_merge': 0,
            'needs_review': 0
        }
    else:
        latest_summary = summary_files[-1]
        print(f"Sending notification for: {latest_summary}")
        
        with open(latest_summary) as f:
            summary = json.load(f)
    
    send_slack_message(summary)


if __name__ == '__main__':
    if not SLACK_WEBHOOK_URL:
        print("Error: SLACK_WEBHOOK_URL not found")
        sys.exit(1)
    main()
