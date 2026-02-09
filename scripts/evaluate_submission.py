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

import json
import os
import re
import sys
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# Categories available in the awesome list
CATEGORIES = [
    "Infrastructure Clouds",
    "Sovereign Clouds",
    "Unikernels & WebAssembly",
    "Data Clouds",
    "Workflow and Operations Clouds",
    "Network, Connectivity and Security Clouds",
    "Vibe Clouds",
    "Developer Happiness Clouds",
    "Authorization, Identity, Fraud and Abuse Clouds",
    "Monetization, Finance and Legal Clouds",
    "Customer, Marketing and eCommerce Clouds",
    "IoT, Communications, and Media Clouds",
    "Blockchain Clouds",
    "Source Code Control",
    "Cloud Adjacent",
    "Future Clouds",
]


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


def extract_urls_from_issue(issue_body):
    """Extract all submitted URLs from the issue body"""
    urls = []

    # Look for numbered list format: 1. https://...
    numbered_matches = re.findall(r'^\d+\.\s*(https?://[^\s]+)', issue_body, re.MULTILINE)
    if numbered_matches:
        urls.extend(numbered_matches)

    # Fallback: Look for **URL:** pattern (single URL format)
    if not urls:
        match = re.search(r'\*\*URL:\*\*\s*(https?://[^\s]+)', issue_body)
        if match:
            urls.append(match.group(1).strip())

    # Last fallback: find any URLs
    if not urls:
        urls = re.findall(r'https?://[^\s\)]+', issue_body)

    # Clean and deduplicate
    cleaned_urls = []
    seen = set()
    for url in urls:
        url = url.strip().rstrip('.,;:')
        if url not in seen and 'github.com' not in url:
            seen.add(url)
            cleaned_urls.append(url)

    return cleaned_urls[:5]  # Max 5 URLs


def fetch_page(url, timeout=15, retries=2):
    """Fetch a page and return soup, handling Cloudflare and other protections"""
    # Headers that mimic a real browser to bypass basic bot detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # Check if we got a Cloudflare challenge page
            if 'cloudflare' in response.text.lower() and 'challenge' in response.text.lower():
                print(f"Cloudflare challenge detected for {url}")
                if attempt < retries:
                    print(f"Retrying... ({attempt + 1}/{retries})")
                    continue
                return None, None

            return BeautifulSoup(response.text, 'html.parser'), response.url

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"Access denied (403) for {url} - likely Cloudflare protected")
            else:
                print(f"HTTP error fetching {url}: {e}")
        except requests.exceptions.Timeout:
            print(f"Timeout fetching {url}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

        if attempt < retries:
            print(f"Retrying... ({attempt + 1}/{retries})")

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


def generate_metadata_with_claude(url, page_content=None):
    """Use Claude API to generate name, description, and category"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set, skipping AI metadata generation")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

        # Build prompt based on whether we have page content
        if page_content and len(page_content.strip()) > 100:
            truncated_content = page_content[:15000]
            prompt = f"""Analyze this cloud service website and provide metadata for an awesome list entry.

URL: {url}

Page content:
{truncated_content}

Based on the website content, provide:
1. **Name**: The official service/company name (short, no taglines)
2. **Description**: A concise description (max 200 characters) of what the service does, written in third person, starting with a verb like "Provides", "Offers", "Delivers", etc.
3. **Category**: The most appropriate category from this list:
{categories_list}

Respond in this exact JSON format only, no other text:
{{"name": "Service Name", "description": "Description here under 200 chars.", "category": "Category Name"}}"""
        else:
            # Fallback: Ask Claude to use its knowledge (for Cloudflare-blocked sites)
            prompt = f"""I need metadata for a cloud service submission, but I couldn't fetch the website content (likely Cloudflare protected).

URL: {url}

Based on your knowledge of this service (from the URL/domain), provide:
1. **Name**: The official service/company name (short, no taglines)
2. **Description**: A concise description (max 200 characters) of what the service does, written in third person, starting with a verb like "Provides", "Offers", "Delivers", etc.
3. **Category**: The most appropriate category from this list:
{categories_list}

If you don't recognize this service, make a reasonable guess based on the domain name.

Respond in this exact JSON format only, no other text:
{{"name": "Service Name", "description": "Description here under 200 chars.", "category": "Category Name"}}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text.strip()

        # Parse JSON from response
        # Handle case where response might have markdown code blocks
        if "```" in response_text:
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)

        metadata = json.loads(response_text)

        # Validate category
        if metadata.get('category') not in CATEGORIES:
            print(f"Warning: Invalid category '{metadata.get('category')}', defaulting to Infrastructure Clouds")
            metadata['category'] = "Infrastructure Clouds"

        # Truncate description if too long
        if len(metadata.get('description', '')) > 200:
            metadata['description'] = metadata['description'][:197] + "..."

        print(f"Claude generated metadata: {metadata}")
        return metadata

    except Exception as e:
        print(f"Error calling Claude API: {e}")
        return None


