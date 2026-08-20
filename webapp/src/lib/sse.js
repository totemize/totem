/**
 * Pull complete SSE messages from a chunked response buffer.
 * @param {string} buffer
 * @returns {{ events: { event: string, data: string }[], rest: string }}
 */
export function parseSse(buffer) {
  const events = [];
  let match;
  while ((match = /\r?\n\r?\n/.exec(buffer))) {
    const block = buffer.slice(0, match.index);
    buffer = buffer.slice(match.index + match[0].length);
    let event = "message";
    const data = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trimStart();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length) events.push({ event, data: data.join("\n") });
  }
  return { events, rest: buffer };
}
