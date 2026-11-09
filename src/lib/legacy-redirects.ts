/**
 * Redirects for the 24-category taxonomy that the 5-cloud taxonomy replaced.
 * Each retired category page points at the new category now holding most of its entries
 * ("Emerging & Unverified" became a badge, so it points at the unverified filter).
 * `infrastructure-clouds` and `workload-clouds` kept their slugs, so they need no redirect.
 * Covered by tests/test_taxonomy_sync.py.
 */
export const legacyCategoryRedirects: Record<string, string> = {
  "/categories/gpu-ai-compute-clouds": "/categories/infrastructure-clouds/",
  "/categories/security-compliance-sovereignty-clouds": "/categories/service-clouds/",
  "/categories/unikernels-webassembly": "/categories/workload-clouds/",
  "/categories/databases-storage": "/categories/workload-clouds/",
  "/categories/analytics-data-warehousing": "/categories/workload-clouds/",
  "/categories/observability-monitoring": "/categories/workload-clouds/",
  "/categories/data-integration-etl": "/categories/workload-clouds/",
  "/categories/workflow-operations-clouds": "/categories/workload-clouds/",
  "/categories/network-connectivity-clouds": "/categories/infrastructure-clouds/",
  "/categories/ai-inference-model-apis": "/categories/workload-clouds/",
  "/categories/ai-assistants-copilots": "/categories/service-clouds/",
  "/categories/ai-coding-app-generation": "/categories/workload-clouds/",
  "/categories/paas-application-hosting": "/categories/workload-clouds/",
  "/categories/developer-tooling-ci-cd": "/categories/service-clouds/",
  "/categories/authorization-identity-fraud": "/categories/service-clouds/",
  "/categories/monetization-billing-clouds": "/categories/service-clouds/",
  "/categories/customer-marketing-ecommerce": "/categories/service-clouds/",
  "/categories/communications-iot-media": "/categories/service-clouds/",
  "/categories/decentralized-web3-compute": "/categories/infrastructure-clouds/",
  "/categories/source-code-control": "/categories/service-clouds/",
  "/categories/cloud-adjacent-infrastructure-tooling": "/categories/service-clouds/",
  "/categories/emerging-unverified-providers": "/?tags=unverified",
};
