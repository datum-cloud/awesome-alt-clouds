const svgAttrs =
  'width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"';

export const externalLinkIcon = `<svg ${svgAttrs}><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 17 17 7M7 7h10v10"/></svg>`;

export const visitLinkClassName =
  "inline-flex items-center gap-1 text-xs font-normal text-bright-tangerine hover:underline";

export function renderVisitLink(href: string): string {
  return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="${visitLinkClassName}"><span>Visit</span>${externalLinkIcon}</a>`;
}
