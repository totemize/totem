/**
 * Domain model, aligned with the totem spec (totemd branch).
 *
 * - One keypair per node: the nostr identity IS the FIPS identity
 *   (spec 02-identity). A node is identified by its pubkey.
 * - Wire keys are hex per NIP-01; npub (bech32) is display-only
 *   (spec 07-conventions).
 * - Friends = mutual kind 3 follows; a "wants to peer" row is a node
 *   that follows us where we don't follow back yet.
 */

/** 64-char lowercase hex pubkey — the wire encoding. */
export type Pubkey = string;

export interface NodeInfo {
  pubkey: Pubkey;
  name: string; // NIP-11 name minus the "!Totem " marker prefix
  relayUrl: string; // ws:// endpoint of the node's relay
  picture?: string; // kind 0 picture URL
}

export type Health = "good" | "degraded" | "down";

/** Shape of totem.status.get's result, plus device vitals. */
export interface NodeStatus {
  /** False until an owner npub is on the daemon's allowlist (spec 06/10). */
  claimed: boolean;
  health: Health;
  batteryPct: number;
  batteryHoursLeft: number;
  storageUsedBytes: number;
  storageTotalBytes: number;
  relayEventCount: number;
  totemsMet: number;
  lastEncounter: Encounter | null;
  mesh: MeshState;
}

/** FIPS mesh state, part of totem.status.get. */
export interface MeshState {
  up: boolean;
  peersConnected: number;
  address: string; // .fips name on the overlay
}

/** One line of totemd's append-only encounter log. */
export interface EncounterLogEntry {
  peer: NodeInfo;
  at: Date;
  transport: Transport;
  verdict: "verified" | "failed";
  received: number;
  sent: number;
}

/** A recognized meeting with another totem (challenge verdict passed). */
export interface Encounter {
  peer: NodeInfo;
  at: Date;
}

export type PeerRelation =
  | { kind: "friend"; since: Date } // mutual kind 3 follow
  | { kind: "request" }; // they follow us; owner answers yes/no

export type Transport = "bluetooth" | "wifi" | "fips";

export interface Peer {
  info: NodeInfo;
  relation: PeerRelation;
  lastMet: Date | null;
  /** Set while the peer is currently connected on the mesh. */
  connected: { transport: Transport } | null;
}

/** A kind 1 event from the node's relay. */
export interface Note {
  id: string;
  author: NodeInfo | null; // null = anonymous guest post
  content: string;
  at: Date;
  own: boolean; // authored by this node's owner
  replyTo: string | null; // id of the note this replies to
}

export type NoteFilter = "all" | "own";

export interface Settings {
  /** Master switch: meet other totems + guest-facing features. */
  publicTotem: boolean;
  wifiForGuests: boolean; // the !Totem AP (only meaningful when public)
  guestPosting: boolean; // relay policy: may guests write (only when public)
  retention: Retention; // relay retention rule
}

/** How the relay sheds notes when storage fills (values TBD in spec). */
export type Retention = "oldest first" | "30 days" | "keep all";
export const RETENTION_OPTIONS: Retention[] = ["oldest first", "30 days", "keep all"];
