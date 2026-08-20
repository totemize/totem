import { parseSse } from "./sse.js";

export type Befriend = "auto" | "ask" | "never";

export interface TotemConfig {
  device_name: string;
  probe: boolean;
  verdict_ttl_hours: number;
  befriend: Befriend;
  sync: boolean;
}

export interface Profile {
  name: string;
  display_name?: string;
  about?: string;
  picture?: string;
  website?: string;
  source: string;
  nip11_name: string;
}

export interface TotemStatus {
  version: string;
  uptime_secs: number;
  config: TotemConfig;
  fips: {
    connected: boolean;
    npub: string | null;
    mesh_size: number;
    last_ok_secs_ago: number | null;
    last_error: string | null;
  };
  peers: number;
  recognized: number;
  claimed: boolean;
  events: Record<string, number>;
}

export interface PublicSnapshot {
  profile: Profile;
  relay_url: string;
  status: TotemStatus;
}

export interface PeerSnapshot {
  npub: string;
  ipv6_addr: string;
  transport_type: string;
  first_seen: number;
  last_seen: number;
  probe_verdict: string | null;
  nip11_name: string | null;
  recognized: boolean;
  sync_attempt: number | null;
  sync_state: string | null;
  sync_duration_ms: number | null;
  sync_exit_code: number | null;
  sync_error: string | null;
}

export type Push = { type: string } & Record<string, unknown>;

export interface OwnerFrame {
  status: TotemStatus;
  peers: PeerSnapshot[];
  events?: Push[];
  event?: Push;
}

export interface OwnerSigner {
  getPublicKey(): Promise<string>;
  signEvent(template: {
    kind: number;
    created_at: number;
    tags: string[][];
    content: string;
  }): Promise<unknown>;
  clear?(): void;
}

declare global {
  interface Window {
    nostr?: OwnerSigner;
    TotemNsec?: { signer(value: string): OwnerSigner };
  }
}

interface Challenge {
  nonce: string;
  url: string;
  method: string;
  payload: string;
}

function errorText(value: unknown, fallback: string): string {
  if (value && typeof value === "object" && "error" in value && typeof value.error === "string") {
    return value.error;
  }
  return fallback;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...options });
  const value: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorText(value, `Request failed (${response.status})`));
  return value as T;
}

function base64(value: string): string {
  let binary = "";
  for (const byte of new TextEncoder().encode(value)) binary += String.fromCharCode(byte);
  return btoa(binary);
}

async function authorization(
  signer: OwnerSigner,
  path: string,
  method: string,
  body: string,
): Promise<string> {
  const challenge = await requestJson<Challenge>("/api/auth/challenge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, method, body }),
  });
  const event = await signer.signEvent({
    kind: 27235,
    created_at: Math.floor(Date.now() / 1000),
    content: "",
    tags: [
      ["nonce", challenge.nonce],
      ["u", challenge.url],
      ["method", challenge.method],
      ["payload", challenge.payload],
    ],
  });
  return `Nostr ${base64(JSON.stringify(event))}`;
}

async function signedJson<T>(
  signer: OwnerSigner,
  path: string,
  method: string,
  value: object,
): Promise<T> {
  const body = JSON.stringify(value);
  return requestJson<T>(path, {
    method,
    headers: {
      Authorization: await authorization(signer, path, method, body),
      "Content-Type": "application/json",
    },
    body,
  });
}

export function loadSnapshot(): Promise<PublicSnapshot> {
  return requestJson("/api/status");
}

export async function waitForNip07(timeout = 5000): Promise<OwnerSigner> {
  const deadline = Date.now() + timeout;
  do {
    if (
      window.nostr &&
      typeof window.nostr.getPublicKey === "function" &&
      typeof window.nostr.signEvent === "function"
    ) {
      return window.nostr;
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  } while (Date.now() < deadline);
  throw new Error("No NIP-07 extension detected. Retry or use a development nsec.");
}

let nsecScript: Promise<void> | null = null;

function loadNsecSigner(): Promise<void> {
  if (window.TotemNsec) return Promise.resolve();
  if (!nsecScript) {
    nsecScript = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/nsec-signer.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Local nsec signer failed to load."));
      document.head.append(script);
    });
  }
  return nsecScript;
}

export async function nsecSigner(value: string): Promise<OwnerSigner> {
  await loadNsecSigner();
  if (!window.TotemNsec) throw new Error("Local nsec signer failed to load.");
  return window.TotemNsec.signer(value);
}

export function claim(signer: OwnerSigner): Promise<{ claimed: boolean }> {
  return signedJson(signer, "/api/owner/claim", "POST", {});
}

export function putMetadata(
  signer: OwnerSigner,
  metadata: {
    name: string;
    display_name?: string;
    about?: string;
    picture?: string;
    website?: string;
  },
): Promise<{ profile: Profile; event_id: string }> {
  return signedJson(signer, "/api/metadata", "PUT", metadata);
}

export function putConfig(
  signer: OwnerSigner,
  config: { sync: boolean; befriend: Befriend },
): Promise<{ config: TotemConfig }> {
  return signedJson(signer, "/api/config", "PUT", config);
}

/** One signed connection yields current history/state and future typed pushes. */
export async function streamOwner(
  signer: OwnerSigner,
  signal: AbortSignal,
  onFrame: (frame: OwnerFrame) => void,
): Promise<void> {
  const path = "/api/owner/events";
  const response = await fetch(path, {
    cache: "no-store",
    headers: {
      Accept: "text/event-stream",
      Authorization: await authorization(signer, path, "GET", ""),
    },
    signal,
  });
  if (!response.ok) {
    const value: unknown = await response.json().catch(() => null);
    throw new Error(errorText(value, `Owner stream failed (${response.status})`));
  }
  if (!response.body) throw new Error("Owner stream has no response body.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let rest = "";
  while (true) {
    const { done, value } = await reader.read();
    rest += decoder.decode(value, { stream: !done });
    const parsed = parseSse(rest);
    rest = parsed.rest;
    for (const event of parsed.events) {
      if (event.event === "snapshot" || event.event === "update") {
        onFrame(JSON.parse(event.data) as OwnerFrame);
      }
    }
    if (done) return;
  }
}
