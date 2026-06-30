export interface ComparePickerName {
  slug: string;
  name: string;
}

export interface ComparePickerCloudMeta {
  name?: string;
  categories?: string[];
}

const MAX_RESULTS = 12;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getSlugInput(root: HTMLElement): HTMLInputElement | null {
  return root.querySelector<HTMLInputElement>(".compare-picker-slug");
}

function getTextInput(root: HTMLElement): HTMLInputElement | null {
  return root.querySelector<HTMLInputElement>(".compare-picker-input");
}

function getListbox(root: HTMLElement): HTMLUListElement | null {
  return root.querySelector<HTMLUListElement>(".compare-picker-listbox");
}

function getClearBtn(root: HTMLElement): HTMLButtonElement | null {
  return root.querySelector<HTMLButtonElement>(".compare-picker-clear");
}

export function getPickerSlugs(roots: HTMLElement[]): string[] {
  return roots.map((root) => getSlugInput(root)?.value ?? "").filter(Boolean);
}

export function setPickerSlugs(
  roots: HTMLElement[],
  slugs: string[],
  cloudMap: Record<string, { name: string }>
): void {
  roots.forEach((root, index) => {
    const slug = slugs[index] ?? "";
    const slugInput = getSlugInput(root);
    const textInput = getTextInput(root);
    const clearBtn = getClearBtn(root);
    if (!slugInput || !textInput) return;

    slugInput.value = slug;
    textInput.value = slug && cloudMap[slug] ? cloudMap[slug].name : "";
    if (clearBtn) {
      clearBtn.classList.toggle("hidden", !slug);
      clearBtn.classList.toggle("flex", Boolean(slug));
    }
  });
}

interface PickerState {
  activeIndex: number;
  currentMatches: ComparePickerName[];
}

