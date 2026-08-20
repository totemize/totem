import type {
  EncounterLogEntry,
  NodeInfo,
  NodeStatus,
  Note,
  NoteFilter,
  Peer,
  Pubkey,
  Settings,
} from "./types";

/**
 * The two seams the app talks through, mirroring the real architecture
 * (spec 10-control-plane): totemd's bus for control, the relay for notes.
 * Mocks implement these today; real clients replace them without touching
 * the views.
 */

/** Push types from /bus/events (spec 07-conventions bus registry). */
export type BusPush =
  | { type: "totem.peer.seen"; pubkey: Pubkey }
  | { type: "totem.recognized"; pubkey: Pubkey }
  | { type: "totem.befriended"; pubkey: Pubkey }
  | { type: "totem.sync.started"; pubkey: Pubkey }
  | { type: "totem.sync.done"; pubkey: Pubkey; received: number; sent: number };

/**
 * Control plane. Real impl: NIP-5D request/result over HTTP
 * ({type:"totem.status.get",id} -> {type:"...result",ok,...}) plus SSE.
 * Pushes are lossy by design — on (re)connect, reconcile with getStatus().
 */
export interface BusClient {
  getNode(): Promise<NodeInfo>;
  getStatus(): Promise<NodeStatus>;
  getPeers(): Promise<Peer[]>;
  /** totemd's append-only encounter log, newest first. */
  getEncounterLog(): Promise<EncounterLogEntry[]>;
  /** totem.contacts.add / totem.contacts.remove — the kind 3 single writer. */
  addContact(pubkey: Pubkey): Promise<void>;
  removeContact(pubkey: Pubkey): Promise<void>;
  getSettings(): Promise<Settings>;
  updateSettings(patch: Partial<Settings>): Promise<void>;
  /**
   * First-time claim (provisioning is an open question in the spec —
   * this models our proposal): registers the owner npub as a pending
   * claim and resolves once physical presence is confirmed on the
   * device (button press / NFC tap). Rejects on timeout.
   */
  claim(ownerNpub: string): Promise<void>;
  /** Rename the totem (NIP-11 name after the "!Totem " marker). */
  setName(name: string): Promise<void>;
  /** Factory-reset the config: clears the owner allowlist and name. */
  resetConfig(): Promise<void>;
  /** Subscribe to pushes; returns unsubscribe. */
  onPush(handler: (push: BusPush) => void): () => void;
}

/**
 * Notes live on the relay, not the bus: the app is a plain nostr client
 * there (NIP-98-signed writes for owner actions like deletion).
 */
export interface RelayClient {
  /** Top-level notes only. */
  listNotes(filter: NoteFilter): Promise<Note[]>;
  listReplies(noteId: string): Promise<Note[]>;
  publishNote(content: string, replyTo?: string): Promise<Note>;
  /** Owner moderation: publish a deletion for the given event. */
  removeNote(id: string): Promise<void>;
}
