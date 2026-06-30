export const COMPARE_STORAGE_KEY = "aac:compare";
export const COMPARE_CHANGE_EVENT = "aac:compare-change";
export const MAX_COMPARE_ITEMS = 3;

export interface CompareItem {
  slug: string;
  name: string;
}

/** In-memory fallback when localStorage is unavailable (private mode, etc.). */
let memoryStore: CompareItem[] = [];
let useMemory = false;

function readRaw(): CompareItem[] {
  if (useMemory) return [...memoryStore];
  try {
    const raw = localStorage.getItem(COMPARE_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is CompareItem =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as CompareItem).slug === "string" &&
        typeof (item as CompareItem).name === "string"
    );
  } catch {
    useMemory = true;
    return [...memoryStore];
  }
}

function writeRaw(items: CompareItem[]): void {
  const trimmed = items.slice(0, MAX_COMPARE_ITEMS);
  if (useMemory) {
    memoryStore = trimmed;
    notifyChange();
    return;
  }
  try {
    if (trimmed.length === 0) {
      localStorage.removeItem(COMPARE_STORAGE_KEY);
    } else {
      localStorage.setItem(COMPARE_STORAGE_KEY, JSON.stringify(trimmed));
    }
    notifyChange();
  } catch {
    useMemory = true;
    memoryStore = trimmed;
    notifyChange();
  }
}

function notifyChange(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(COMPARE_CHANGE_EVENT));
}

export function getItems(): CompareItem[] {
  return readRaw();
}

export function has(slug: string): boolean {
  return readRaw().some((item) => item.slug === slug);
}

export function isFull(): boolean {
  return readRaw().length >= MAX_COMPARE_ITEMS;
}

export function add(item: CompareItem): boolean {
  const items = readRaw();
  if (items.some((i) => i.slug === item.slug)) return true;
  if (items.length >= MAX_COMPARE_ITEMS) return false;
  writeRaw([...items, item]);
  return true;
}

export function remove(slug: string): void {
  writeRaw(readRaw().filter((item) => item.slug !== slug));
}

export function toggle(item: CompareItem): boolean {
  if (has(item.slug)) {
    remove(item.slug);
    return true;
  }
  return add(item);
}

export function clear(): void {
  writeRaw([]);
}

export function setItems(items: CompareItem[]): void {
  const unique: CompareItem[] = [];
  for (const item of items) {
    if (!unique.some((i) => i.slug === item.slug)) {
      unique.push(item);
    }
    if (unique.length >= MAX_COMPARE_ITEMS) break;
  }
  writeRaw(unique);
}

export function getSlugs(): string[] {
  return getItems().map((item) => item.slug);
}

/** Call once on the client to sync tray across tabs. */
export function initCrossTabSync(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;

  const onStorage = (event: StorageEvent) => {
    if (event.key === COMPARE_STORAGE_KEY) onChange();
  };
  const onCustom = () => onChange();

  window.addEventListener("storage", onStorage);
  window.addEventListener(COMPARE_CHANGE_EVENT, onCustom);

  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(COMPARE_CHANGE_EVENT, onCustom);
  };
}
