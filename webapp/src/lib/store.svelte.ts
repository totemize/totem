import type { BusClient, RelayClient } from "./api";
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

export type Screen =
  | "home"
  | "peers"
  | "notes"
  | "settings"
  | "encounters"
  | "landing"
  | "note"
  | "activity";

export type SetupStep = "welcome" | "presence" | "name" | "public";

export interface State {
  screen: Screen;
  /** Screen to return to when settings toggles closed. */
  beforeSettings: Screen;
  node: NodeInfo | null;
  status: NodeStatus | null;
  peers: Peer[];
  notes: Note[];
  noteFilter: NoteFilter;
  settings: Settings | null;
  /** First-run claim flow; null once the totem is claimed. */
  setup: { step: SetupStep; ownerNpub: string; error: string | null } | null;
  encounterLog: EncounterLogEntry[];
  friendFilter: "all" | "active" | "requests";
  /** Note composer open on the Notes screen. */
  composing: boolean;
  /** Note id whose ⋯ actions are expanded. */
  noteMenu: string | null;
  /** Totem whose landing page is open (screen "landing") — any totem,
   * friend or not; carries the identity so no list lookup is needed. */
  landing: NodeInfo | null;
  /** Note open in the detail view (screen "note"), with its replies. */
  openNote: Note | null;
  replies: Note[];
}

/** Reactive app store: Svelte 5 runes state, mutations via methods. */
export class Store {
  state = $state<State>({
    screen: "home",
    beforeSettings: "home",
    node: null,
    status: null,
    peers: [],
    notes: [],
    noteFilter: "all",
    settings: null,
    setup: null,
    encounterLog: [],
    friendFilter: "all",
    composing: false,
    noteMenu: null,
    landing: null,
    openNote: null,
    replies: [],
  });

  constructor(
    private bus: BusClient,
    private relay: RelayClient,
  ) {
    // Pushes are lossy; any push just triggers a reconcile.
    this.bus.onPush(() => void this.refresh());
  }

  async refresh(): Promise<void> {
    const [node, status, peers, notes, settings, encounterLog] = await Promise.all([
      this.bus.getNode(),
      this.bus.getStatus(),
      this.bus.getPeers(),
      this.relay.listNotes(this.state.noteFilter),
      this.bus.getSettings(),
      this.bus.getEncounterLog(),
    ]);
    Object.assign(this.state, { node, status, peers, notes, settings, encounterLog });
    if (!status.claimed && !this.state.setup) {
      this.state.setup = { step: "welcome", ownerNpub: "", error: null };
    }
  }

  show(screen: Screen): void {
    this.state.screen = screen;
  }

  toggleSettings(): void {
    if (this.state.screen === "settings") {
      this.show(this.state.beforeSettings);
    } else {
      this.state.beforeSettings = this.state.screen;
      this.show("settings");
    }
  }

  setFriendFilter(filter: "all" | "active" | "requests"): void {
    this.state.friendFilter = filter;
  }

  /** Screen to return to when closing a landing page. */
  private beforeLanding: Screen = "peers";

  openLanding(info: NodeInfo): void {
    if (this.state.screen !== "landing") this.beforeLanding = this.state.screen;
    this.state.landing = info;
    this.show("landing");
  }

  closeLanding(): void {
    this.show(this.beforeLanding);
  }

  private beforeNote: Screen = "notes";

  async openNoteDetail(note: Note): Promise<void> {
    if (this.state.screen !== "note") this.beforeNote = this.state.screen;
    this.state.openNote = note;
    this.state.replies = await this.relay.listReplies(note.id);
    this.show("note");
  }

  closeNoteDetail(): void {
    this.state.openNote = null;
    this.show(this.beforeNote);
  }

  /** Mixed activity feed, newest first: encounters and notes. */
  activity(): { at: Date; text: string; note: Note | null; peer: NodeInfo | null }[] {
    const events: { at: Date; text: string; note: Note | null; peer: NodeInfo | null }[] = [];
    for (const e of this.state.encounterLog) {
      events.push({
        at: e.at,
        text: e.verdict === "failed" ? "a stranger failed the challenge" : `met ${e.peer.name}`,
        note: null,
        peer: e.peer,
      });
    }
    for (const n of this.state.notes) {
      events.push({
        at: n.at,
        text: n.own ? "you posted a note" : `${n.author?.name ?? "a guest"} left a note`,
        note: n,
        peer: null,
      });
    }
    return events.sort((a, b) => b.at.getTime() - a.at.getTime());
  }

  async publishReply(content: string): Promise<void> {
    const open = this.state.openNote;
    if (!open) return;
    await this.relay.publishNote(content, open.id);
    this.state.replies = await this.relay.listReplies(open.id);
  }

  async setNoteFilter(filter: NoteFilter): Promise<void> {
    this.state.noteFilter = filter;
    this.state.notes = await this.relay.listNotes(filter);
  }

  async answerPeerRequest(pubkey: Pubkey, accept: boolean): Promise<void> {
    if (accept) await this.bus.addContact(pubkey);
    else await this.bus.removeContact(pubkey);
    this.state.peers = await this.bus.getPeers();
  }

  setComposing(open: boolean): void {
    this.state.composing = open;
    if (open) this.state.screen = "notes";
  }

  toggleNoteMenu(id: string): void {
    this.state.noteMenu = this.state.noteMenu === id ? null : id;
  }

  async removeNote(id: string): Promise<void> {
    await this.relay.removeNote(id);
    this.state.noteMenu = null;
    this.state.notes = await this.relay.listNotes(this.state.noteFilter);
  }

  async publishNote(content: string): Promise<void> {
    await this.relay.publishNote(content);
    this.state.composing = false;
    this.state.notes = await this.relay.listNotes(this.state.noteFilter);
  }

  async updateSettings(patch: Partial<Settings>): Promise<void> {
    await this.bus.updateSettings(patch);
    this.state.settings = await this.bus.getSettings();
  }

  async resetConfig(): Promise<void> {
    await this.bus.resetConfig();
    this.state.screen = "home";
    this.state.setup = null; // refresh() re-enters setup on unclaimed status
    await this.refresh();
  }

  setupGo(step: SetupStep): void {
    if (!this.state.setup) return;
    this.state.setup.step = step;
    this.state.setup.error = null;
  }

  /**
   * Claim the totem. The owner key is generated on the device for now
   * (no external signer); the claim is bound by physical presence.
   */
  async setupClaim(): Promise<void> {
    const setup = this.state.setup;
    if (!setup) return;
    setup.ownerNpub = "device-generated";
    setup.step = "presence";
    setup.error = null;
    try {
      await this.bus.claim(setup.ownerNpub);
      setup.step = "name";
    } catch {
      setup.step = "welcome";
      setup.error = "no press detected — try again";
    }
  }

  async setupSetName(name: string): Promise<void> {
    if (!this.state.setup) return;
    const trimmed = name.trim();
    if (trimmed) await this.bus.setName(trimmed);
    this.state.node = await this.bus.getNode();
    this.state.setup.step = "public";
  }

  async setupFinish(): Promise<void> {
    this.state.setup = null;
    this.state.screen = "home";
    await this.refresh();
  }
}
