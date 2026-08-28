/**
 * The phone claim path, checked where it cannot be checked on hardware.
 *
 * The interesting failures here are all encoding: what the browser does to a
 * `nostrsigner:` link on the way out, and what the signer app does to the
 * signed event on the way back. So the central test is not "does this build a
 * string" but "does Amber's own parse recover exactly what we put in" - that
 * parse is transcribed from IntentUtils.decodeData and is the reason the event
 * is percent-encoded rather than passed raw as the NIP-55 example shows.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
global.window = global;
require('./phone-claim.js');
const claim = globalThis.TotemPhoneClaim;

const CHALLENGE = {
  nonce: 'e6f1c0b28d4a7395',
  url: 'http://10.21.0.1:8080/api/owner/claim',
  method: 'POST',
  payload: '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a',
};

const SIGNED = {
  id: '9b1c'.repeat(16),
  pubkey: '3bf0c63fcb93463407af97a5e5ee64fa883d107ef9e558472c4eb9aaaefa459d',
  created_at: 1756300000,
  kind: 27235,
  content: '',
  tags: [
    ['nonce', CHALLENGE.nonce],
    ['u', CHALLENGE.url],
    ['method', 'POST'],
    ['payload', CHALLENGE.payload],
  ],
  sig: 'ab'.repeat(64),
};

/**
 * Android's Intent.parseUri, for the "intent:" form.
 *
 * Everything between "intent:" and "#Intent;" becomes the scheme-specific part
 * and the scheme= directive replaces the scheme, so an intent link with no "//"
 * yields exactly the opaque "nostrsigner:<payload>" a direct link would.
 * "S.key=value" pairs become String extras, percent-decoded.
 */
function androidParses(uri) {
  const at = uri.indexOf('#Intent;');
  if (at < 0) return { data: uri, extras: {} };
  const payload = uri.slice('intent:'.length, at);
  const extras = {};
  let scheme = '';
  for (const part of uri.slice(at + '#Intent;'.length).split(';')) {
    if (part === 'end' || part === '') continue;
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    const key = part.slice(0, eq);
    const value = decodeURIComponent(part.slice(eq + 1));
    if (key === 'scheme') scheme = value;
    else if (key.startsWith('S.')) extras[key.slice(2)] = value;
  }
  return { data: `${scheme}:${payload}`, extras };
}

/** Amber's read of the URL (IntentUtils.getIntentDataWithoutExtras). */
function amberParses(data) {
  const decoded = decodeURIComponent(data.replace('nostrsigner:', '').replace(/\+/g, '%2b'));
  const parts = decoded.split('?');
  const parameters = {};
  parts.slice(1).forEach((part) => part.split('&').forEach((pair) => {
    const eq = pair.indexOf('=');
    if (eq > 0) parameters[pair.slice(0, eq)] = pair.slice(eq + 1);
  }));
  return { event: parts[0], parameters };
}

/** Amber's read of the extras (IntentUtils.getIntentDataFromIntent). */
function amberReadsExtras(data, extras) {
  return {
    event: decodeURIComponent(data.replace('nostrsigner:', '')).split('?')[0],
    type: extras.type,
    returnType: extras.returnType,
    callbackUrl: extras.callbackUrl,
    appName: extras.appName,
  };
}

test('the authorization carries exactly the four tags totemd accepts', () => {
  const template = claim.authTemplate(CHALLENGE, 1756300000);
  assert.equal(template.kind, 27235);
  assert.equal(template.content, '');
  assert.equal(template.created_at, 1756300000);
  // totemd rejects an event with a fifth tag outright, so this count is a
  // contract and not a detail.
  assert.equal(template.tags.length, 4);
  assert.deepEqual(new Map(template.tags), new Map([
    ['nonce', CHALLENGE.nonce],
    ['u', CHALLENGE.url],
    ['method', 'POST'],
    ['payload', CHALLENGE.payload],
  ]));
});

test('the challenge is echoed, never rebuilt', () => {
  const odd = { nonce: 'N', url: 'http://elsewhere/api/owner/claim', method: 'PUT', payload: 'P' };
  const template = claim.authTemplate(odd, 1);
  const tags = new Map(template.tags);
  assert.equal(tags.get('u'), 'http://elsewhere/api/owner/claim');
  assert.equal(tags.get('method'), 'PUT');
});

