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

export { logoUrl as faviconUrl } from "./clouds";
