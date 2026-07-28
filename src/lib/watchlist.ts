import watchlistData from "../../public/watchlist.json";

export interface WatchlistEntry {
  name: string;
  url: string;
  category: string;
  dateAdded: string;
  reasonNotQualifying: string;
  criteriaNeed: string;
  lastReviewed: string;
}

export const watchlist = watchlistData as WatchlistEntry[];

export function faviconUrl(url: string): string {
  try {
    const hostname = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=64`;
  } catch {
    return "";
  }
}