test("Amber's parse recovers the event and the parameters exactly", () => {
  const template = claim.authTemplate(CHALLENGE, 1756300000);
  const uri = claim.signerUri(template, claim.callbackUrl('http://10.21.0.1:8080'));
  const seen = amberParses(androidParses(uri).data);
  assert.deepEqual(JSON.parse(seen.event), template);
  assert.equal(seen.parameters.type, 'sign_event');
  // The whole point of one round trip: the finished event carries the pubkey.
  assert.equal(seen.parameters.returnType, 'event');
  assert.equal(seen.parameters.compressionType, 'none');
  assert.equal(seen.parameters.callbackUrl, 'http://10.21.0.1:8080/claim/phone/');
});

test('the callback survives being decoded and split on "?"', () => {
  // The trap this whole design is shaped around. Amber decodes the entire link
  // before splitting it on "?", so a callback ending in "?signed=" comes back
  // truncated at the "?" and the signed event is appended to an address that
  // no longer points at this page. Nothing about percent-encoding prevents it,
  // because the decode happens first.
  const uri = claim.signerUri(claim.authTemplate(CHALLENGE, 1), claim.callbackUrl('http://t'));
  const recovered = amberParses(androidParses(uri).data).parameters.callbackUrl;
  assert.ok(!recovered.includes('?'), 'a callback with a "?" loses everything after it');
  assert.equal(recovered, 'http://t/claim/phone/');
  // And what Amber then builds must land back on this page.
  const back = recovered + encodeURIComponent(JSON.stringify(SIGNED));
  assert.deepEqual(claim.returnedEvent(back), SIGNED);
});

test('the encoded event survives a brace, a quote and a slash', () => {
  const uri = claim.signerUri(claim.authTemplate(CHALLENGE, 1), claim.callbackUrl('http://x'));
  // If the payload were passed raw as the NIP-55 example shows, the decode
  // would split the event on a "?" that never belonged to the parameters.
  assert.ok(!uri.includes('{'), 'the event must not reach the link unencoded');
  assert.ok(!uri.includes('"'), 'the event must not reach the link unencoded');
  assert.equal(JSON.parse(amberParses(androidParses(uri).data).event).tags.length, 4);
});

test('with no callback the signer is asked to use the clipboard', () => {
  // The second way home. NIP-55: "If [callbackUrl] is omitted, the result is
  // copied to the clipboard" - so the absence of the parameter *is* the
  // instruction, and adding it back empty would silently disable the fallback.
  const uri = claim.plainSignerUri(claim.authTemplate(CHALLENGE, 1), null);
  const seen = amberParses(uri);
  assert.equal(seen.parameters.callbackUrl, undefined);
  assert.ok(!uri.includes('callbackUrl'), 'no callback at all, not an empty one');
  // Everything else must still be there, or the answer comes back unusable.
  assert.equal(seen.parameters.type, 'sign_event');
  assert.equal(seen.parameters.returnType, 'event');
  assert.deepEqual(JSON.parse(seen.event).tags.length, 4);
});

test('the signer is sent back to this page and nowhere else', () => {
  assert.equal(claim.callbackUrl('http://10.21.0.1:8080'), 'http://10.21.0.1:8080/claim/phone/');
});

test('a page opened by hand is not a failed return', () => {
  assert.equal(claim.returnedEvent('http://10.21.0.1:8080/claim/phone'), null);
  // The callback address itself, with nothing appended yet.
  assert.equal(claim.returnedEvent('http://10.21.0.1:8080/claim/phone/'), null);
  assert.equal(claim.returnedEvent('http://10.21.0.1:8080/claim/phone#signed='), null);
});

test('a result carried some other way is still read', () => {
  const body = encodeURIComponent(JSON.stringify(SIGNED));
  // A signer that answers in the fragment or the query is not a dead end.
  assert.deepEqual(claim.returnedEvent('http://x/claim/phone#signed=' + body), SIGNED);
  assert.deepEqual(claim.returnedEvent('http://x/claim/phone?signed=' + body), SIGNED);
  // And a blob pasted from the clipboard, which is what Amber does with no
  // callback at all, goes through the same check.
  assert.deepEqual(claim.parseEvent(JSON.stringify(SIGNED)), SIGNED);
});

test('the event Amber appends is read back whole', () => {
  // Uri.encode escapes every reserved character - slashes included - so the
  // event arrives as one path segment and is read by slicing, not by
  // URLSearchParams, which would turn a "+" into a space.
  const href = claim.callbackUrl('http://10.21.0.1:8080') +
    encodeURIComponent(JSON.stringify(SIGNED));
  assert.deepEqual(claim.returnedEvent(href), SIGNED);
  assert.ok(href.includes('%2F'), 'the event keeps its slashes escaped');
});

