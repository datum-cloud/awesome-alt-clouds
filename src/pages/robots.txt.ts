import { blockSearchBots } from "../lib/site";
import { absoluteUrl } from "../lib/site-urls";

/** Build-time endpoint — emits static dist/robots.txt on GitHub Pages. */
export async function GET() {
  const lines = blockSearchBots
    ? ["User-agent: *", "Disallow: /"]
    : ["User-agent: *", "Allow: /", "", `Sitemap: ${absoluteUrl("sitemap-index.xml")}`];

  return new Response(lines.join("\n") + "\n", {
    headers: { "Content-Type": "text/plain" },
  });
}
