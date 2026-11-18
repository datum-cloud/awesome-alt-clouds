/**
 * Client logic for /list/: category + tag + search filtering, provider sort,
 * list/grid view switch, faceted option counts, and URL sync.
 *
 * Rows (`#rows > tr`) and tiles (`#tiles > li`) are rendered in the same order,
 * so row i and tile i are the same cloud: the filter runs on row data and the
 * result is mirrored onto the tile at the same index.
 *
 * URL: ?category=<slug>&tags=<a,b>&search=<term>&sort=<asc|desc|recent>&view=<list|grid>
 * Multiple tags combine with AND (same as the pre-redesign directory).
 */

type Sort = "asc" | "desc" | "recent";
type View = "list" | "grid";

const VIEW_KEY = "altcloud:list-view";

function readStoredView(): View | null {
  try {
    const v = localStorage.getItem(VIEW_KEY);
    return v === "grid" || v === "list" ? v : null;
  } catch {
    return null;
  }
}

function storeView(view: View) {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    /* private mode / blocked storage: URL still carries the view */
  }
}

export function initListFilters() {
  const root = document.getElementById("listRoot");
  const rowsEl = document.getElementById("rows");
  const tilesEl = document.getElementById("tiles");
  const categorySelect = document.getElementById("categorySelect") as HTMLSelectElement | null;
  const tagToggle = document.getElementById("tagToggle") as HTMLButtonElement | null;
  const tagPanel = document.getElementById("tagPanel");
  const tagSummary = document.getElementById("tagSummary");
  const tagClear = document.getElementById("tagClear") as HTMLButtonElement | null;
  const searchInput = document.getElementById("searchInput") as HTMLInputElement | null;
  const sortBtn = document.getElementById("sortBtn");
  const sortHeader = document.getElementById("sortHeader");
  const emptyState = document.getElementById("emptyState");
  const resultCount = document.getElementById("resultCount");
  if (!root || !rowsEl || !tilesEl || !categorySelect || !tagPanel || !searchInput) return;
  const tagBoxes = Array.from(
    tagPanel.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')
  );
  const validTags = new Set(tagBoxes.map((b) => b.value));

  const rows = Array.from(rowsEl.children) as HTMLElement[];
  const tiles = Array.from(tilesEl.children) as HTMLElement[];
  const pairs = rows.map((row, i) => ({
    row,
    tile: tiles[i],
    name: row.dataset.name ?? "",
    desc: row.dataset.description ?? "",
    cats: (row.dataset.categories ?? "").split("|").filter(Boolean),
    tags: (row.dataset.tags ?? "").split("|").filter(Boolean),
    date: row.dataset.dateAdded ?? "",
  }));
  type Pair = (typeof pairs)[number];

  const categoryBySlug = new Map(
    Array.from(categorySelect.options)
      .filter((o) => o.value)
      .map((o) => [o.value, o.dataset.category ?? ""])
  );

  const state = {
    category: "", // display name, "" = all
    tags: new Set<string>(),
    search: "",
    sort: "asc" as Sort,
    view: "list" as View,
  };
  let appliedSort: Sort = "asc";

  const matchesSearch = (p: Pair, term: string) =>
    !term || p.name.includes(term) || p.desc.includes(term);
  const matchesTag = (p: Pair) => [...state.tags].every((t) => p.tags.includes(t));
  const matchesCat = (p: Pair) => !state.category || p.cats.includes(state.category);

  function compare(a: Pair, b: Pair): number {
    if (state.sort === "recent") {
      if (a.date === b.date) return a.name.localeCompare(b.name);
      if (!a.date) return 1;
      if (!b.date) return -1;
      return b.date.localeCompare(a.date);
    }
    const r = a.name.localeCompare(b.name);
    return state.sort === "desc" ? -r : r;
  }

  function apply() {
    const term = state.search.trim().toLowerCase();
    let visible = 0;
    for (const p of pairs) {
      const show = matchesCat(p) && matchesTag(p) && matchesSearch(p, term);
      p.row.hidden = !show;
      if (p.tile) p.tile.hidden = !show;
      if (show) visible++;
    }

    if (state.sort !== appliedSort) {
      const sorted = [...pairs].sort(compare);
      const rf = document.createDocumentFragment();
      const tf = document.createDocumentFragment();
      for (const p of sorted) {
        rf.appendChild(p.row);
        if (p.tile) tf.appendChild(p.tile);
      }
      rowsEl!.appendChild(rf);
      tilesEl!.appendChild(tf);
      appliedSort = state.sort;
    }

    if (emptyState) emptyState.hidden = visible > 0;
    if (resultCount) {
      resultCount.textContent =
        visible === pairs.length
          ? `${pairs.length} clouds`
          : `${visible} of ${pairs.length} clouds`;
    }
    refreshFacets(term);
  }

  /**
   * Faceted counts, as in the pre-redesign directory:
   * - Category option = clouds matching search + selected tags (category ignored), so it
   *   shows what you'd get by switching to it.
   * - Tag option = clouds in the current result set carrying that tag, i.e. what adding
   *   it would leave (tags AND together). Zero-result tags, and groups left empty,
   *   are hidden; checked tags always stay visible.
   */
  function refreshFacets(term: string) {
    const catCounts = new Map<string, number>();
    const tagCounts = new Map<string, number>();
    let catAll = 0;
    for (const p of pairs) {
      if (!matchesSearch(p, term)) continue;
      if (matchesTag(p)) {
        catAll++;
        for (const c of p.cats) catCounts.set(c, (catCounts.get(c) ?? 0) + 1);
      }
      if (matchesCat(p) && matchesTag(p)) {
        for (const t of p.tags) tagCounts.set(t, (tagCounts.get(t) ?? 0) + 1);
      }
    }
    for (const opt of Array.from(categorySelect!.options)) {
      const cat = opt.dataset.category;
      const n = cat ? (catCounts.get(cat) ?? 0) : catAll;
      opt.textContent = `${opt.dataset.label} (${n})`;
      opt.disabled = n === 0 && !opt.selected;
    }
    for (const box of tagBoxes) {
      const n = tagCounts.get(box.value) ?? 0;
      const option = box.closest<HTMLElement>("[data-tag-option]");
      const count = option?.querySelector<HTMLElement>("[data-tag-count]");
      if (count) count.textContent = String(n);
      // Like the old directory: hide tags that would leave nothing (never checked ones).
      if (option) option.hidden = n === 0 && !box.checked;
    }
    tagPanel!.querySelectorAll<HTMLElement>("fieldset").forEach((group) => {
      group.hidden = !group.querySelector("[data-tag-option]:not([hidden])");
    });
  }

  function setView(view: View, persist = true) {
    state.view = view;
    root!.dataset.view = view;
    root!.querySelectorAll<HTMLElement>("[data-view-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.viewPanel !== view;
    });
    root!.querySelectorAll<HTMLButtonElement>("[data-view-btn]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.dataset.viewBtn === view));
    });
    if (persist) storeView(view);
  }

  function syncTagUi() {
    for (const box of tagBoxes) box.checked = state.tags.has(box.value);
    const picked = tagBoxes.filter((b) => b.checked).map((b) => b.dataset.label ?? b.value);
    if (tagSummary) {
      tagSummary.textContent =
        picked.length === 0
          ? "Tags: All"
          : picked.length === 1
            ? `Tags: ${picked[0]}`
            : `Tags: ${picked[0]} +${picked.length - 1}`;
    }
    if (tagToggle) tagToggle.title = picked.join(", ");
    if (tagClear) tagClear.disabled = picked.length === 0;
  }

  function setTagPanelOpen(open: boolean) {
    tagPanel!.hidden = !open;
    tagToggle?.setAttribute("aria-expanded", String(open));
  }

  function syncSortUi() {
    if (!sortHeader) return;
    sortHeader.setAttribute(
      "aria-sort",
      state.sort === "asc" ? "ascending" : state.sort === "desc" ? "descending" : "none"
    );
  }

  function updateUrl() {
    const params = new URLSearchParams();
    const catSlug = categorySelect!.value;
    if (catSlug) params.set("category", catSlug);
    if (state.tags.size > 0) params.set("tags", [...state.tags].join(","));
    if (state.search) params.set("search", state.search);
    if (state.sort !== "asc") params.set("sort", state.sort);
    if (state.view !== "list") params.set("view", state.view);
    const qs = params.toString();
    history.replaceState(null, "", location.pathname + (qs ? `?${qs}` : ""));
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    // Legacy: category used to live in the hash (#workload-clouds).
    const catSlug = params.get("category") ?? location.hash.slice(1);
    state.category = categoryBySlug.get(catSlug) ?? "";
    categorySelect!.value = state.category ? catSlug : "";

    state.tags = new Set(
      (params.get("tags") ?? "")
        .split(",")
        .map((t) => t.trim())
        .filter((t) => validTags.has(t))
    );
    syncTagUi();

    state.search = params.get("search") ?? params.get("q") ?? "";
    searchInput!.value = state.search;

    const sort = params.get("sort");
    state.sort = sort === "desc" || sort === "recent" ? sort : "asc";

    const view = params.get("view");
    setView(view === "grid" || view === "list" ? view : (readStoredView() ?? "list"), false);
  }

  categorySelect.addEventListener("change", () => {
    state.category = categoryBySlug.get(categorySelect.value) ?? "";
    apply();
    updateUrl();
  });
  tagPanel.addEventListener("change", (e) => {
    const box = e.target as HTMLInputElement;
    if (box.type !== "checkbox") return;
    if (box.checked) state.tags.add(box.value);
    else state.tags.delete(box.value);
    syncTagUi();
    apply();
    updateUrl();
  });
  tagClear?.addEventListener("click", () => {
    state.tags.clear();
    syncTagUi();
    apply();
    updateUrl();
  });
  tagToggle?.addEventListener("click", () =>
    setTagPanelOpen(tagToggle.getAttribute("aria-expanded") !== "true")
  );
  // Close on Escape (focus back to the toggle) or a click outside the picker.
  tagPanel.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      setTagPanelOpen(false);
      tagToggle?.focus();
    }
  });
  tagToggle?.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setTagPanelOpen(false);
  });
  document.addEventListener("click", (e) => {
    if (!tagPanel.hidden && !(e.target as Element).closest("#tagPicker")) setTagPanelOpen(false);
  });

  let debounce: ReturnType<typeof setTimeout> | undefined;
  searchInput.addEventListener("input", () => {
    state.search = searchInput.value;
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      apply();
      updateUrl();
    }, 120);
  });

  sortBtn?.addEventListener("click", () => {
    state.sort = state.sort === "asc" ? "desc" : "asc";
    syncSortUi();
    apply();
    updateUrl();
  });

  root.querySelectorAll<HTMLButtonElement>("[data-view-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setView(btn.dataset.viewBtn === "grid" ? "grid" : "list");
      updateUrl();
    });
  });

  window.addEventListener("popstate", () => {
    readUrl();
    syncSortUi();
    apply();
  });

  readUrl();
  syncSortUi();
  apply();
  if (location.hash) updateUrl(); // normalise legacy #category into ?category=
}
