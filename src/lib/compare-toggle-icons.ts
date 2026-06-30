export type CompareToggleState = "add" | "selected" | "full";

const svgAttrs =
  'width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"';

export const compareIconAdd = `<svg ${svgAttrs}><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"/></svg>`;

export const compareIconCheck = `<svg ${svgAttrs}><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>`;

export const compareIconDash = `<svg ${svgAttrs}><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 12h14"/></svg>`;

export function renderCompactCompareToggle(state: CompareToggleState): string {
  switch (state) {
    case "selected":
      return compareIconCheck;
    case "full":
      return compareIconDash;
    case "add":
      return compareIconAdd;
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

export function renderFullCompareToggle(state: CompareToggleState): string {
  switch (state) {
    case "selected":
      return `<span class="inline-flex items-center gap-1.5">${compareIconCheck}<span>In compare</span></span>`;
    case "full":
      return `<span>Full</span>`;
    case "add":
      return `<span class="inline-flex items-center gap-1.5"><span>Compare</span>${compareIconAdd}</span>`;
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

export function compareToggleState(
  selected: boolean,
  full: boolean
): CompareToggleState {
  if (selected) return "selected";
  if (full) return "full";
  return "add";
}
