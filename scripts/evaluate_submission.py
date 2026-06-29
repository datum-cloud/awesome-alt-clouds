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

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

QWEN_BASE_URL = os.environ.get("QWEN_BASE_URL")
QWEN_MODEL = "qwen3.6-35b-a3b"

# Set LLM_PROVIDER=qwen to use the self-hosted Qwen endpoint instead of Claude.
# Defaults to claude. Whichever provider is selected, the corresponding secret
# (ANTHROPIC_API_KEY or QWEN_BASE_URL) must be present.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "claude").lower()

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


def _jina_markdown_to_soup(markdown_text, base_url):
    """Convert Jina Reader markdown output into a BeautifulSoup object.

    Jina's default (markdown) mode executes JavaScript and returns rendered
    content, but as markdown — not HTML.  This helper extracts all markdown
    links and builds a minimal HTML document so that the existing
    ``find_link_matching`` / ``find_all('a')`` logic keeps working.
    """
    # Extract markdown links: [text](url)
    links = re.findall(r'\[([^\]]*)\]\((https?://[^)]+)\)', markdown_text)

    # Build minimal HTML with the extracted links + full text
    html_parts = ['<html><body>']
    for text, href in links:
        html_parts.append(f'<a href="{href}">{text}</a>')
    # Preserve full text so that get_text() searches (SLA, pricing indicators) work
    html_parts.append(f'<div>{markdown_text}</div>')
    html_parts.append('</body></html>')

    return BeautifulSoup('\n'.join(html_parts), 'html.parser')


def _soup_has_meaningful_content(soup):
    """Return True if the soup contains real rendered content, not just an SPA shell."""
    text = soup.get_text(strip=True)
    links = soup.find_all('a', href=True)
    # An empty SPA shell typically has very little visible text and no links.
    # A real page has substantial text (>200 chars) and at least one link.
    return len(text) > 200 and len(links) >= 1


