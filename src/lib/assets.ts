/** Root-relative URL with Astro `base` (e.g. GitHub Pages project subpath). */
export function asset(path: string): string {
  const normalized = path.startsWith("/") ? path.slice(1) : path;
  return `${import.meta.env.BASE_URL}${normalized}`;
}