def evaluate_service(url):
    """Evaluate a service against all 3 criteria"""
    print(f"Evaluating: {url}")

    soup, final_url = fetch_page(url)

    if not soup:
        # Could not fetch - likely Cloudflare protected
        # Return special result that allows Claude fallback
        return {
            'url': url,
            'company_name': extract_company_name(url, None),
            'score': 2,  # Allow PR creation with manual review
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': None, 'evidence': 'Could not verify (site protected)'},
                {'name': 'Usage-based Self-Service', 'passed': None, 'evidence': 'Could not verify (site protected)'},
                {'name': 'Production Indicators', 'passed': None, 'evidence': 'Could not verify (site protected)'},
            ],
            'fetch_failed': True,
            'needs_manual_review': True,
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
        'fetch_failed': False,
    }


def generate_single_result_markdown(result, ai_metadata=None):
    """Generate markdown for a single service result"""
    score = result['score']
    fetch_failed = result.get('fetch_failed', False)
    needs_manual = result.get('needs_manual_review', False)

    if fetch_failed:
        status = "Needs Manual Review"
        emoji = "orange_circle"
    elif score == 3:
        status = "Ready to Merge"
        emoji = "green_circle"
    elif score == 2:
        status = "Needs Review"
        emoji = "yellow_circle"
    else:
        status = "Does Not Meet Criteria"
        emoji = "red_circle"

    md = f"""### {result['company_name']}

**URL:** {result['url']}
**Score:** {score}/3 :{emoji}: {status}
"""

    if fetch_failed:
        md += "\n:warning: **Could not fetch website** (likely Cloudflare protected). Criteria could not be verified automatically.\n\n"

    md += """
| Criteria | Status | Evidence |
|----------|--------|----------|
"""

    for c in result['criteria']:
        if c['passed'] is None:
            status_icon = ":grey_question:"
        elif c['passed']:
            status_icon = ":white_check_mark:"
        else:
            status_icon = ":x:"
        md += f"| {c['name']} | {status_icon} | {c['evidence']} |\n"

    if ai_metadata:
        md += f"""
**AI-Generated Entry:**
- **Name:** {ai_metadata['name']}
- **Description:** {ai_metadata['description']}
- **Category:** {ai_metadata['category']}

"""
        if needs_manual:
            md += ":warning: Will be included in PR but **requires manual verification** of criteria\n"
        else:
            md += ":white_check_mark: Will be included in PR\n"
    elif score >= 2:
        md += "\n:warning: Could not generate AI metadata\n"
    else:
        md += "\n:x: Does not meet minimum criteria (2/3)\n"

    return md


