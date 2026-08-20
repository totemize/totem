import assert from "node:assert/strict";
import test from "node:test";
import { createNos2xSigner } from "../src/lib/nos2x.js";

class FakeWindow extends EventTarget {
  calls = [];

  postMessage(message) {
    this.calls.push(message);
    const response = message.type === "replaceURL"
      ? { error: { message: "invalid test URL" } }
      : message.type === "getPublicKey"
        ? "a".repeat(64)
        : { ...message.params.event, id: "signed" };
    queueMicrotask(() => {
      const event = new Event("message");
      Object.defineProperty(event, "data", {
        value: { id: message.id, ext: "nos2x", response },
      });
      this.dispatchEvent(event);
    });
  }
}

test("nos2x bridge probes, caches its key, and signs", async () => {
  const target = new FakeWindow();
  const signer = createNos2xSigner(target, 100);
  await signer.probe(); // an error response still proves the content script exists
  assert.equal(await signer.getPublicKey(), "a".repeat(64));
  assert.equal(await signer.getPublicKey(), "a".repeat(64));
  assert.equal(target.calls.filter((call) => call.type === "getPublicKey").length, 1);
  assert.deepEqual(await signer.signEvent({ kind: 1 }), { kind: 1, id: "signed" });
  signer.clear();
  await assert.rejects(signer.getPublicKey(), /disconnected/);
});

test("nos2x bridge fails promptly when no content script answers", async () => {
  const target = new EventTarget();
  target.postMessage = () => {};
  const signer = createNos2xSigner(target, 5);
  await assert.rejects(signer.probe(5), /did not answer/);
  signer.clear();
});
