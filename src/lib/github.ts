export const GITHUB_OWNER = "datum-cloud";
export const GITHUB_REPO = "awesome-alt-clouds";

export const EMERGING_CATEGORY = "Emerging & Unverified Providers";

/**
 * Pre-filled "[Graduation] <Name>" issue link for a cloud currently listed
 * under Emerging & Unverified Providers. Mirrors the shape the Alt Cloud
 * browser extension already produces (see scripts/evaluate_graduation.py,
 * which parses the `**Service:**` field back out) so both entry points
 * feed the same bot pipeline.
 */
export function graduationIssueUrl(cloud: { name: string; url: string }): string {
  const title = `[Graduation] ${cloud.name}`;
  const body = `## Graduation Request

**Service:** [${cloud.name}](${cloud.url})

**Why they should graduate from Emerging & Unverified Providers to full listing:**


**Evidence of criteria now met:**


---
*Reported via the Alt Cloud website.*`;

  const params = new URLSearchParams({ title, body });
  return `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/issues/new?${params.toString()}`;
}