def generate_markdown_results(results_list):
    """Generate markdown formatted results for multiple services"""
    passed = [r for r in results_list if r['score'] >= 2 and r.get('ai_metadata')]
    failed = [r for r in results_list if r['score'] < 2 or not r.get('ai_metadata')]

    md = f"""## Evaluation Results

**Total Submitted:** {len(results_list)}
**Passed (2/3+):** {len(passed)}
**Failed:** {len(failed)}

---

"""

    for result in results_list:
        md += generate_single_result_markdown(result, result.get('ai_metadata'))
        md += "\n---\n\n"

    if passed:
        md += """
## Next Steps

:rocket: **A Pull Request will be automatically created to add the passing services to the README.**

"""
    else:
        md += """
## Next Steps

No services passed the evaluation criteria. Please review and resubmit.
"""

    md += "\n*Evaluated automatically by the Awesome Alt Clouds bot*"

    return md


def main():
    # Get issue body from environment
    issue_body = os.environ.get('ISSUE_BODY', '')
    issue_number = os.environ.get('ISSUE_NUMBER', '')

    # Check for admin override
    admin_approved = os.environ.get('ADMIN_APPROVED', '').lower() == 'true'
    admin_score_override = os.environ.get('ADMIN_SCORE_OVERRIDE', '')

    if admin_approved:
        print("=== ADMIN APPROVAL MODE ===")
        if admin_score_override:
            print(f"Score override: {admin_score_override}")

    if not issue_body:
        print("Error: ISSUE_BODY environment variable not set")
        sys.exit(1)

    # Extract URLs from issue
    urls = extract_urls_from_issue(issue_body)

    if not urls:
        # Write error results
        with open('evaluation_results.md', 'w') as f:
            f.write("## Evaluation Error\n\nCould not extract any URLs from submission. Please ensure URLs are properly formatted.")
        with open('evaluation_score.txt', 'w') as f:
            f.write('0')
        sys.exit(0)

    print(f"Found {len(urls)} URL(s) to evaluate")

    # Evaluate each URL
    results_list = []
    passing_services = []

    for url in urls:
        print(f"\n--- Evaluating: {url} ---")

        # Fetch page content
        soup, final_url = fetch_page(url)
        page_content = soup.get_text()[:20000] if soup else ""

        # Evaluate against criteria
        result = evaluate_service(url)

        # Apply admin score override if provided
        if admin_approved and admin_score_override:
            original_score = result['score']
            result['score'] = int(admin_score_override)
            result['admin_override'] = True
            print(f"Admin override: {original_score}/3 -> {result['score']}/3")

        # Determine if service should pass
        # In admin mode: always pass (admin explicitly approved)
        # In normal mode: pass if score >= 2
        should_pass = admin_approved or result['score'] >= 2

        if should_pass:
            ai_metadata = generate_metadata_with_claude(url, page_content)
            if ai_metadata:
                result['company_name'] = ai_metadata['name']
                result['ai_metadata'] = ai_metadata
                passing_services.append({
                    'name': ai_metadata['name'],
                    'url': url,
                    'description': ai_metadata['description'],
                    'category': ai_metadata['category'],
                    'score': result['score'],
                    'needs_manual_review': False if admin_approved else result.get('needs_manual_review', False),
                    'admin_approved': admin_approved,
                })

        results_list.append(result)
        print(f"Score: {result['score']}/3")

    # Calculate max score for labeling
    max_score = max(r['score'] for r in results_list) if results_list else 0

    # Write results (only in non-admin mode to avoid duplicate comments)
    if not admin_approved:
        with open('evaluation_results.md', 'w') as f:
            f.write(generate_markdown_results(results_list))

    with open('evaluation_score.txt', 'w') as f:
        f.write(str(max_score))

    # Save submission data for PR creation (if any services passed)
    if passing_services:
        submission_data = {
            'services': passing_services,
            'issue_number': issue_number,
        }
        with open('submission_data.json', 'w') as f:
            json.dump(submission_data, f, indent=2)
        print(f"\n{len(passing_services)} service(s) saved for PR creation")

    print(f"\nEvaluation complete. {len(passing_services)}/{len(urls)} passed.")


if __name__ == "__main__":
    main()
