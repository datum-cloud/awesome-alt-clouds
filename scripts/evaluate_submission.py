#!/usr/bin/env python3
"""
Evaluate a cloud service submission against the 3 criteria:
1. Transparent Public Pricing - Publicly visible pricing page
2. Usage-based Self-Service - Self-service signup with usage-based billing
3. Production Indicators - Public SLA or status page

Reads URL from ISSUE_BODY environment variable, outputs:
- evaluation_results.md: Markdown formatted results for GitHub comment
- evaluation_score.txt: Score (0-3) for labeling
"""

import os
import re
import sys
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup


def extract_field_from_issue(issue_body, field_name):
    """Extract a field value from the issue body"""
    pattern = rf'\*\*{field_name}:\*\*\s*(.+?)(?:\n|$)'
    match = re.search(pattern, issue_body)
    if match:
        return match.group(1).strip()
    return None


def extract_submission_data(issue_body):
    """Extract all submission data from the issue body"""
    return {
        'name': extract_field_from_issue(issue_body, 'Name'),
        'url': extract_field_from_issue(issue_body, 'URL'),
        'description': extract_field_from_issue(issue_body, 'Description'),
        'category': extract_field_from_issue(issue_body, 'Category'),
        'submitter': extract_field_from_issue(issue_body, 'Submitter'),
    }


def extract_url_from_issue(issue_body):
    """Extract the submitted URL from the issue body"""
    # Look for **URL:** pattern
    match = re.search(r'\*\*URL:\*\*\s*(https?://[^\s]+)', issue_body)
    if match:
        return match.group(1).strip()

    # Fallback: find any URL
    match = re.search(r'https?://[^\s]+', issue_body)
    if match:
        return match.group(0).strip()

    return None


def fetch_page(url, timeout=10):
    """Fetch a page and return soup, handling errors gracefully"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; AwesomeAltClouds/1.0; +https://github.com/datum-cloud/awesome-alt-clouds)'
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, None


def find_link_matching(soup, base_url, patterns):
    """Find a link on the page matching any of the given patterns"""
    if not soup:
        return None

    for pattern in patterns:
        # Check href attributes
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            text = a.get_text().lower()
            if pattern in href or pattern in text:
                return urljoin(base_url, a['href'])

    return None


def check_pricing_page(soup, base_url):
    """Check for transparent public pricing"""
    result = {
        'name': 'Transparent Public Pricing',
        'passed': False,
        'evidence': 'No pricing page found'
    }

    pricing_patterns = ['pricing', 'price', 'plans', 'cost', 'rates']
    pricing_url = find_link_matching(soup, base_url, pricing_patterns)

    if pricing_url:
        pricing_soup, final_url = fetch_page(pricing_url)
        if pricing_soup:
            # Look for pricing indicators
            text = pricing_soup.get_text().lower()
            price_indicators = ['$', '€', '£', '/month', '/mo', '/year', '/hr', 'per hour', 'free tier', 'pay as you go']

            for indicator in price_indicators:
                if indicator in text:
                    result['passed'] = True
                    result['evidence'] = f'Pricing page found at {final_url}'
                    return result

            result['evidence'] = f'Pricing page exists but no clear pricing found'

    return result


def check_self_service(soup, base_url):
    """Check for usage-based self-service signup"""
    result = {
        'name': 'Usage-based Self-Service',
        'passed': False,
        'evidence': 'No self-service signup found'
    }

    signup_patterns = ['signup', 'sign-up', 'register', 'get started', 'start free', 'try free', 'create account']

    if not soup:
        return result

    # Check for signup links/buttons
    for a in soup.find_all(['a', 'button']):
        text = a.get_text().lower()
        href = a.get('href', '').lower()

        for pattern in signup_patterns:
            if pattern in text or pattern in href:
                result['passed'] = True
                result['evidence'] = f'Self-service signup available'
                return result

    # Check for signup forms
    forms = soup.find_all('form')
    for form in forms:
        form_text = form.get_text().lower()
        if any(p in form_text for p in ['email', 'sign up', 'register']):
            result['passed'] = True
            result['evidence'] = 'Signup form found on homepage'
            return result

    return result


def check_production_indicators(soup, base_url):
    """Check for production indicators (SLA, status page)"""
    result = {
        'name': 'Production Indicators',
        'passed': False,
        'evidence': 'No SLA or status page found'
    }

    # Check for status page link
    status_patterns = ['status', 'uptime', 'system status']
    status_url = find_link_matching(soup, base_url, status_patterns)

    if status_url:
        result['passed'] = True
        result['evidence'] = f'Status page found: {status_url}'
        return result

    # Check for SLA in page text
    if soup:
        text = soup.get_text().lower()
        sla_patterns = ['sla', 'service level', '99.9%', '99.99%', 'uptime guarantee']

        for pattern in sla_patterns:
            if pattern in text:
                result['passed'] = True
                result['evidence'] = f'SLA mentioned on website'
                return result

    # Try common status page URLs
    domain = urlparse(base_url).netloc.replace('www.', '')
    common_status_urls = [
        f'https://status.{domain}',
        f'https://{domain}/status',
        f'https://{domain.split(".")[0]}.statuspage.io',
    ]

    for status_url in common_status_urls:
        try:
            response = requests.head(status_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                result['passed'] = True
                result['evidence'] = f'Status page found: {status_url}'
                return result
        except:
            continue

    return result


def extract_company_name(url, soup):
    """Try to extract company name from the page"""
    if soup:
        # Try title tag
        title = soup.find('title')
        if title:
            name = title.get_text().split('|')[0].split('-')[0].strip()
            if name and len(name) < 50:
                return name

    # Fallback to domain
    domain = urlparse(url).netloc.replace('www.', '')
    return domain.split('.')[0].title()


def evaluate_service(url):
    """Evaluate a service against all 3 criteria"""
    print(f"Evaluating: {url}")

    soup, final_url = fetch_page(url)

    if not soup:
        return {
            'url': url,
            'company_name': extract_company_name(url, None),
            'score': 0,
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': False, 'evidence': 'Could not fetch website'},
                {'name': 'Usage-based Self-Service', 'passed': False, 'evidence': 'Could not fetch website'},
                {'name': 'Production Indicators', 'passed': False, 'evidence': 'Could not fetch website'},
            ],
            'error': 'Could not fetch website'
        }

    base_url = final_url or url

    criteria = [
        check_pricing_page(soup, base_url),
        check_self_service(soup, base_url),
        check_production_indicators(soup, base_url),
    ]

    score = sum(1 for c in criteria if c['passed'])

    return {
        'url': url,
        'company_name': extract_company_name(url, soup),
        'score': score,
        'criteria': criteria,
    }


def generate_markdown_results(result):
    """Generate markdown formatted results"""
    score = result['score']

    if score == 3:
        status = "Ready to Merge"
        emoji = "green_circle"
    elif score == 2:
        status = "Needs Review"
        emoji = "yellow_circle"
    else:
        status = "Does Not Meet Criteria"
        emoji = "red_circle"

    md = f"""## Evaluation Results

