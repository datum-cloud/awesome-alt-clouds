// Minimal static file server for the Datum Compute unikernel image.
//
// The image holds the prebuilt Astro output (dist/) and this file, nothing else.
// It runs under Bun (the unikernel root filesystem has no shell and no Node).
//
// - Listens on HOST (default "::"): Datum networks are IPv6 only, and an
//   IPv4-only socket starts but never answers.
// - Astro builds with `format: "directory"`, so /foo and /foo/ both map to
//   dist/foo/index.html.
// - Text responses (HTML, CSS, JS, JSON, ...) are compressed with brotli or gzip,
//   whichever the client accepts. The home page is ~1.5 MB of HTML, so this
//   matters. Compressed bodies are cached in memory: dist/ never changes while
//   the instance runs, so each file is compressed at most once per encoding.
// - Every response carries `Access-Control-Allow-Origin: *`, like GitHub Pages
//   does, so clouds.json and llms.txt stay readable from other origins.
// - No access control here: put basic auth on the load balancer instead
//   (`datumctl alb auth set`), so Envoy checks it at the edge.

import { join, normalize, extname, sep } from "node:path";
import { brotliCompressSync, constants as zlib } from "node:zlib";

const PORT = Number(process.env.PORT ?? 3000);
const HOST = process.env.HOST ?? "::";
const ROOT = join(import.meta.dir, "dist");

const COMPRESSIBLE = /^(text\/|application\/(json|javascript|xml|manifest\+json)|image\/svg\+xml)/;
const MIN_COMPRESS_BYTES = 1024;
/** Stop caching compressed bodies past this many bytes (the rootfs is in memory). */
const MAX_CACHE_BYTES = 64 * 1024 * 1024;

const CORS = { "Access-Control-Allow-Origin": "*" };

const CACHE_IMMUTABLE = "public, max-age=31536000, immutable";
const CACHE_HTML = "public, max-age=300";
const CACHE_OTHER = "public, max-age=3600";

// --- compression -----------------------------------------------------------

/** Pick "br", "gzip" or null from an Accept-Encoding header (q=0 means no). */
function pickEncoding(header) {
  const accepted = new Set();
  for (const part of (header ?? "").split(",")) {
    const [name, ...params] = part.trim().toLowerCase().split(";");
    const q = params.map((p) => p.trim()).find((p) => p.startsWith("q="));
    if (name && !(q && Number(q.slice(2)) === 0)) accepted.add(name);
  }
  if (accepted.has("br")) return "br";
  if (accepted.has("gzip")) return "gzip";
  return null;
}

const compressed = new Map(); // "<encoding>:<path>" -> Promise<Uint8Array>
let compressedBytes = 0;

function compress(encoding, key, bytes) {
  const cacheKey = `${encoding}:${key}`;
  const hit = compressed.get(cacheKey);
  if (hit) return hit;

  const result = Promise.resolve().then(() =>
    encoding === "br"
      ? brotliCompressSync(bytes, {
          params: { [zlib.BROTLI_PARAM_QUALITY]: 5, [zlib.BROTLI_PARAM_SIZE_HINT]: bytes.length },
        })
      : Bun.gzipSync(bytes, { level: 6 })
  );
  if (compressedBytes < MAX_CACHE_BYTES) {
    compressed.set(cacheKey, result);
    result.then((out) => {
      compressedBytes += out.length;
    });
  }
  return result;
}

// --- static files ----------------------------------------------------------

/** Resolve a request path to a file inside ROOT, or null. */
async function resolveFile(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  if (decoded.includes("\0")) return null;

  const target = normalize(join(ROOT, decoded));
  // Reject traversal outside dist/.
  if (target !== ROOT && !target.startsWith(ROOT + sep)) return null;

  const candidates = extname(target) ? [target] : [join(target, "index.html"), `${target}.html`];
  for (const candidate of candidates) {
    const file = Bun.file(candidate);
    if (await file.exists()) return { file, path: candidate };
  }
  return null;
}

const server = Bun.serve({
  port: PORT,
  hostname: HOST,
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/healthz") return new Response("ok\n");

    if (req.method !== "GET" && req.method !== "HEAD") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { ...CORS, Allow: "GET, HEAD" },
      });
    }

    const found = await resolveFile(url.pathname);
    if (!found) {
      const notFound = Bun.file(join(ROOT, "404.html"));
      if (await notFound.exists()) {
        return new Response(notFound, { status: 404, headers: CORS });
      }
      return new Response("Not Found\n", { status: 404, headers: CORS });
    }

    const { file, path } = found;
    const type = file.type;
    const isHtml = type.startsWith("text/html");
    const immutable = url.pathname.startsWith("/_astro/");
    const headers = {
      ...CORS,
      "Cache-Control": immutable ? CACHE_IMMUTABLE : isHtml ? CACHE_HTML : CACHE_OTHER,
    };

    const compressible = COMPRESSIBLE.test(type) && file.size >= MIN_COMPRESS_BYTES;
    if (!compressible) {
      return new Response(req.method === "HEAD" ? null : file, { headers });
    }

    headers.Vary = "Accept-Encoding";
    const encoding = pickEncoding(req.headers.get("accept-encoding"));
    if (!encoding) {
      return new Response(req.method === "HEAD" ? null : file, { headers });
    }

    const body = await compress(encoding, path, await file.bytes());
    headers["Content-Encoding"] = encoding;
    headers["Content-Type"] = type;
    headers["Content-Length"] = String(body.length);
    return new Response(req.method === "HEAD" ? null : body, { headers });
  },
});

console.log(`Started server: http://${server.hostname}:${server.port}`);
