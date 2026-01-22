#!/usr/bin/env python3
"""
Alt-Clouds News Monitor
Runs daily to discover new cloud services across all categories
"""

import os
import json
import time
import anthropic
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CATEGORIES = {
    "Infrastructure Clouds": {
        "keywords": ["GPU cloud", "cloud compute", "inference API", "serverless GPU"],
        "description": "GPU and compute infrastructure providers"
    },
    "Sovereign Clouds": {
        "keywords": ["sovereign cloud", "data residency", "regional compliance cloud"],
        "description": "Cloud platforms with data sovereignty"
    },
    "Data Clouds": {
        "keywords": ["database cloud", "data warehouse", "analytics platform", "observability"],
        "description": "Data storage, processing, and observability"
    },
    "Workflow and Operations Clouds": {
        "keywords": ["workflow automation", "orchestration platform", "incident management"],
        "description": "Workflow automation and operations"
    },
    "Network, Connectivity and Security Clouds": {
        "keywords": ["CDN", "edge network", "zero trust", "API gateway", "VPN alternative"],
        "description": "Networking, security, and connectivity"
    },
    "Vibe Clouds": {
        "keywords": ["AI coding assistant", "LLM API", "AI development platform"],
        "description": "AI-powered creativity and development tools"
    },
    "Developer Happiness Clouds": {
        "keywords": ["PaaS", "deployment platform", "CI/CD", "developer tools cloud"],
        "description": "Developer platforms and tools"
    },
    "Authorization, Identity, Fraud and Abuse Clouds": {
        "keywords": ["authentication service", "identity platform", "fraud detection API"],
        "description": "Auth, identity, and fraud prevention"
    },
    "Monetization, Finance and Legal Clouds": {
        "keywords": ["billing platform", "usage metering", "subscription management API"],
        "description": "Billing, payments, and monetization"
    },
    "Customer, Marketing and eCommerce Clouds": {
        "keywords": ["CRM platform", "marketing automation", "ecommerce platform"],
        "description": "Customer engagement and commerce"
    },
    "IoT, Communications, and Media Clouds": {
        "keywords": ["IoT platform", "messaging API", "video platform", "SMS gateway"],
        "description": "IoT, communications, and media"
    },
    "Blockchain Clouds": {
        "keywords": ["blockchain infrastructure", "web3 cloud", "decentralized compute"],
        "description": "Blockchain-based infrastructure"
    },
    "Unikernels & WebAssembly": {
        "keywords": ["unikernel platform", "WebAssembly cloud", "wasm runtime"],
        "description": "Unikernel and WebAssembly platforms"
    },
    "Source Code Control": {
        "keywords": ["git hosting", "version control platform", "code repository"],
        "description": "Source code management"
    },
    "Cloud Adjacent": {
        "keywords": ["cloud tools", "cloud utilities", "infrastructure software"],
        "description": "Cloud-complementary tools and services"
    }
}


class AltCloudsMonitor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.findings = []
        
    def search_category(self, category: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for new services in a specific category using Claude with web search
        """
        print(f"🔍 Searching {category}...")
        
        # Calculate date range for "recent" news
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        # Construct the search prompt
        prompt = f"""Search for new cloud services and platforms launched in the past week in the "{category}" category.

Category description: {config['description']}
Keywords to focus on: {', '.join(config['keywords'])}

For each service you find:
1. Verify it's a real company/service (not just news about existing ones)
2. Get the company name and primary URL
3. Check if it appears to be a cloud/SaaS service
4. Get a brief description of what they offer

Return results as a JSON array with this format:
[
  {{
    "company_name": "Acme GPU Cloud",
    "url": "https://acmegpu.com",
    "description": "Brief description of the service",
    "found_via": "TechCrunch article about...",
    "category": "{category}"
  }}
]

Focus on NEW services (launched or announced in past 7 days).
If you don't find any new services, return an empty array [].
ONLY return the JSON array, no other text.
"""

        try:
            # Call Claude with web search enabled
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search"
                }],
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract the response
            results = []
            for block in response.content:
                if block.type == "text":
                    text = block.text.strip()
                    # Try to parse as JSON
                    if text.startswith('[') and text.endswith(']'):
                        try:
                            results = json.loads(text)
                        except json.JSONDecodeError:
                            print(f"⚠️  Failed to parse response as JSON for {category}")
                            continue
            
            print(f"✅ Found {len(results)} candidates in {category}")
            return results
            
        except anthropic.RateLimitError as e:
            print(f"⚠️  Rate limit hit for {category}, waiting 10 seconds...")
            time.sleep(10)
            # Retry once
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    tools=[{
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }],
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                results = []
                for block in response.content:
                    if block.type == "text":
                        text = block.text.strip()
                        if text.startswith('[') and text.endswith(']'):
                            try:
                                results = json.loads(text)
                            except json.JSONDecodeError:
                                pass
                print(f"✅ Found {len(results)} candidates in {category} (retry)")
                return results
            except Exception as retry_error:
                print(f"❌ Retry failed for {category}: {retry_error}")
                return []
        except Exception as e:
            print(f"❌ Error searching {category}: {e}")
            return []
    
    def deduplicate_against_existing(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove candidates that already exist in the awesome-alt-clouds list
        """
        # TODO: Load existing entries from README.md and filter
        # For now, just return all candidates
        return candidates
    
    def run_daily_monitor(self) -> Dict[str, Any]:
        """
        Run the daily monitoring across all categories
        """
        print("🚀 Starting daily alt-clouds monitoring...")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔍 Monitoring {len(CATEGORIES)} categories")
        print("-" * 60)
        
        all_candidates = []
        
        # Search each category with rate limiting
        for i, (category, config) in enumerate(CATEGORIES.items()):
            candidates = self.search_category(category, config)
            all_candidates.extend(candidates)
            
            # Rate limiting: wait between requests to avoid hitting API limits
            # 30k tokens/min limit = need ~2 second delay between calls
            if i < len(CATEGORIES) - 1:  # Don't sleep after last one
                print(f"⏱️  Rate limiting: waiting 3 seconds...")
                time.sleep(3)
        
        # Deduplicate
        unique_candidates = self.deduplicate_against_existing(all_candidates)
        
        # Save results
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_found": len(unique_candidates),
            "by_category": {},
            "candidates": unique_candidates
        }
        
        # Group by category
        for candidate in unique_candidates:
            cat = candidate.get("category", "Unknown")
            if cat not in output["by_category"]:
                output["by_category"][cat] = []
            output["by_category"][cat].append(candidate)
        
        # Save to file
        output_file = f"data/candidates/scan-{datetime.now().strftime('%Y%m%d')}.json"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print("-" * 60)
        print(f"✅ Monitoring complete!")
        print(f"📊 Total candidates found: {len(unique_candidates)}")
        print(f"💾 Results saved to: {output_file}")
        
        # Print summary by category
        if output["by_category"]:
            print("\n📋 Summary by category:")
            for cat, items in output["by_category"].items():
                print(f"   • {cat}: {len(items)}")
        
        return output


def main():
    """Main entry point"""
    if not ANTHROPIC_API_KEY:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        return 1
    
    monitor = AltCloudsMonitor()
    results = monitor.run_daily_monitor()
    
    # If candidates found, proceed to evaluation
    if results["total_found"] > 0:
        print(f"\n🎯 Next step: Evaluate {results['total_found']} candidates")
        print("   Run: python scripts/evaluate_candidates.py")
    else:
        print("\n💤 No new candidates found today")
    
    return 0


if __name__ == "__main__":
    exit(main())