**Service:** {result['company_name']}
**URL:** {result['url']}
**Score:** {score}/3 :{emoji}: {status}

### Criteria Evaluation

| Criteria | Status | Evidence |
|----------|--------|----------|
"""

    for c in result['criteria']:
        status_icon = ":white_check_mark:" if c['passed'] else ":x:"
        md += f"| {c['name']} | {status_icon} | {c['evidence']} |\n"

    if score >= 2:
        md += f"""
### Next Steps

This service meets {score}/3 criteria and qualifies for inclusion in the list.

:rocket: **A Pull Request will be automatically created to add this service to the README.**

"""
        if score == 3:
            md += "The PR can be merged after a brief maintainer review."
        else:
            md += "A maintainer should review the missing criteria before merging the PR."
    else:
        md += """
### Next Steps

This service does not meet the minimum criteria (2/3) for inclusion.
Please review the criteria and resubmit if the service has been updated.
"""

    md += "\n---\n*Evaluated automatically by the Awesome Alt Clouds bot*"

    return md


def main():
    # Get issue body from environment
    issue_body = os.environ.get('ISSUE_BODY', '')
    issue_number = os.environ.get('ISSUE_NUMBER', '')

    if not issue_body:
        print("Error: ISSUE_BODY environment variable not set")
        sys.exit(1)

    # Extract submission data
    submission = extract_submission_data(issue_body)
    url = submission.get('url') or extract_url_from_issue(issue_body)

    if not url:
        # Write error results
        with open('evaluation_results.md', 'w') as f:
            f.write("## Evaluation Error\n\nCould not extract URL from submission. Please ensure the URL is properly formatted.")
        with open('evaluation_score.txt', 'w') as f:
            f.write('0')
        sys.exit(0)

    # Evaluate
    result = evaluate_service(url)

    # Override company name if provided in submission
    if submission.get('name'):
        result['company_name'] = submission['name']

    # Write results
    with open('evaluation_results.md', 'w') as f:
        f.write(generate_markdown_results(result))

    with open('evaluation_score.txt', 'w') as f:
        f.write(str(result['score']))

    # Save submission data for PR creation (if score >= 2)
    if result['score'] >= 2 and submission.get('name') and submission.get('description') and submission.get('category'):
        submission_data = {
            'name': submission['name'],
            'url': url,
            'description': submission['description'],
            'category': submission['category'],
            'score': result['score'],
            'issue_number': issue_number,
        }
        with open('submission_data.json', 'w') as f:
            json.dump(submission_data, f, indent=2)
        print(f"Submission data saved for PR creation")

    print(f"Evaluation complete. Score: {result['score']}/3")


if __name__ == "__main__":
    main()
