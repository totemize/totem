// nos2x injects its content script on every URL, but exposes the page-side
// provider only to HTTPS and localhost. This bridge speaks the content
// script's postMessage protocol when a Totem is reached over LAN HTTP.

/**
 * @param {Window | (EventTarget & { postMessage(message: unknown, targetOrigin: string): void })} target
 * @param {number} operationTimeout
 */
export function createNos2xSigner(target = window, operationTimeout = 120_000) {
  let sequence = 0;
  /** @type {string | null} */
  let pubkey = null;
  let closed = false;
  /** @type {Map<string, { resolve(value: unknown): void, reject(error: Error): void, timer: ReturnType<typeof setTimeout>, acceptError: boolean }>} */
  const pending = new Map();

  /** @param {Event & { data?: unknown, source?: unknown }} message */
  function receive(message) {
    if (message.source && message.source !== target) return;
    const data = message.data;
    if (
      !data ||
      typeof data !== "object" ||
      !("id" in data) ||
      !("ext" in data) ||
      !("response" in data)
    ) return;
    if (data.ext !== "nos2x" || typeof data.id !== "string") return;
    const request = pending.get(data.id);
    if (!request) return;
    clearTimeout(request.timer);
    pending.delete(data.id);
    const response = data.response;
    if (
      response &&
      typeof response === "object" &&
      "error" in response &&
      response.error &&
      typeof response.error === "object"
    ) {
      const detail = "message" in response.error ? String(response.error.message) : "request failed";
      if (request.acceptError) request.resolve(undefined);
      else request.reject(new Error(`nos2x: ${detail}`));
    } else {
      request.resolve(response);
    }
  }

  target.addEventListener("message", receive);

  /** @param {string} type @param {object} params @param {number} timeout @param {boolean} acceptError */
  function call(type, params, timeout = operationTimeout, acceptError = false) {
    if (closed) return Promise.reject(new Error("nos2x signer is disconnected"));
    const id = `totem-${Date.now().toString(36)}-${++sequence}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error("nos2x did not answer on this page"));
      }, timeout);
      pending.set(id, { resolve, reject, timer, acceptError });
      target.postMessage({ id, ext: "nos2x", type, params }, "*");
    });
  }

  return Object.freeze({
    async getPublicKey() {
      if (pubkey) return pubkey;
      const value = await call("getPublicKey", {});
      if (typeof value !== "string") throw new Error("nos2x returned an invalid public key");
      pubkey = value;
      return value;
    },
    /** @param {{ kind: number, created_at: number, tags: string[][], content: string }} event */
    signEvent(event) {
      return call("signEvent", { event });
    },
    // replaceURL needs no permission, so it detects the content script without
    // asking for the owner's key. Any response, including an error, proves it.
    probe(timeout = 1_500) {
      return call("replaceURL", { url: "nostr:invalid" }, timeout, true);
    },
    clear() {
      if (closed) return;
      closed = true;
      target.removeEventListener("message", receive);
      for (const request of pending.values()) {
        clearTimeout(request.timer);
        request.reject(new Error("nos2x signer is disconnected"));
      }
      pending.clear();
      pubkey = null;
    },
  });
}
