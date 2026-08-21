import assert from "node:assert/strict";
import test from "node:test";
import { parseSse } from "../src/lib/sse.js";

test("parses complete SSE frames and retains a split frame", () => {
  const parsed = parseSse(
    'event: snapshot\r\ndata: {"ok":true}\r\n\r\nevent: update\ndata: {"n":1}\n\nevent: up',
  );
  assert.deepEqual(parsed.events, [
    { event: "snapshot", data: '{"ok":true}' },
    { event: "update", data: '{"n":1}' },
  ]);
  assert.equal(parsed.rest, "event: up");
});