export function initComparePickers(options: {
  roots: HTMLElement[];
  names: ComparePickerName[];
  cloudMap: Record<string, ComparePickerCloudMeta>;
  onChange: () => void;
}): void {
  const { roots, names, cloudMap, onChange } = options;
  const states = new Map<HTMLElement, PickerState>();

  function getOtherSelectedSlugs(currentRoot: HTMLElement): Set<string> {
    const selected = new Set<string>();
    for (const root of roots) {
      if (root === currentRoot) continue;
      const slug = getSlugInput(root)?.value;
      if (slug) selected.add(slug);
    }
    return selected;
  }

  function setClearVisible(root: HTMLElement, visible: boolean): void {
    const clearBtn = getClearBtn(root);
    if (!clearBtn) return;
    clearBtn.classList.toggle("hidden", !visible);
    clearBtn.classList.toggle("flex", visible);
  }

  function closeListbox(root: HTMLElement): void {
    const listbox = getListbox(root);
    const input = getTextInput(root);
    if (!listbox || !input) return;
    listbox.classList.add("hidden");
    listbox.innerHTML = "";
    input.setAttribute("aria-expanded", "false");
    states.set(root, { activeIndex: -1, currentMatches: [] });
  }

  function openListbox(root: HTMLElement): void {
    const listbox = getListbox(root);
    const input = getTextInput(root);
    if (!listbox || !input) return;
    listbox.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
  }

  function selectItem(root: HTMLElement, item: ComparePickerName): void {
    const slugInput = getSlugInput(root);
    const textInput = getTextInput(root);
    if (!slugInput || !textInput) return;

    slugInput.value = item.slug;
    textInput.value = item.name;
    setClearVisible(root, true);
    closeListbox(root);
    onChange();
  }

  function clearPicker(root: HTMLElement): void {
    const slugInput = getSlugInput(root);
    const textInput = getTextInput(root);
    if (!slugInput || !textInput) return;

    slugInput.value = "";
    textInput.value = "";
    setClearVisible(root, false);
    closeListbox(root);
    onChange();
  }

  function filterMatches(root: HTMLElement, term: string): ComparePickerName[] {
    const query = term.trim().toLowerCase();
    if (!query) return [];

    const taken = getOtherSelectedSlugs(root);
    return names
      .filter((item) => {
        if (taken.has(item.slug)) return false;
        const cloud = cloudMap[item.slug];
        const nameMatch = item.name.toLowerCase().includes(query);
        const catMatch = cloud?.categories?.some((cat) => cat.toLowerCase().includes(query));
        return nameMatch || catMatch;
      })
      .slice(0, MAX_RESULTS);
  }

  function highlightOption(root: HTMLElement, index: number): void {
    const listbox = getListbox(root);
    if (!listbox) return;
    const opts = listbox.querySelectorAll<HTMLElement>(".compare-picker-option");
    opts.forEach((opt, i) => {
      opt.classList.toggle("bg-cream", i === index);
      opt.setAttribute("aria-selected", i === index ? "true" : "false");
    });
    const state = states.get(root);
    if (state) state.activeIndex = index;
    const active = opts[index];
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  function renderListbox(root: HTMLElement, matches: ComparePickerName[]): void {
    const listbox = getListbox(root);
    if (!listbox) return;

    if (matches.length === 0) {
      listbox.innerHTML =
        '<li class="px-4 py-3 text-sm text-warm-stone">No matches</li>';
      openListbox(root);
      states.set(root, { activeIndex: -1, currentMatches: [] });
      return;
    }

    const items = matches
      .map((item, i) => {
        const cats = cloudMap[item.slug]?.categories?.join(" · ") ?? "";
        return `<li role="option" data-index="${i}" data-slug="${escapeHtml(item.slug)}" class="compare-picker-option cursor-pointer px-4 py-2.5 text-sm text-rich-earth hover:bg-cream transition-colors" aria-selected="false">
          <span class="block font-medium truncate">${escapeHtml(item.name)}</span>
          ${cats ? `<span class="block text-xs text-warm-stone truncate">${escapeHtml(cats)}</span>` : ""}
        </li>`;
      })
      .join("");

    listbox.innerHTML = items;
    openListbox(root);
    states.set(root, { activeIndex: -1, currentMatches: matches });
  }

  function runSearch(root: HTMLElement): void {
    const input = getTextInput(root);
    if (!input) return;

    const term = input.value;
    const slugInput = getSlugInput(root);
    const selectedSlug = slugInput?.value ?? "";
    if (selectedSlug && term === cloudMap[selectedSlug]?.name) {
      closeListbox(root);
      return;
    }

    if (term.trim().length === 0) {
      closeListbox(root);
      return;
    }

    const matches = filterMatches(root, term);
    renderListbox(root, matches);
  }

  roots.forEach((root) => {
    const input = getTextInput(root);
    const clearBtn = getClearBtn(root);
    const listbox = getListbox(root);
    if (!input || !listbox) return;

    states.set(root, { activeIndex: -1, currentMatches: [] });

    input.addEventListener("focus", () => {
      if (input.value.trim().length > 0) runSearch(root);
    });

    input.addEventListener("input", () => {
      const slugInput = getSlugInput(root);
      const hadSlug = Boolean(slugInput?.value);
      if (slugInput) slugInput.value = "";
      setClearVisible(root, false);
      if (hadSlug) onChange();
      runSearch(root);
    });

    clearBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      clearPicker(root);
      input.focus();
    });

    listbox.addEventListener("click", (e) => {
      const target = e.target as HTMLElement;
      const option = target.closest<HTMLElement>(".compare-picker-option");
      if (!option || option.classList.contains("compare-picker-option--disabled")) return;
      const slug = option.getAttribute("data-slug");
      const state = states.get(root);
      const match = state?.currentMatches.find((m) => m.slug === slug);
      if (match) selectItem(root, match);
    });

    input.addEventListener("keydown", (e) => {
      const state = states.get(root);
      const matches = state?.currentMatches ?? [];
      const activeIndex = state?.activeIndex ?? -1;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (matches.length === 0) return;
        const next = activeIndex < matches.length - 1 ? activeIndex + 1 : 0;
        highlightOption(root, next);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (matches.length === 0) return;
        const next = activeIndex > 0 ? activeIndex - 1 : matches.length - 1;
        highlightOption(root, next);
      } else if (e.key === "Enter") {
        if (activeIndex >= 0 && matches[activeIndex]) {
          e.preventDefault();
          selectItem(root, matches[activeIndex]);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        closeListbox(root);
        input.blur();
      }
    });
  });

  document.addEventListener("click", (e) => {
    const target = e.target as Node;
    for (const root of roots) {
      if (!root.contains(target)) closeListbox(root);
    }
  });
}
