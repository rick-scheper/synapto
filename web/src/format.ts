// Display helpers shared by the pages.

import type { Difficulty } from "./api";

/** "2026-10-03T11:20:00+02:00" -> "3 Oct 2026" */
export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const difficultyLabel = (d: Difficulty) => capitalise(d);

/** The last folder of a repo path: "/home/me/code/pointtools" -> "pointtools". */
export const repoName = (path: string) => path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path;

export const shortCommit = (sha: string | null) => (sha ? sha.slice(0, 7) : null);

export const plural = (n: number, word: string, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;

/** "just now", "4 min ago", "2 h ago", else the date. */
export const timeAgo = (iso: string, now = Date.now()) => {
  const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`;
  return formatDate(iso);
};