test('a compressed answer is named, not silently mis-parsed', () => {
  const href = 'http://x/claim/phone/' + encodeURIComponent('Signer1H4sIAAAA');
  assert.throws(() => claim.returnedEvent(href), /compressed/);
});

test('an answer that is not a usable authorization is refused', () => {
  const back = (value) => 'http://x/claim/phone/' + encodeURIComponent(JSON.stringify(value));
  assert.throws(() => claim.returnedEvent('http://x/claim/phone/notjson'), /not an event/);
  assert.throws(() => claim.returnedEvent(back({ ...SIGNED, kind: 1 })), /wrong kind/);
  assert.throws(() => claim.returnedEvent(back({ ...SIGNED, sig: undefined })), /wrong kind/);
  assert.throws(() => claim.returnedEvent(back({ ...SIGNED, pubkey: 42 })), /wrong kind/);
  assert.throws(() => claim.returnedEvent(back(null)), /wrong kind/);
});

test('the header is what totemd decodes back into the event', () => {
  const header = claim.authorization(SIGNED);
  assert.ok(header.startsWith('Nostr '));
  const decoded = Buffer.from(header.slice('Nostr '.length), 'base64').toString('utf8');
  assert.deepEqual(JSON.parse(decoded), SIGNED);
});

/**
 * The screen, on the leg that has no second chance.
 *
 * These tests exist because every pure function above passed while the page was
 * broken: on the return from the signer, init() handled the answer and returned
 * before attaching a single listener. A refused claim then showed the reason
 * next to a button and a paste box that did nothing. Everything below is about
 * what is still usable after something has gone wrong.
 */
const realTimeout = setTimeout;
const settle = () => new Promise((resolve) => realTimeout(resolve, 15));

function fakeElement(id) {
  return {
    id,
    listeners: [],
    hidden: false,
    disabled: false,
    value: '',
    textContent: '',
    className: '',
    addEventListener(_type, fn) { this.listeners.push(fn); },
    focus() {},
  };
}

/** Install a minimal page, run init() against it, and hand back what it did. */
function openPage(href, answer) {
  const made = {};
  for (const id of ['status', 'sign', 'hint', 'pasted', 'manual', 'reveal', 'use-pasted']) {
    made[id] = fakeElement(id);
  }
  const body = { classes: [], classList: { add(name) { body.classes.push(name); } } };
  const fake = {
    document: { body, getElementById: (id) => made[id] ?? null, addEventListener() {} },
    location: { href, origin: 'http://t' },
    fetch: async (path) => answer(String(path)),
    setTimeout: () => 0,
    clearTimeout: () => {},
  };
  const saved = {};
  for (const key of Object.keys(fake)) {
    saved[key] = globalThis[key];
    globalThis[key] = fake[key];
  }
  claim.init();
  return {
    made,
    body,
    restore() { for (const key of Object.keys(saved)) globalThis[key] = saved[key]; },
  };
}

/** totemd refusing the claim, in its own words. */
const refuses = async () => ({
  ok: false,
  status: 409,
  json: async () => ({ ok: false, error: 'totem is already claimed' }),
});

test('a fresh page wires every control', () => {
  const page = openPage('http://t/claim', refuses);
  try {
    for (const id of ['sign', 'reveal', 'use-pasted']) {
      assert.equal(page.made[id].listeners.length, 1, `${id} must respond to a tap`);
    }
    assert.equal(page.made.status.textContent, '', 'and say nothing before anything happened');
  } finally {
    page.restore();
  }
});

test('a refused claim leaves a page the owner can still act on', async () => {
  const page = openPage(
    'http://t/claim/phone/' + encodeURIComponent(JSON.stringify(SIGNED)),
    refuses,
  );
  try {
    await settle();
    for (const id of ['sign', 'reveal', 'use-pasted']) {
      assert.equal(page.made[id].listeners.length, 1,
        `${id} must still respond after the claim was refused`);
    }
    // The server's own words, not a friendly sentence over the top of them.
    assert.match(page.made.status.textContent, /already claimed/);
    assert.equal(page.made.status.className, 'bad');
    assert.equal(page.made.manual.hidden, false, 'the other way in must be offered');
    assert.equal(page.made.sign.disabled, false, 'and the button must be tappable again');
  } finally {
    page.restore();
  }
});

