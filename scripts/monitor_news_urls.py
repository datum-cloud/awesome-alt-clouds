#!/usr/bin/env python3
"""
Alt-Clouds News Monitor - URL-based version
Checks user-provided URLs for new cloud services (NO web search)
"""

import os
import json
import time
import anthropic
from datetime import datetime
from typing import List, Dict, Any

# Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


class URLBasedMonitor:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
    def analyze_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Fetch and analyze URL for cloud services
        """
        print(f"📄 Analyzing: {url}")
        
        prompt = f"""Analyze this page for NEW cloud/SaaS services announced or launched recently.

Extract any cloud services mentioned. For each one:
- Company name
- URL (if available)
- Brief description
- Suggested category: Infrastructure, Developer Tools, Data, Network/Security, Workflow, Auth, Finance, AI, IoT, Blockchain, WebAssembly, or Other

Return JSON array:
[{{"company_name": "...", "url": "...", "description": "...", "category": "..."}}]

If no cloud services found, return []. JSON only."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                tools=[{
                    "type": "web_fetch_20250305",
                    "name": "web_fetch",
                    "url": url
                }],
                messages=[{"role": "user", "content": prompt}]
            )
            
            results = []
            for block in response.content:
                if block.type == "text":
                    text = block.text.strip()
                    if text.startswith('['):
                        try:
                            results = json.loads(text)
                        except:
                            pass
            
            print(f"✅ Found {len(results)} candidates")
            return results
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    def run_monitor(self, urls: List[str]) -> Dict[str, Any]:
        """Run monitoring on provided URLs"""
        print("🚀 Starting URL-based monitoring...")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Checking {len(urls)} URLs")
        print("-" * 60)
        
        all_candidates = []
        
        for i, url in enumerate(urls):
            candidates = self.analyze_url(url)
            all_candidates.extend(candidates)
            
            if i < len(urls) - 1:
                print(f"⏱️  Waiting 3 seconds...")
                time.sleep(3)
        
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_found": len(all_candidates),
            "sources_checked": len(urls),
            "candidates": all_candidates
        }
        
        output_file = f"data/candidates/scan-{datetime.now().strftime('%Y%m%d')}.json"
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print("-" * 60)
        print(f"✅ Complete! Found {len(all_candidates)} candidates")
        print(f"💾 Saved to: {output_file}")
        
        return output


def main():
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set")
        return 1
    
    # Load URLs from config
    config_file = os.environ.get('URLS_CONFIG', 'config/news_sources.json')
    
    if not os.path.exists(config_file):
        print(f"❌ Config not found: {config_file}")
        print("\nCreate config/news_sources.json:")
        print("""{
  "urls": [
    "https://www.producthunt.com/topics/developer-tools",
    "https://news.ycombinator.com/",
    "https://techcrunch.com/category/startups/"
  ]
}""")
        return 1
    
    with open(config_file) as f:
        config = json.load(f)
        urls = config.get('urls', [])
    
    if not urls:
        print("❌ No URLs in config")
        return 1
    
    monitor = URLBasedMonitor()
    results = monitor.run_monitor(urls)
    
    if results["total_found"] > 0:
        print(f"\n🎯 Next: python scripts/evaluate_candidates.py")
    else:
        print("\n💤 No candidates found")
    
    return 0


if __name__ == "__main__":
    exit(main())
