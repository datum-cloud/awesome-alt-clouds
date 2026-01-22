#!/usr/bin/env python3
"""
Candidate Evaluation Engine
Scores each candidate against the 3 alt-clouds criteria
"""

import os
import sys
import json
import anthropic
from typing import Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class EvaluationResult:
    """Structured evaluation result"""
    company_name: str
    url: str
    category: str
    score: int  # 0-3
    has_public_pricing: bool
    has_self_service: bool
    has_production_indicators: bool
    evidence: Dict[str, str]
    recommendation: str  # "accept", "review", "reject"
    reasoning: str
    description: str  # Generated description for README


class CandidateEvaluator:
    """Evaluates candidates against alt-clouds criteria"""
    
    CRITERIA_PROMPT = """You are evaluating a cloud service for inclusion in the awesome-alt-clouds list.

The service must meet these criteria:
1. **Transparent Public Pricing**: Has publicly visible pricing information
2. **Usage-Based Self-Service**: Offers usage-based model with self-service signup
3. **Production-Ready Indicators**: Has public SLA or status page

Company: {company_name}
URL: {url}
Category: {category}

Use web search to investigate:
1. Visit the company website and look for:
   - Pricing page (check /pricing, /plans, etc.)
   - Self-service signup (check if you can create account without sales call)
   - Status page (check /status, status.{domain}, etc.)
   - SLA or uptime guarantees

2. For each criterion, determine:
   - Does it meet the requirement? (true/false)
   - What's the evidence? (URL where you found it)

3. Calculate score:
   - Score 3: Meets all 3 criteria ✅✅✅
   - Score 2: Meets 2 criteria ✅✅❌
   - Score 1: Meets 1 criterion ✅❌❌
   - Score 0: Meets no criteria ❌❌❌

4. Recommendation:
   - Score 3: "accept" (auto-propose)
   - Score 2: "review" (needs human review)
   - Score 0-1: "reject" (doesn't qualify)

5. Generate a concise description (60-100 words) in the style of existing entries:
   - Focus on what makes them unique
   - Mention key features
   - Keep it technical but accessible

Return ONLY a JSON object:
{{
  "company_name": "{company_name}",
  "url": "{url}",
  "category": "{category}",
  "score": 0-3,
  "has_public_pricing": true/false,
  "has_self_service": true/false,
  "has_production_indicators": true/false,
  "evidence": {{
    "pricing_url": "URL or null",
    "signup_url": "URL or null",
    "status_page": "URL or null",
    "sla_doc": "URL or null"
  }},
  "recommendation": "accept|review|reject",
  "reasoning": "Brief explanation of the evaluation",
  "description": "Generated description for README"
}}
"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
    
    def evaluate_candidate(self, candidate: Dict[str, Any]) -> EvaluationResult:
        """
        Evaluate a single candidate against criteria
        """
        company_name = candidate.get("company_name", "Unknown")
        url = candidate.get("url", "")
        category = candidate.get("category", "Unknown")
        
        print(f"🔍 Evaluating: {company_name}")
        print(f"   URL: {url}")
        print(f"   Category: {category}")
        
        # Format the prompt
        prompt = self.CRITERIA_PROMPT.format(
            company_name=company_name,
            url=url,
            category=category
        )
        
        try:
            # Call Claude with web search
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
            
            # Extract JSON response
            result_json = None
            for block in response.content:
                if block.type == "text":
                    text = block.text.strip()
                    # Try to extract JSON
                    if '{' in text and '}' in text:
                        # Find JSON object
                        start = text.find('{')
                        end = text.rfind('}') + 1
                        json_str = text[start:end]
                        try:
                            result_json = json.loads(json_str)
                            break
                        except json.JSONDecodeError:
                            continue
            
            if not result_json:
                print(f"⚠️  Failed to parse evaluation response for {company_name}")
                # Return default "reject" result
                return EvaluationResult(
                    company_name=company_name,
                    url=url,
                    category=category,
                    score=0,
                    has_public_pricing=False,
                    has_self_service=False,
                    has_production_indicators=False,
                    evidence={},
                    recommendation="reject",
                    reasoning="Failed to evaluate - unable to parse response",
                    description=""
                )
            
            # Create EvaluationResult
            result = EvaluationResult(**result_json)
            
            # Print summary
            score_emoji = {
                3: "✅✅✅",
                2: "✅✅❌", 
                1: "✅❌❌",
                0: "❌❌❌"
            }
            print(f"   Score: {result.score}/3 {score_emoji.get(result.score, '')}")
            print(f"   Recommendation: {result.recommendation.upper()}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error evaluating {company_name}: {e}")
            return EvaluationResult(
                company_name=company_name,
                url=url,
                category=category,
                score=0,
                has_public_pricing=False,
                has_self_service=False,
                has_production_indicators=False,
                evidence={},
                recommendation="reject",
                reasoning=f"Evaluation error: {str(e)}",
                description=""
            )
    
    def evaluate_batch(self, candidates: List[Dict[str, Any]]) -> List[EvaluationResult]:
        """
        Evaluate a batch of candidates
        """
        print(f"🎯 Evaluating {len(candidates)} candidates...")
        print("-" * 60)
        
        results = []
        for i, candidate in enumerate(candidates, 1):
            print(f"\n[{i}/{len(candidates)}]")
            result = self.evaluate_candidate(candidate)
            results.append(result)
        
        print("\n" + "-" * 60)
        print(f"✅ Evaluation complete!")
        
        # Print summary
        accept_count = sum(1 for r in results if r.recommendation == "accept")
        review_count = sum(1 for r in results if r.recommendation == "review")
        reject_count = sum(1 for r in results if r.recommendation == "reject")
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Accept: {accept_count}")
        print(f"   👀 Review: {review_count}")
        print(f"   ❌ Reject: {reject_count}")
        
        return results


def save_evaluations(results: List[EvaluationResult], output_file: str):
    """Save evaluation results to JSON file"""
    output_data = {
        "evaluated_at": "2025-01-20T00:00:00Z",
        "total": len(results),
        "summary": {
            "accept": sum(1 for r in results if r.recommendation == "accept"),
            "review": sum(1 for r in results if r.recommendation == "review"),
            "reject": sum(1 for r in results if r.recommendation == "reject")
        },
        "results": [asdict(r) for r in results]
    }
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")


def main():
    """Main entry point"""
    import sys
    from datetime import datetime
    from pathlib import Path
    
    # Auto-find latest scan file or use provided file
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    else:
        # Auto-find latest scan file
        candidates_dir = Path('data/candidates')
        if not candidates_dir.exists():
            print("❌ No candidates directory found. Run monitor_news.py first.")
            return 1
        
        scan_files = sorted(candidates_dir.glob('scan-*.json'))
        if not scan_files:
            print("❌ No scan files found. Run monitor_news.py first.")
            return 1
        
        input_file = str(scan_files[-1])
        print(f"📂 Auto-selected latest scan: {input_file}")
    
    # Load candidates
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
            candidates = data.get("candidates", [])
    except Exception as e:
        print(f"❌ Error loading candidates: {e}")
        return 1
    
    if not candidates:
        print("No candidates to evaluate")
        return 0
    
    # Evaluate
    evaluator = CandidateEvaluator()
    results = evaluator.evaluate_batch(candidates)
    
    # Save results
    output_file = f"data/evaluations/eval-{datetime.now().strftime('%Y%m%d')}.json"
    save_evaluations(results, output_file)
    
    # Next steps
    accept_count = sum(1 for r in results if r.recommendation == "accept")
    review_count = sum(1 for r in results if r.recommendation == "review")
    
    if accept_count > 0 or review_count > 0:
        print(f"\n🎯 Next step: Create GitHub issues for review")
        print(f"   Run: python scripts/create_issues.py {output_file}")
    
    return 0


if __name__ == "__main__":
    exit(main())
