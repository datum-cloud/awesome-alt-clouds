/** GitHub Pages project-site prefix (datum-cloud.github.io/awesome-alt-clouds/). */
const GITHUB_PAGES_PREFIX = "/awesome-alt-clouds/";

/** Runtime site root path — proxied www is `/`, direct GitHub Pages includes the subpath. */
export function clientBasePath(): string {
  const { pathname, hostname } = window.location;
  if (pathname.startsWith(GITHUB_PAGES_PREFIX) || hostname.endsWith("github.io")) {
    return GITHUB_PAGES_PREFIX;
  }
  return "/";
}
