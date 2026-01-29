#!/usr/bin/env python3
"""
Parse README.md and generate clouds.json for the frontend
Extracts: name, url, description, category, and score (from circles)
"""

import json
import re

def parse_readme(readme_path):
    """Parse README.md and extract all cloud services"""
    
    with open(readme_path, 'r') as f:
        content = f.read()
    
    clouds = []
    current_category = None
    
    for line in content.split('\n'):
        # Track current category
        if line.startswith('## ') and not line.startswith('## Contents') and not line.startswith('## Criteria'):
            current_category = line.replace('## ', '').strip()
            # Skip non-cloud categories
            if current_category in ['Contents', 'Criteria', 'Contributing', 'License']:
                current_category = None
            continue
        
        # Parse service entries: * 🟢 [Name](url) - Description
        match = re.match(r'^\s*\*\s*(🟢|🟡)?\s*\[([^\]]+)\]\(([^)]+)\)\s+-\s+(.+)$', line)
        
        if match and current_category:
            badge = match.group(1)
            name = match.group(2)
            url = match.group(3)
            description = match.group(4)
            
            # Determine score from badge
            if badge == '🟢':
                score = 3
            elif badge == '🟡':
                score = 2
            else:
                score = 3  # Default if no badge
            
            clouds.append({
                'name': name,
                'url': url,
                'description': description,
                'category': current_category,
                'score': score
            })
    
    return clouds


def generate_clouds_json(readme_path, output_path):
    """Generate clouds.json from README.md"""
    
    clouds = parse_readme(readme_path)
    
    # Write JSON
    with open(output_path, 'w') as f:
        json.dump(clouds, f, indent=2)
    
    # Print stats
    total = len(clouds)
    score_3 = sum(1 for c in clouds if c['score'] == 3)
    score_2 = sum(1 for c in clouds if c['score'] == 2)
    categories = len(set(c['category'] for c in clouds))
    
    print(f"✅ Generated {output_path}")
    print(f"\n📊 Statistics:")
    print(f"   Total services: {total}")
    print(f"   🟢 3/3 criteria: {score_3} ({score_3/total*100:.0f}%)")
    print(f"   🟡 2/3 criteria: {score_2} ({score_2/total*100:.0f}%)")
    print(f"   Categories: {categories}")
    
    return clouds


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python parse_readme_to_json.py <README.md> [clouds.json]")
        return 1
    
    readme_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'clouds.json'
    
    try:
        generate_clouds_json(readme_path, output_path)
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
