#!/usr/bin/env python3
"""
Batch driver for profile generation.

Reads public/clouds.json, skips clouds that already have an MDX file,
calls generate_cloud_profile.py for up to BATCH_SIZE clouds, then writes
a summary report at backfill_summary.json.

Env vars:
  BATCH_SIZE          — max clouds to process (default: 20)
  CATEGORY_FILTER     — only process clouds in this category (optional, exact match)
  SCORE_FILTER        — only process clouds with this score: "2", "3", or "all" (default: "3")
  CONTENT_DIR         — path to MDX content dir (default: src/content/clouds)
  CLOUDS_JSON         — path to clouds.json (default: public/clouds.json)
  ANTHROPIC_API_KEY   — passed through to generate_cloud_profile
  DRY_RUN             — if "true", print slugs that would be processed; no API calls
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from lib.slugify import slugify


def load_clouds(clouds_json_path: str) -> list[dict]:
    with open(clouds_json_path) as f:
        return json.load(f)


def get_existing_slugs(content_dir: str) -> set[str]:
    p = Path(content_dir)
    if not p.exists():
        return set()
    return {f.stem for f in p.glob("*.mdx")}


def select_candidates(
    clouds: list[dict],
    existing_slugs: set[str],
    category_filter: str | None,
    score_filter: str,
    batch_size: int,
) -> list[dict]:
    """Filter clouds by score/category, skip ones with existing MDX, cap at batch_size."""
    candidates = []
    for cloud in clouds:
        slug = slugify(cloud["name"])
        if slug in existing_slugs:
            continue
        if score_filter != "all" and str(cloud.get("score", 0)) != score_filter:
            continue
        if category_filter:
            if not any(category_filter == cat for cat in cloud.get("categories", [])):
                continue
        candidates.append(cloud)
        if len(candidates) >= batch_size:
            break
    return candidates


def _run_generator(cloud: dict, output_path: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update({
        "CLOUD_NAME": cloud["name"],
        "CLOUD_URL": cloud["url"],
        "CLOUD_SCORE": str(cloud.get("score", 3)),
        "CLOUD_CATEGORIES": ",".join(cloud.get("categories", [])),
        "CLOUD_DESCRIPTION": cloud.get("description", ""),
        "OUTPUT_PATH": output_path,
        "DRY_RUN": "false",
    })
    return subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "generate_cloud_profile.py")],
        env=env,
        capture_output=True,
        text=True,
    )


def main():
    batch_size = int(os.environ.get("BATCH_SIZE", "20"))
    category_filter = os.environ.get("CATEGORY_FILTER", "").strip() or None
    score_filter = os.environ.get("SCORE_FILTER", "3")
    content_dir = os.environ.get("CONTENT_DIR", "src/content/clouds")
    clouds_json = os.environ.get("CLOUDS_JSON", "public/clouds.json")
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    clouds = load_clouds(clouds_json)
    existing_slugs = get_existing_slugs(content_dir)
    candidates = select_candidates(
        clouds, existing_slugs, category_filter, score_filter, batch_size
    )

    print(f"Total clouds:        {len(clouds)}")
    print(f"Already have MDX:    {len(existing_slugs)}")
    print(f"Candidates batch:    {len(candidates)} (cap {batch_size})")
    if category_filter:
        print(f"Category filter:     {category_filter}")
    print(f"Score filter:        {score_filter}")

    if dry_run:
        for c in candidates:
            print(f"  Would generate: {slugify(c['name'])} ({c['name']})")
        return

    reports: list[dict] = []
    failed: list[dict] = []

    for cloud in candidates:
        slug = slugify(cloud["name"])
        output_path = os.path.join(content_dir, f"{slug}.mdx")
        print(f"\n--- Generating: {cloud['name']} ({slug}) ---")

        result = _run_generator(cloud, output_path)
        print(result.stdout)

        if result.returncode != 0:
            print(f"FAILED: {result.stderr}")
            failed.append({
                "name": cloud["name"],
                "slug": slug,
                "error": result.stderr[-500:],
            })
            continue

        report_path = "profile_generation_report.json"
        if os.path.exists(report_path):
            with open(report_path) as f:
                reports.append(json.load(f))

    summary = {
        "total_attempted": len(candidates),
        "succeeded": len(reports),
        "failed": len(failed),
        "failed_details": failed,
        "reports": reports,
    }
    with open("backfill_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nBatch complete: {len(reports)} generated, {len(failed)} failed")
    if failed:
        print("Failed clouds:")
        for item in failed:
            print(f"  - {item['name']}: {item['error'][:100]}")


if __name__ == "__main__":
    main()
