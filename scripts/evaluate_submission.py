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
    "GPU & AI Compute Clouds",
    "Security, Compliance & Sovereignty Clouds",
    "Unikernels & WebAssembly",
    "Databases & Storage",
    "Analytics & Data Warehousing",
    "Observability & Monitoring",
    "Data Integration & ETL",
    "Workflow & Operations Clouds",
    "Network & Connectivity Clouds",
    "AI Inference & Model APIs",
    "AI Assistants & Copilots",
    "AI Coding & App Generation",
    "PaaS & Application Hosting",
    "Developer Tooling & CI/CD",
    "Authorization, Identity & Fraud",
    "Monetization & Billing Clouds",
    "Customer, Marketing & eCommerce",
    "Communications, IoT & Media",
    "Decentralized & Web3 Compute",
    "Source Code Control",
    "Cloud Adjacent & Infrastructure Tooling",
    "Emerging & Unverified Providers",
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


def fetch_page_with_fallback(url, timeout=15, retries=2):
    """Try requests first, then Jina Reader. Returns (soup, final_url, fetch_method)."""
    # Stage 1: existing requests-based scraper
    soup, final_url = fetch_page(url, timeout=timeout, retries=retries)
    if soup is not None:
        return soup, final_url, "requests"

    # Stage 2: Jina Reader (handles JS-rendered pages)
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; awesome-alt-clouds-bot/1.0)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        response = requests.get(jina_url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        if response.text and len(response.text) > 100:
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup, url, "jina"
    except Exception as e:
        print(f"Jina Reader failed for {url}: {e}")

    return None, None, None


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
        print("ERROR: ANTHROPIC_API_KEY not set, cannot generate AI metadata")
        print("Available env vars:", [k for k in os.environ.keys() if 'KEY' in k or 'TOKEN' in k or 'SECRET' in k])
        return None

    print(f"Calling Claude API for {url}...")

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


def evaluate_with_claude_websearch(url):
    """Last-resort evaluation using Claude with web_search when both scrapers fail.

    Returns a dict with criteria, score, name, description, category,
    recommendation, and fetch_method='claude_websearch', or None on failure.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set, cannot use Claude web search")
        return None

    print(f"Falling back to Claude web search for {url}...")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        domain = urlparse(url).netloc.replace('www.', '')
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

        prompt = f"""Evaluate this cloud service for an awesome list. Use web search to find real evidence.

URL: {url}
Domain: {domain}

Search for (in this order):
1. "{domain} pricing" to find their pricing page URL
2. "status.{domain}" OR "{domain} status page" to find their status/uptime page
3. "{domain} sign up" OR "{domain} register" to find their self-service signup URL

Then assess these 3 criteria and provide the actual URLs you found as evidence:
1. Transparent Public Pricing - public pricing page with actual prices shown
2. Usage-based Self-Service - can sign up and use without contacting sales
3. Production Indicators - public SLA or status page exists

Also provide:
- name: official service name (short, no taglines)
- description: what the service does (max 200 chars, start with "Provides", "Offers", "Delivers", etc.)
- category: best fit from this list:
{categories_list}
- recommendation: one sentence (e.g. "Pricing and status page found — looks legit" or "No SLA evidence found — review carefully")

If you cannot find evidence for a criterion, set passed to false and evidence to "Not found via web search".

Respond in this exact JSON format only, no other text:
{{
  "criteria": [
    {{"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"}},
    {{"name": "Usage-based Self-Service", "passed": true, "evidence": "https://example.com/signup"}},
    {{"name": "Production Indicators", "passed": false, "evidence": "Not found via web search"}}
  ],
  "name": "Service Name",
  "description": "Description under 200 chars.",
  "category": "Category Name",
  "recommendation": "One sentence recommendation"
}}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from the last text block in the response
        response_text = next(
            (block.text for block in reversed(message.content) if hasattr(block, 'text')),
            ""
        ).strip()

        if not response_text:
            print(f"Claude web search returned no text for {url}")
            return None

        # Strip markdown code fences if present
        if "```" in response_text:
            json_match = re.search(r'\{[\s\S]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)

        data = json.loads(response_text)

        # Validate and normalise
        score = sum(1 for c in data.get('criteria', []) if c.get('passed'))
        if data.get('category') not in CATEGORIES:
            print(f"Warning: invalid category '{data.get('category')}', defaulting")
            data['category'] = "Infrastructure Clouds"
        if len(data.get('description', '')) > 200:
            data['description'] = data['description'][:197] + "..."

        print(f"Claude web search result: score={score}/3, name={data['name']}")
        return {
            'criteria': data['criteria'],
            'score': score,
            'name': data['name'],
            'description': data['description'],
            'category': data['category'],
            'recommendation': data.get('recommendation', ''),
            'fetch_method': 'claude_websearch',
        }

    except Exception as e:
        print(f"Error in Claude web search for {url}: {e}")
        return None


def evaluate_service(url):
    """Evaluate a service against all 3 criteria using the fetch cascade."""
    print(f"Evaluating: {url}")

    soup, final_url, fetch_method = fetch_page_with_fallback(url)

    if fetch_method is None:
        # Both scrapers failed — try Claude web search as last resort
        ws_result = evaluate_with_claude_websearch(url)
        if ws_result:
            return {
                'url': url,
                'company_name': ws_result['name'],
                'score': ws_result['score'],
                'criteria': ws_result['criteria'],
                'fetch_failed': False,
                'fetch_method': 'claude_websearch',
                'needs_manual_review': ws_result['score'] < 3,
                'ai_metadata': {
                    'name': ws_result['name'],
                    'description': ws_result['description'],
                    'category': ws_result['category'],
                },
                'recommendation': ws_result['recommendation'],
                'page_content': '',
            }
        # All three stages failed — preserve existing behaviour
        return {
            'url': url,
            'company_name': extract_company_name(url, None),
            'score': 2,
            'criteria': [
                {'name': 'Transparent Public Pricing', 'passed': None, 'evidence': 'Could not verify (site protected)'},
                {'name': 'Usage-based Self-Service',    'passed': None, 'evidence': 'Could not verify (site protected)'},
                {'name': 'Production Indicators',       'passed': None, 'evidence': 'Could not verify (site protected)'},
            ],
            'fetch_failed': True,
            'fetch_method': None,
            'needs_manual_review': True,
            'page_content': '',
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
        'fetch_method': fetch_method,
        'page_content': soup.get_text()[:20000],
    }


def generate_single_result_markdown(result, ai_metadata=None):
    """Generate markdown for a single service result"""
    score = result['score']
    fetch_failed = result.get('fetch_failed', False)
    needs_manual = result.get('needs_manual_review', False)
    fetch_method = result.get('fetch_method')
    recommendation = result.get('recommendation', '')

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

    web_search_badge = " *(verified via web search)*" if fetch_method == "claude_websearch" else ""

    md = f"""### {result['company_name']}

**URL:** {result['url']}
**Score:** {score}/3 :{emoji}: {status}{web_search_badge}
"""

    if fetch_method == "claude_websearch" and recommendation:
        md += f"\n> :mag: {recommendation}\n"

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

        evidence = c['evidence']
        # Render evidence as a clickable link if it's a URL
        if fetch_method == "claude_websearch" and evidence.startswith("http"):
            evidence = f"[{evidence}]({evidence})"

        md += f"| {c['name']} | {status_icon} | {evidence} |\n"

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
    admin_target_url = os.environ.get('ADMIN_TARGET_URL', 'all').strip()

    if admin_approved:
        print("=== ADMIN APPROVAL MODE ===")
        if admin_target_url and admin_target_url != 'all':
            print(f"Target URL: {admin_target_url}")
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

    # Filter URLs if admin specified a target
    if admin_approved and admin_target_url and admin_target_url.lower() != 'all':
        target = admin_target_url.lower()
        # Remove protocol if present for matching
        if target.startswith('http://') or target.startswith('https://'):
            target = urlparse(target).netloc
        # Remove www. prefix for matching
        target = target.replace('www.', '')

        filtered_urls = []
        for url in urls:
            url_domain = urlparse(url).netloc.replace('www.', '').lower()
            if target in url_domain or url_domain in target:
                filtered_urls.append(url)

        if filtered_urls:
            print(f"Admin targeting specific URL: {admin_target_url}")
            print(f"Matched URLs: {filtered_urls}")
            urls = filtered_urls
        else:
            print(f"ERROR: No URLs matched target '{admin_target_url}'")
            print(f"Available URLs: {urls}")
            with open('evaluation_results.md', 'w') as f:
                f.write(f"## Approval Error\n\nNo URLs matched target `{admin_target_url}`.\n\nAvailable URLs in this submission:\n")
                for u in urls:
                    f.write(f"- {u}\n")
            with open('evaluation_score.txt', 'w') as f:
                f.write('0')
            sys.exit(0)

    # Evaluate each URL
    results_list = []
    passing_services = []

    for url in urls:
        print(f"\n--- Evaluating: {url} ---")

        # Evaluate against criteria (fetch cascade is handled inside evaluate_service)
        result = evaluate_service(url)

        # Apply admin score override if provided
        if admin_approved and admin_score_override:
            original_score = result['score']
            result['score'] = int(admin_score_override)
            result['admin_override'] = True
            print(f"Admin override: {original_score}/3 -> {result['score']}/3")

        should_pass = admin_approved or result['score'] >= 2

        if should_pass:
            # Claude web search already generated metadata — use it directly
            if result.get('fetch_method') == 'claude_websearch' and result.get('ai_metadata'):
                ai_metadata = result['ai_metadata']
                result['company_name'] = ai_metadata['name']
                passing_services.append({
                    'name': ai_metadata['name'],
                    'url': url,
                    'description': ai_metadata['description'],
                    'category': ai_metadata['category'],
                    'score': result['score'],
                    'needs_manual_review': result.get('needs_manual_review', False),
                    'admin_approved': admin_approved,
                })
            else:
                # Scraped successfully — call Claude for metadata as before
                page_content = result.get('page_content', '')
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
                elif admin_approved:
                    fallback_name = result['company_name']
                    print(f"Warning: Claude API failed, using fallback for {fallback_name}")
                    passing_services.append({
                        'name': fallback_name,
                        'url': url,
                        'description': "Cloud service provider.",
                        'category': 'Infrastructure Clouds',
                        'score': result['score'],
                        'needs_manual_review': True,
                        'admin_approved': admin_approved,
                    })
                    result['ai_metadata'] = {
                        'name': fallback_name,
                        'description': 'Cloud service provider.',
                        'category': 'Infrastructure Clouds',
                        'fallback': True,
                    }

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