test('an unreadable answer is named, and the page stays usable', () => {
  const page = openPage('http://t/claim/phone/notanevent', refuses);
  try {
    assert.match(page.made.status.textContent, /not an event/);
    assert.equal(page.made.status.className, 'bad');
    assert.equal(page.made.sign.listeners.length, 1);
  } finally {
    page.restore();
  }
});

test('an accepted claim says whose it is and puts the buttons away', async () => {
  const page = openPage(
    'http://t/claim/phone/' + encodeURIComponent(JSON.stringify(SIGNED)),
    async () => ({ ok: true, status: 200, json: async () => ({ ok: true, claimed: true }) }),
  );
  try {
    await settle();
    assert.match(page.made.status.textContent, /yours/);
    assert.equal(page.made.status.className, 'good');
    assert.ok(page.made.status.textContent.includes(SIGNED.pubkey.slice(0, 8)),
      'the owner must be able to check the key against the panel');
    assert.deepEqual(page.body.classes, ['done']);
    assert.equal(page.made.manual.hidden, true);
  } finally {
    page.restore();
  }
});

test('a marker glued in front of the answer is peeled, not parsed', () => {
  // The path stop matches first on the callback this page hands out, so a
  // signer that appends after "#signed=" would otherwise hand parseEvent a
  // string that begins with the marker and can never be JSON.
  const body = encodeURIComponent(JSON.stringify(SIGNED));
  assert.deepEqual(claim.returnedEvent('http://t/claim/phone/#signed=' + body), SIGNED);
  assert.deepEqual(claim.returnedEvent('http://t/claim/phone/?signed=' + body), SIGNED);
  // And a bare marker with nothing after it is still not a failed return.
  assert.equal(claim.returnedEvent('http://t/claim/phone/#signed='), null);
});

test('one claim at a time, however many times the button is tapped', async () => {
  let posts = 0;
  const page = openPage(
    'http://t/claim/phone/' + encodeURIComponent(JSON.stringify(SIGNED)),
    async (path) => {
      if (String(path).includes('/api/owner/claim')) posts += 1;
      return { ok: true, status: 200, json: async () => ({ ok: true, claimed: true }) };
    },
  );
  try {
    // Tapping "use this answer" while the first claim is in flight must not
    // send the same spent authorization again; the refusal would overwrite the
    // success the first tap earned.
    page.made.pasted.value = JSON.stringify(SIGNED);
    page.made['use-pasted'].listeners[0]();
    await settle();
    assert.equal(posts, 1, 'exactly one claim reaches the server');
    assert.equal(page.made['use-pasted'].disabled, true);
  } finally {
    page.restore();
  }
});

test('Amber finds the request whichever way it looks', () => {
  // This is the bug that reached hardware. IntentUtils routes on whether the
  // launching browser set Browser.EXTRA_APPLICATION_ID: with it, the parameters
  // are read from the URL; without it, from the intent extras. A plain
  // "nostrsigner:" link carries no extras, so on that branch parseSignerType
  // got null and Amber answered "Amber received a malformed nostrsigner
  // request". Which branch runs is not ours to choose, so both must work.
  const template = claim.authTemplate(CHALLENGE, 1756300000);
  const back = claim.callbackUrl('http://10.21.0.1:8080');
  const { data, extras } = androidParses(claim.signerUri(template, back));

  // The URL branch.
  const url = amberParses(data);
  assert.equal(url.parameters.type, 'sign_event');
  assert.equal(url.parameters.returnType, 'event');
  assert.equal(url.parameters.callbackUrl, back);
  assert.deepEqual(JSON.parse(url.event), template);

  // The extras branch, which reads the event from the URI and the rest here.
  const bare = amberReadsExtras(data, extras);
  assert.equal(bare.type, 'sign_event');
  assert.equal(bare.returnType, 'event');
  assert.equal(bare.callbackUrl, back);
  assert.deepEqual(JSON.parse(bare.event), template);

  // And the data really is the opaque form Amber strips a scheme off.
  assert.ok(data.startsWith('nostrsigner:'), data.slice(0, 24));
  assert.ok(!data.startsWith('nostrsigner://'), 'a "//" would make it hierarchical');
});

test('the clipboard variant keeps both halves callback-free', () => {
  const { data, extras } = androidParses(claim.signerUri(claim.authTemplate(CHALLENGE, 1), null));
  assert.equal(amberParses(data).parameters.callbackUrl, undefined);
  assert.equal(extras.callbackUrl, undefined);
  // NIP-55: the absence of the parameter is the instruction to use the clipboard.
  assert.equal(extras.type, 'sign_event');
});