def fetch_page_with_fallback(url, timeout=15, retries=2):
    """Try Jina Reader first (renders JS, bypasses CDN blocks), then requests as fallback.
    Returns (soup, final_url, fetch_method)."""
    jina_url = f"https://r.jina.ai/{url}"

    # Stage 1a: Jina Reader in default markdown mode — actually executes JavaScript
    # and returns rendered content.  HTML mode (X-Return-Format: html) returns the
    # raw HTML *before* JS execution, which is an empty shell for SPAs.
    try:
        md_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; awesome-alt-clouds-bot/1.0)',
            'Accept': 'text/plain',
        }
        response = requests.get(jina_url, headers=md_headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        if response.text and len(response.text) > 200:
            soup = _jina_markdown_to_soup(response.text, url)
            if _soup_has_meaningful_content(soup):
                return soup, url, "jina"
            else:
                print(f"Jina markdown response too thin for {url}, trying HTML mode")
    except Exception as e:
        print(f"Jina Reader (markdown) failed for {url}: {e}")

    # Stage 1b: Jina Reader in HTML mode — works well for static / server-rendered sites
    try:
        html_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; awesome-alt-clouds-bot/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'X-Return-Format': 'html',
        }
        response = requests.get(jina_url, headers=html_headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        if response.text and len(response.text) > 100:
            soup = BeautifulSoup(response.text, 'html.parser')
            if _soup_has_meaningful_content(soup):
                return soup, url, "jina"
            else:
                print(f"Jina HTML response is an empty SPA shell for {url}, falling back")
    except Exception as e:
        print(f"Jina Reader (HTML) failed for {url}: {e}")

    # Stage 2: direct requests scraper (cheaper but fails on JS-heavy / CDN-blocked sites)
    soup, final_url = fetch_page(url, timeout=timeout, retries=retries)
    if soup is not None:
        return soup, final_url, "requests"

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


def _probe_url(url, timeout=10):
    """Try to fetch a URL and return (soup, final_url) if it returns 200."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 200 and len(response.text) > 200:
            return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception:
        pass
    return None, None


def _check_pricing_indicators(soup):
    """Return True if the page contains pricing indicators."""
    text = soup.get_text().lower()
    price_indicators = [
        '$', '€', '£', '/month', '/mo', '/year', '/yr', '/hr',
        'per hour', 'per month', 'per year', 'free tier', 'free plan',
        'pay as you go', 'pay-as-you-go', 'usage-based',
    ]
    return any(indicator in text for indicator in price_indicators)


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
        if pricing_soup and _check_pricing_indicators(pricing_soup):
            result['passed'] = True
            result['evidence'] = f'Pricing page found at {final_url}'
            return result
        if pricing_soup:
            result['evidence'] = 'Pricing page exists but no clear pricing found'

    # Fallback: check if the homepage itself contains pricing indicators
    if soup and _check_pricing_indicators(soup):
        result['passed'] = True
        result['evidence'] = 'Pricing information found on homepage'
        return result

    # Fallback: probe common pricing URL patterns directly
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in ['/pricing', '/plans', '/price', '/#pricing', '/#plans']:
        probe_url = base + path
        probe_soup, probe_final = _probe_url(probe_url)
        if probe_soup and _check_pricing_indicators(probe_soup):
            result['passed'] = True
            result['evidence'] = f'Pricing page found at {probe_final}'
            return result

    return result


def _has_signup_indicators(soup):
    """Return True if the page contains signup/self-service indicators."""
    signup_patterns = [
        'signup', 'sign-up', 'sign up', 'register', 'get started',
        'start free', 'try free', 'try for free', 'create account',
        'start building', 'get started free', 'free trial', 'start trial',
        'sign in', 'log in', 'login', 'signin',
    ]

    # Check links and buttons
    for a in soup.find_all(['a', 'button']):
        text = a.get_text().lower().strip()
        href = a.get('href', '').lower()
        for pattern in signup_patterns:
            if pattern in text or pattern in href:
                return True

    # Check forms
    for form in soup.find_all('form'):
        form_text = form.get_text().lower()
        if any(p in form_text for p in ['email', 'sign up', 'register', 'password']):
            return True

    # Check full page text as last resort (for Jina markdown-converted pages)
    text = soup.get_text().lower()
    strong_signals = ['sign up', 'create account', 'start free trial', 'get started free', 'try for free']
    return any(signal in text for signal in strong_signals)


def check_self_service(soup, base_url):
    """Check for usage-based self-service signup"""
    result = {
        'name': 'Usage-based Self-Service',
        'passed': False,
        'evidence': 'No self-service signup found'
    }

    if not soup:
        return result

    if _has_signup_indicators(soup):
        result['passed'] = True
        result['evidence'] = 'Self-service signup available'
        return result

    # Fallback: probe common signup URL patterns
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in ['/signup', '/sign-up', '/register', '/login', '/signin']:
        probe_soup, probe_final = _probe_url(base + path)
        if probe_soup:
            # A 200 on a signup/login page is strong evidence
            result['passed'] = True
            result['evidence'] = f'Signup page found at {probe_final}'
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
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set, cannot generate AI metadata")
        return None

    print(f"Calling Claude API for {url}...")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
            model=CLAUDE_MODEL,
            max_tokens=1024,
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


def evaluate_with_claude(url):
    """Last-resort evaluation using Claude when both scrapers fail.

    Returns a dict with criteria, score, name, description, category,
    recommendation, and fetch_method='claude_websearch', or None on failure.
    """
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set, cannot use Claude fallback")
        return None

    print(f"Falling back to Claude for {url}...")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        domain = urlparse(url).netloc.replace('www.', '')
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

        prompt = f"""Evaluate this cloud service for an awesome list based on your knowledge.

URL: {url}
Domain: {domain}

Based on what you know about this service, assess these 3 criteria and provide evidence URLs where possible:
1. Transparent Public Pricing - public pricing page with actual prices shown
2. Usage-based Self-Service - can sign up and use without contacting sales
3. Production Indicators - public SLA or status page exists

Also provide:
- name: official service name (short, no taglines)
- description: what the service does (max 200 chars, start with "Provides", "Offers", "Delivers", etc.)
- category: best fit from this list:
{categories_list}
- recommendation: one sentence (e.g. "Pricing and status page found — looks legit" or "No SLA evidence found — review carefully")

If you cannot confirm a criterion, set passed to false and evidence to "Not found".

Respond in this exact JSON format only, no other text:
{{
  "criteria": [
    {{"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"}},
    {{"name": "Usage-based Self-Service", "passed": true, "evidence": "https://example.com/signup"}},
    {{"name": "Production Indicators", "passed": false, "evidence": "Not found"}}
  ],
  "name": "Service Name",
  "description": "Description under 200 chars.",
  "category": "Category Name",
  "recommendation": "One sentence recommendation"
}}"""

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()

        if not response_text:
            print(f"Claude returned no text for {url}")
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

        print(f"Claude fallback result: score={score}/3, name={data['name']}")
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
        print(f"Error in Claude fallback for {url}: {e}")
        return None


def generate_metadata_with_qwen(url, page_content=None):
    """Use Qwen API to generate name, description, and category"""
    if not QWEN_BASE_URL:
        print("ERROR: QWEN_BASE_URL not set, cannot generate AI metadata")
        return None

    print(f"Calling Qwen API for {url}...")

    try:
        from openai import OpenAI
        client = OpenAI(base_url=QWEN_BASE_URL, api_key="none")

        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

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

        message = client.chat.completions.create(
            model=QWEN_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )

        response_text = (message.choices[0].message.content or "").strip()
        response_text = re.sub(r'<think>[\s\S]*?</think>', '', response_text).strip()

        if "```" in response_text:
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)

        metadata = json.loads(response_text)

        if metadata.get('category') not in CATEGORIES:
            print(f"Warning: Invalid category '{metadata.get('category')}', defaulting to Infrastructure Clouds")
            metadata['category'] = "Infrastructure Clouds"

        if len(metadata.get('description', '')) > 200:
            metadata['description'] = metadata['description'][:197] + "..."

        print(f"Qwen generated metadata: {metadata}")
        return metadata

    except Exception as e:
        print(f"Error calling Qwen API: {e}")
        return None


def evaluate_with_qwen(url):
    """Last-resort evaluation using Qwen when both scrapers fail.

    Returns a dict with criteria, score, name, description, category,
    recommendation, and fetch_method='claude_websearch', or None on failure.
    """
    if not QWEN_BASE_URL:
        print("ERROR: QWEN_BASE_URL not set, cannot use Qwen fallback")
        return None

    print(f"Falling back to Qwen for {url}...")

    try:
        from openai import OpenAI
        client = OpenAI(base_url=QWEN_BASE_URL, api_key="none")

        domain = urlparse(url).netloc.replace('www.', '')
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

        prompt = f"""Evaluate this cloud service for an awesome list based on your knowledge.

URL: {url}
Domain: {domain}

Based on what you know about this service, assess these 3 criteria and provide evidence URLs where possible:
1. Transparent Public Pricing - public pricing page with actual prices shown
2. Usage-based Self-Service - can sign up and use without contacting sales
3. Production Indicators - public SLA or status page exists

Also provide:
- name: official service name (short, no taglines)
- description: what the service does (max 200 chars, start with "Provides", "Offers", "Delivers", etc.)
- category: best fit from this list:
{categories_list}
- recommendation: one sentence (e.g. "Pricing and status page found — looks legit" or "No SLA evidence found — review carefully")

If you cannot confirm a criterion, set passed to false and evidence to "Not found".

Respond in this exact JSON format only, no other text:
{{
  "criteria": [
    {{"name": "Transparent Public Pricing", "passed": true, "evidence": "https://example.com/pricing"}},
    {{"name": "Usage-based Self-Service", "passed": true, "evidence": "https://example.com/signup"}},
    {{"name": "Production Indicators", "passed": false, "evidence": "Not found"}}
  ],
  "name": "Service Name",
  "description": "Description under 200 chars.",
  "category": "Category Name",
  "recommendation": "One sentence recommendation"
}}"""

        message = client.chat.completions.create(
            model=QWEN_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        )

        response_text = (message.choices[0].message.content or "").strip()
        response_text = re.sub(r'<think>[\s\S]*?</think>', '', response_text).strip()

        if not response_text:
            print(f"Qwen returned no text for {url}")
            return None

        if "```" in response_text:
            json_match = re.search(r'\{[\s\S]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)

        data = json.loads(response_text)

        score = sum(1 for c in data.get('criteria', []) if c.get('passed'))
        if data.get('category') not in CATEGORIES:
            print(f"Warning: invalid category '{data.get('category')}', defaulting")
            data['category'] = "Infrastructure Clouds"
        if len(data.get('description', '')) > 200:
            data['description'] = data['description'][:197] + "..."

        print(f"Qwen fallback result: score={score}/3, name={data['name']}")
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
        print(f"Error in Qwen fallback for {url}: {e}")
        return None


def generate_metadata(url, page_content=None):
    """Dispatch to the provider selected by LLM_PROVIDER."""
    if LLM_PROVIDER == "qwen":
        return generate_metadata_with_qwen(url, page_content)
    return generate_metadata_with_claude(url, page_content)


def evaluate_with_llm(url):
    """Dispatch last-resort LLM evaluation to the provider selected by LLM_PROVIDER."""
    if LLM_PROVIDER == "qwen":
        return evaluate_with_qwen(url)
    return evaluate_with_claude(url)


def evaluate_service(url):
    """Evaluate a service against all 3 criteria using the fetch cascade."""
    print(f"Evaluating: {url}")

    soup, final_url, fetch_method = fetch_page_with_fallback(url)

    if fetch_method is None:
        # Both scrapers failed — try LLM fallback as last resort
        ws_result = evaluate_with_llm(url)
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
                ai_metadata = generate_metadata(url, page_content)
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
                    print(f"Warning: Claude metadata call failed, using fallback for {fallback_name}")
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
