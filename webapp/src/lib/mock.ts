import type { BusClient, BusPush, RelayClient } from "./api";
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

function storage(): globalThis.Storage | null {
  return typeof localStorage === "undefined" ? null : localStorage;
}

/** Deterministic fake hex pubkey from a seed string. */
function fakePubkey(seed: string): Pubkey {
  let h = 2166136261;
  for (const c of seed) h = (h ^ c.charCodeAt(0)) * 16777619;
  const hex = (h >>> 0).toString(16).padStart(8, "0");
  return hex.repeat(8).slice(0, 64);
}

const minutes = (n: number) => new Date(Date.now() - n * 60_000);
const days = (n: number) => minutes(n * 24 * 60);

function node(name: string): NodeInfo {
  return { pubkey: fakePubkey(name), name, relayUrl: `ws://${name}.local:7777` };
}

const self: NodeInfo = { ...node("café-totem"), relayUrl: "ws://totem.local:7777" };
const park: NodeInfo = node("park-totem");
const harbor: NodeInfo = node("harbor-totem");
const lib: NodeInfo = node("lib-totem");

const GB = 1024 ** 3;

export class MockBus implements BusClient {
  private handlers = new Set<(push: BusPush) => void>();

  /** Claim state persists across reloads; resetConfig() clears it. */
  private claimed = storage()?.getItem("mock.claimed") === "1";
  private name = storage()?.getItem("mock.name") ?? "totem-a4f2";

  private peers: Peer[] = [
    { info: harbor, relation: { kind: "request" }, lastMet: minutes(35), connected: { transport: "fips" } },
    { info: park, relation: { kind: "friend", since: days(30) }, lastMet: minutes(14), connected: { transport: "bluetooth" } },
    { info: lib, relation: { kind: "friend", since: days(90) }, lastMet: days(17), connected: null },
  ];

  private settings: Settings = {
    publicTotem: true,
    wifiForGuests: true,
    guestPosting: true,
    retention: "oldest first",
  };

  async getNode(): Promise<NodeInfo> {
    return { ...self, name: this.name };
  }

  async claim(_ownerNpub: string): Promise<void> {
    // No real device yet, so presence is faked on every path: clicking
    // the pulse (window.mockPress) confirms, 60s without a press rejects.
    // A real BusClient replaces this with the actual button/NFC wait.
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        delete (window as { mockPress?: () => void }).mockPress;
        reject(new Error("timeout"));
      }, 60_000);
      (window as { mockPress?: () => void }).mockPress = () => {
        clearTimeout(timer);
        delete (window as { mockPress?: () => void }).mockPress;
        resolve();
      };
      console.info("presence: call window.mockPress() to simulate the device button");
    });
    this.claimed = true;
    storage()?.setItem("mock.claimed", "1");
  }

  async setName(name: string): Promise<void> {
    this.name = name;
    storage()?.setItem("mock.name", name);
  }

  async resetConfig(): Promise<void> {
    this.claimed = false;
    this.name = "totem-a4f2";
    storage()?.removeItem("mock.claimed");
    storage()?.removeItem("mock.name");
  }

  async getStatus(): Promise<NodeStatus> {
    return {
      claimed: this.claimed,
      health: "good",
      batteryPct: 78,
      batteryHoursLeft: 14,
      storageUsedBytes: 2.1 * GB,
      storageTotalBytes: 32 * GB,
      relayEventCount: 41_203,
      totemsMet: 12,
      lastEncounter: { peer: park, at: minutes(14) },
      mesh: { up: true, peersConnected: 2, address: "café-totem.fips" },
    };
  }

  async getEncounterLog(): Promise<EncounterLogEntry[]> {
    return [
      { peer: park, at: minutes(14), transport: "bluetooth", verdict: "verified", received: 212, sent: 8 },
      { peer: harbor, at: minutes(35), transport: "fips", verdict: "verified", received: 0, sent: 0 },
      { peer: harbor, at: days(8), transport: "wifi", verdict: "verified", received: 1904, sent: 41 },
      { peer: { ...lib, name: "unknown marker" }, at: days(11), transport: "bluetooth", verdict: "failed", received: 0, sent: 0 },
      { peer: lib, at: days(17), transport: "bluetooth", verdict: "verified", received: 356, sent: 12 },
    ];
  }

  async getPeers(): Promise<Peer[]> {
    return [...this.peers];
  }

  async addContact(pubkey: Pubkey): Promise<void> {
    const peer = this.peers.find((p) => p.info.pubkey === pubkey);
    if (peer) peer.relation = { kind: "friend", since: new Date() };
    this.emit({ type: "totem.befriended", pubkey });
  }

  async removeContact(pubkey: Pubkey): Promise<void> {
    this.peers = this.peers.filter((p) => p.info.pubkey !== pubkey);
  }

  async getSettings(): Promise<Settings> {
    return { ...this.settings };
  }

  async updateSettings(patch: Partial<Settings>): Promise<void> {
    Object.assign(this.settings, patch);
  }

  onPush(handler: (push: BusPush) => void): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  private emit(push: BusPush): void {
    for (const h of this.handlers) h(push);
  }
}

export class MockRelay implements RelayClient {
  private notes: Note[] = [
    note("n1", park, "Someone left sea glass on the counter — take a piece, leave a story.", 14),
    note("n2", null, "First time seeing one of these boxes. Whoever built this: the coffee here is great.", 26),
    note("n3", self, "Taking the totem to the harbor market on Saturday. Notes posted here travel along.", 120, true),
    note("n4", lib, "Reading circle moved to Thursdays. The poster wall has the details.", 60 * 26),
    note("n5", park, "Lost: blue scarf, bench by the fountain. It has a story, ask me.", 60 * 30),
    note("n6", null, "Passing through. This town hides its best places well.", 60 * 47),
    note("r1", lib, "Saved a green piece for the reading circle table.", 9, false, "n1"),
    note("r2", null, "Took the blue one — left a shell from the north beach.", 4, false, "n1"),
  ];

  async listNotes(filter: NoteFilter): Promise<Note[]> {
    const all = [...this.notes]
      .filter((n) => !n.replyTo)
      .sort((a, b) => b.at.getTime() - a.at.getTime());
    return filter === "own" ? all.filter((n) => n.own) : all;
  }

  async listReplies(noteId: string): Promise<Note[]> {
    return this.notes
      .filter((n) => n.replyTo === noteId)
      .sort((a, b) => a.at.getTime() - b.at.getTime());
  }

  async publishNote(content: string, replyTo?: string): Promise<Note> {
    const n = note(`n${this.notes.length + 1}`, self, content, 0, true, replyTo ?? null);
    this.notes.push(n);
    return n;
  }

  async removeNote(id: string): Promise<void> {
    this.notes = this.notes.filter((n) => n.id !== id);
  }
}

function note(
  id: string,
  author: NodeInfo | null,
  content: string,
  minutesAgo: number,
  own = false,
  replyTo: string | null = null,
): Note {
  return { id, author, content, at: minutes(minutesAgo), own, replyTo };
}
