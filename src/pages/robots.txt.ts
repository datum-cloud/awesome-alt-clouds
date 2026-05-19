import type { APIRoute } from "astro";
import { blockSearchBots } from "../lib/site";

export const GET: APIRoute = () => {
  const body = blockSearchBots
    ? [
        "# Preview deploy — block all crawlers (site.config.mjs)",
        "User-agent: *",
        "Disallow: /",
        "",
      ].join("\n")
    : ["User-agent: *", "Allow: /", ""].join("\n");

  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
