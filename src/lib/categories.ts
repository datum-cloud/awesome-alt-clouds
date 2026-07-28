/**
 * Category taxonomy metadata for landing pages and SEO.
 * Keep in sync with `scripts/generate_llms.py:_CAT_DESCRIPTIONS` and
 * `scripts/evaluate_submission.py:CATEGORIES`.
 */
import { categoryToSlug, getCategories } from "./clouds";

export const DEFAULT_CAT_DESCRIPTION = "Cloud services in this category.";

export const categoryDescriptions: Record<string, string> = {
  "Infrastructure Clouds":
    'General-purpose cloud compute, bare metal, and VPS providers. The original "alt clouds" offering virtualized compute, dedicated servers, GPU instances, storage, and Kubernetes services outside the hyperscaler ecosystem.',
  "GPU & AI Compute Clouds":
    "Specialized GPU compute platforms for AI training, model fine-tuning, and high-performance workloads. Includes serverless GPU inference, GPU clusters, and distributed compute networks.",
  "Databases & Storage":
    "Managed database services, vector databases, distributed SQL, time series, object storage, and data warehousing — all self-service with public pricing.",
  "Developer Tooling & CI/CD":
    "CI/CD platforms, code hosting, testing infrastructure, feature flags, error monitoring, and developer workflow automation.",
  "Authorization, Identity & Fraud":
    "Authentication, authorization, identity management, secrets management, and fraud detection services with self-service onboarding.",
  "Observability & Monitoring":
    "Logging, metrics, tracing, APM, uptime monitoring, and error tracking platforms with pay-as-you-go or free tiers.",
  "AI Assistants & Copilots":
    "AI assistant platforms, copilot APIs, and conversational AI services for building customer-facing or developer-facing intelligent experiences.",
  "Network & Connectivity Clouds":
    "CDN, edge networking, DNS, DDoS protection, VPN, and private networking platforms.",
  "Monetization & Billing Clouds":
    "Payment processing, subscription management, usage-based billing, metering, and revenue operations platforms.",
  "Customer, Marketing & eCommerce":
    "CRM, customer support, marketing automation, and e-commerce infrastructure platforms.",
  "AI Coding & App Generation":
    "AI-assisted code generation, app scaffolding, and developer productivity tools built on LLMs.",
  "PaaS & Application Hosting":
    "Platform-as-a-service offerings for deploying web applications, APIs, and backend services with minimal infrastructure management.",
  "Security, Compliance & Sovereignty Clouds":
    "Security-focused cloud platforms with compliance certifications, data sovereignty options, air-gapped deployments, and sovereign cloud infrastructure.",
  "Communications, IoT & Media":
    "Messaging APIs, email delivery, SMS, voice, video, push notifications, and IoT connectivity platforms.",
  "Analytics & Data Warehousing":
    "Cloud data warehouses, analytics databases, business intelligence platforms, and data lakehouse services.",
  "Workflow & Operations Clouds":
    "Workflow orchestration, job queues, event streaming, and operations automation platforms.",
  "Data Integration & ETL":
    "Data pipeline, ETL, CDC, and integration platforms with self-service onboarding.",
  "AI Inference & Model APIs":
    "Hosted inference APIs for open-source and proprietary models, optimized for speed, cost, and scale.",
  "Unikernels & WebAssembly":
    "Edge computing, WebAssembly runtimes, and unikernel deployment platforms.",
  "Source Code Control": "Git hosting platforms with CI/CD integration and collaboration features.",
  "Cloud Adjacent & Infrastructure Tooling":
    "Tools and platforms that extend or manage cloud infrastructure without being cloud providers themselves.",
  "Decentralized & Web3 Compute": "Blockchain-based and decentralized compute platforms.",
  "Emerging & Unverified Providers":
    "Services that passed automated evaluation but have limited track record or are early-stage. Scored 🟡 (2/3 criteria). Included for discovery; verify independently before production use.",
};

export function getCategoryDescription(category: string): string {
  return categoryDescriptions[category] ?? DEFAULT_CAT_DESCRIPTION;
}

export function getCategoryBySlug(slug: string): string | undefined {
  return getCategories()
    .filter((cat) => cat !== "All")
    .find((cat) => categoryToSlug(cat) === slug);
}

export function getAllCategorySlugs(): string[] {
  return getCategories()
    .filter((cat) => cat !== "All")
    .map((cat) => categoryToSlug(cat));
}
