import type { Pubkey } from "./types";

/**
 * Display-only npub abbreviation. Real bech32 lands with a nostr lib;
 * until then this produces a recognizable "npub1xxxx…xxxx" from hex.
 */
export function shortNpub(pubkey: Pubkey): string {
  return `npub1${pubkey.slice(0, 5)}…${pubkey.slice(-4)}`;
}

/** Display-only full fake npub (real bech32 lands with a nostr lib). */
export function fullNpub(pubkey: Pubkey): string {
  return `npub1${pubkey.slice(0, 58)}`;
}

export function relativeTime(d: Date): string {
  const mins = Math.round((Date.now() - d.getTime()) / 60_000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} h`;
  if (hours < 48) return "yesterday";
  const daysAgo = Math.round(hours / 24);
  if (daysAgo < 30) return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short" });
}

export function gigabytes(bytes: number): string {
  return `${Math.round((bytes / 1024 ** 3) * 10) / 10}`;
}
