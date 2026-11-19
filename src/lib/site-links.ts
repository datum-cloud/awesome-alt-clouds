/** Shared navigation + outbound links for the site chrome (header, footer, promos). */
import { asset } from "./assets";

export type NavKey = "list" | "definitions" | "contribute" | "blog";

export const NAV_ITEMS: { key: NavKey; label: string; href: string }[] = [
  { key: "list", label: "The List", href: asset("list/") },
  { key: "definitions", label: "Definitions", href: asset("definitions/") },
  { key: "contribute", label: "Contribute", href: asset("submit/") },
  { key: "blog", label: "Blog", href: asset("blog/") },
];

export const REPO_URL = "https://github.com/datum-cloud/awesome-alt-clouds";
export const REPO_ISSUES_URL = `${REPO_URL}/issues/new/choose`;
export const DATUM_URL = "https://www.datum.net";

/** The Stack's newsletter picker (CTRL: AltCloud is one of the options). */
export const NEWSLETTER_URL = "https://www.thestack.technology/newsletters";

export const EXTENSION_LINKS = {
  chrome:
    "https://chromewebstore.google.com/detail/alt-cloud-checker/nijjhgdijgnlimemhdaghkhgiggofbin",
  firefox: "https://addons.mozilla.org/addon/alt-cloud-checker/",
};

export const LLMS_TXT = asset("llms.txt");
export const CLOUDS_JSON = asset("clouds.json");
