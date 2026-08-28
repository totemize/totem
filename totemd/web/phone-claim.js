/**
 * Claim a Totem from a phone, with no relay and no internet.
 *
 * The other two ways into this page do not exist on a phone. A browser
 * extension is desktop-only, and pasting an nsec into a web page is the one
 * thing a signer app exists to prevent - it is offered here as a development
 * aid and must never be the buyer's path. So an unboxed Totem could be claimed
 * from a laptop and from nothing else.
 *
 * NIP-55 closes that gap without adding a network. The page hands the unsigned
 * authorization to the phone's signer app through a `nostrsigner:` link, the
 * owner approves it there, and the signer comes back to this same page with the
 * signed event in the URL. Both halves are the phone talking to itself; the
 * Totem is reached only over its own access point. Nothing leaves the room.
 *
 * The alternative, NIP-46, needs a relay both sides can reach - which offline
 * means this box, and every failure then lands on a rendezvous that is also the
 * thing being claimed. This path has no rendezvous at all.
 */
(function (global) {
  'use strict';

  /** The one thing a claim needs signed: a NIP-98 authorization. */
  var CLAIM_KIND = 27235;
  var CLAIM_PATH = '/api/owner/claim';
  var CLAIM_METHOD = 'POST';
  /** The claim carries no body of its own; the signature is the whole request. */
  var CLAIM_BODY = '{}';
  /**
   * Where the signer app comes back to, and why it is a path and not a query.
   *
   * Amber URL-decodes the whole link and only then splits it on "?" to find the
   * parameters (`IntentUtils.getIntentDataWithoutExtras`). A callback ending in
   * "?signed=" therefore loses everything from the "?" onward, and the signed
   * event comes back glued to a truncated address. A trailing path segment
   * survives that parse untouched, and `Uri.encode` escapes the event's slashes
   * too, so the whole thing lands in one segment.
   */
  var RETURN_PATH = '/claim/phone/';

  /**
   * The authorization totemd will accept, unsigned.
   *
   * Exactly these four tags, in any order, and empty content: totemd rejects a
   * fifth tag outright, so nothing may be added here for flavour. Every value
   * is echoed from the challenge rather than rebuilt, because the server
   * compares them against what it issued, not against what they should be.
   *
   * Two of those four are not NIP-98, and that is deliberate rather than
   * sloppy. The spec names `u` and `method`, allows `payload`, and says
   * created_at MUST fall inside a window of about a minute. This device has no
   * real-time clock, so that window is unenforceable here and a strict reading
   * would refuse every claim it ever received. The `nonce` carries the
   * freshness instead: the server issues it, binds it to one URL, method and
   * body hash, and spends it on first use.
   *
   * The cost is worth stating plainly: a generic NIP-98 client sends no nonce
   * and this endpoint refuses it. created_at is still set from the phone's
   * clock, which is the one clock in the exchange worth believing, so nothing
   * has to change here if the server ever starts checking it.
   */
  function authTemplate(challenge, nowSeconds) {
    return {
      kind: CLAIM_KIND,
      created_at: nowSeconds,
      content: '',
      tags: [
        ['nonce', challenge.nonce],
        ['u', challenge.url],
        ['method', challenge.method],
        ['payload', challenge.payload],
      ],
    };
  }

  /**
   * The link that wakes the signer app.
   *
   * The event is percent-encoded because Amber URL-decodes the whole payload
   * before reading it (`IntentUtils.decodeData`), and it splits the decoded
   * string on "?" to find the parameters - so a raw brace or quote arriving
   * re-encoded from the browser would be decoded into the wrong place.
   *
   * `returnType=event` asks for the finished event rather than the bare
   * signature, which is what makes this one round trip instead of two: the
   * event carries the owner's pubkey, so the page never has to ask who they
   * are first.
   */
  function signerUri(template, callbackUrl) {
    var event = encodeURIComponent(JSON.stringify(template));
    // Every parameter is sent twice, in the two places Amber looks - and it
    // looks in exactly one of them, chosen by something this page does not
    // control. IntentUtils routes on whether the launching browser set
    // Browser.EXTRA_APPLICATION_ID: with it, the parameters are read out of the
    // URL; without it, out of the intent extras, and a plain "nostrsigner:"
    // link carries no extras at all. Measured on hardware: Amber answered
    // "Amber received a malformed nostrsigner request", which is what
    // parseSignerType(null) produces. Sending both costs a longer link and
    // removes the browser from the question.
    var query = '?compressionType=none' +
      '&returnType=event' +
      '&type=sign_event' +
      '&appName=Totem' +
      (callbackUrl ? '&callbackUrl=' + encodeURIComponent(callbackUrl) : '');
    // An "intent:" link with no "//" keeps the payload opaque, so Amber sees
    // exactly the "nostrsigner:<event>?..." it would have seen directly.
    var extras = ';S.type=sign_event' +
      ';S.returnType=event' +
      ';S.compression=none' +
      ';S.appName=Totem' +
      (callbackUrl ? ';S.callbackUrl=' + encodeURIComponent(callbackUrl) : '');
    return 'intent:' + event + query +
      '#Intent;scheme=nostrsigner;package=com.greenart7c3.nostrsigner' +
      extras + ';end';
  }

  /** The plain link, for a signer that is not Amber and not behind an intent. */
  function plainSignerUri(template, callbackUrl) {
    return 'nostrsigner:' + encodeURIComponent(JSON.stringify(template)) +
      '?compressionType=none&returnType=event&type=sign_event&appName=Totem' +
      (callbackUrl ? '&callbackUrl=' + encodeURIComponent(callbackUrl) : '');
  }

  /** Where the signer is told to come back to: this page, nothing else. */
  function callbackUrl(origin) {
    return origin + RETURN_PATH;
  }

  /**
   * The signed event the signer app appended to this page's address.
   *
   * Read from the path, where the callback puts it - but a fragment and a query
   * are accepted too, so a signer that carries the result differently is not a
   * silent dead end at the one moment a buyer is watching.
   *
   * Returns null when the page was simply opened, so a first visit and a failed
   * return are never confused with each other.
   */
  function returnedBlob(href) {
    var stops = [RETURN_PATH, '#signed=', '?signed='];
    var raw = null;
    for (var i = 0; i < stops.length && raw === null; i += 1) {
      var at = href.indexOf(stops[i]);
      if (at >= 0) raw = href.slice(at + stops[i].length);
    }
    if (raw === null || raw === '') return null;
    // The path stop always matches first on the callback this page hands out,
    // so a signer that appends after a marker instead would have left the
    // marker glued to the front of its own answer. Peel it, rather than let the
    // other two stops be unreachable in every real return.
    for (var j = 1; j < stops.length; j += 1) {
      if (raw.indexOf(stops[j]) === 0) raw = raw.slice(stops[j].length);
    }
    return raw === '' ? null : raw;
  }

  /** Turn whatever came back into an authorization, or say why it is not one. */
  function parseEvent(raw) {
    // Only what came out of an address needs decoding. A clipboard paste is raw
    // JSON that was never encoded, and decoding it again turns a stray "%" into
    // a broken escape and the wrong diagnosis.
    var text = raw;
    if (raw.indexOf('%') >= 0) {
      try {
        text = decodeURIComponent(raw);
      } catch (error) {
        text = raw;
      }
    }
    // A signer told to skip compression but answering "Signer1..." anyway is a
    // gzip payload. Say so, rather than failing on JSON that was never JSON.
    if (text.indexOf('Signer1') === 0) {
      throw new Error('The signer app compressed its answer; this page asked it not to.');
    }
    var event;
    try {
      event = JSON.parse(text);
    } catch (error) {
      throw new Error('The signer app came back with something that is not an event.');
    }
    if (!event || typeof event !== 'object' || typeof event.sig !== 'string' ||
        typeof event.pubkey !== 'string' || event.kind !== CLAIM_KIND) {
      throw new Error('The signer app came back with the wrong kind of event.');
    }
    // totemd refuses a fifth tag and any content outright. Catching that here
    // names the signer that added something; letting it through names nothing.
    if (event.content !== '' || !Array.isArray(event.tags) || event.tags.length !== 4) {
      throw new Error('The signer app changed the authorization before signing it.');
    }
    return event;
  }

  /** The authorization this page was reopened with, if it was reopened at all. */
  function returnedEvent(href) {
    var raw = returnedBlob(href);
    return raw === null ? null : parseEvent(raw);
  }

  /** The NIP-98 header totemd reads, base64 over the event's UTF-8 bytes. */
  function authorization(event) {
    var json = JSON.stringify(event);
    var binary = '';
    var bytes = new global.TextEncoder().encode(json);
    for (var i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
    return 'Nostr ' + global.btoa(binary);
  }

  /** Prefer the server's own words: a rejected claim should say why. */
  function reason(body, fallback) {
    if (body && typeof body === 'object' && typeof body.error === 'string') return body.error;
    return fallback;
  }

  async function ask(path, init) {
    var response = await global.fetch(path, Object.assign({ cache: 'no-store' }, init));
    var body = await response.json().catch(function () { return null; });
    if (!response.ok) throw new Error(reason(body, 'Request failed (' + response.status + ')'));
    return body;
  }

  /** Ask totemd for a nonce bound to exactly the request we are about to make. */
  function challenge() {
    return ask('/api/auth/challenge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: CLAIM_PATH, method: CLAIM_METHOD, body: CLAIM_BODY }),
    });
  }

  /** Hand the signed authorization in. The nonce is single use; this is the claim. */
  function claim(event) {
    return ask(CLAIM_PATH, {
      method: CLAIM_METHOD,
      headers: { Authorization: authorization(event), 'Content-Type': 'application/json' },
      body: CLAIM_BODY,
    });
  }


  /* ---------------------------------------------------------------- screen */

  function shorten(key) {
    return key.length > 16 ? key.slice(0, 8) + '…' + key.slice(-8) : key;
  }

  function init() {
    var doc = global.document;
    var status = doc.getElementById('status');
    var button = doc.getElementById('sign');
    var hint = doc.getElementById('hint');
    var pasted = doc.getElementById('pasted');
    var manual = doc.getElementById('manual');
    var reveal = doc.getElementById('reveal');
    var waiting = null;

    function say(text, kind) {
      status.textContent = text;
      status.className = kind || '';
    }

    function stumble(error) {
      claiming = false;
      global.clearTimeout(waiting);
      hint.hidden = true;
      doc.getElementById('use-pasted').disabled = false;
      // The server's own words, never a friendly sentence over the top of them:
      // a claim that was refused has to be diagnosable while somebody watches.
      say(error && error.message ? error.message : String(error), 'bad');
      button.disabled = false;
      manual.hidden = false;
    }

    var claiming = false;
    async function finish(event) {
      if (claiming) return;
      claiming = true;
      global.clearTimeout(waiting);
      hint.hidden = true;
      button.disabled = true;
      doc.getElementById('use-pasted').disabled = true;
      say('Checking your signature…');
      try {
        await claim(event);
        doc.body.classList.add('done');
        say('This Totem is yours. Key ' + shorten(event.pubkey) + '.', 'good');
        manual.hidden = true;
      } catch (error) {
        stumble(error);
      }
    }

    async function start() {
      button.disabled = true;
      manual.hidden = true;
      say('Asking this Totem for a one-time code…');
      var uri;
      try {
        var issued = await challenge();
        var template = authTemplate(issued, Math.floor(Date.now() / 1000));
        uri = signerUri(template, callbackUrl(global.location.origin));
      } catch (error) {
        stumble(error);
        return;
      }
      say('Opening your key app…');
      // Nothing tells a web page that no app answered the link, so the offer of
      // another way in is on a timer rather than on an event that never comes.
      waiting = global.setTimeout(function () {
        hint.hidden = false;
        button.disabled = false;
        say('Waiting for your key app.');
      }, 3000);
      // If the signer really opened, this page went to the background first.
      // Without this, someone who opened Amber, thought better of it and came
      // back is told to install the app they were just looking at.
      doc.addEventListener('visibilitychange', function opened() {
        if (doc.visibilityState !== 'hidden') return;
        doc.removeEventListener('visibilitychange', opened);
        global.clearTimeout(waiting);
        hint.hidden = true;
        button.disabled = false;
        say('Approve it in your key app.');
      });
      global.location.href = uri;
    }

    button.addEventListener('click', function () { void start(); });
    // The second way home: sign with no callback, and the answer arrives on the
    // clipboard rather than in the address bar.
    reveal.addEventListener('click', async function () {
      global.clearTimeout(waiting);
      hint.hidden = true;
      manual.hidden = false;
      say('Asking for a fresh one-time code…');
      var uri;
      try {
        var issued = await challenge();
        uri = signerUri(authTemplate(issued, Math.floor(Date.now() / 1000)), null);
      } catch (error) {
        stumble(error);
        return;
      }
      say('Approve it, then come back and paste the answer here.');
      pasted.focus();
      global.location.href = uri;
    });
    doc.getElementById('use-pasted').addEventListener('click', function () {
      try {
        void finish(parseEvent(pasted.value.trim()));
      } catch (error) {
        stumble(error);
      }
    });

    // Reopened by the signer app: the answer is already in the address bar.
    // This runs last, and deliberately so. It used to return early, before any
    // handler was attached - so when the claim was refused (an expired nonce, a
    // Totem already claimed) the page showed the reason next to a button and a
    // paste box that did nothing at all. The recovery path was dead in exactly
    // the moment it was needed.
    var blob = returnedBlob(global.location.href);
    if (blob !== null) {
      try {
        void finish(parseEvent(blob));
      } catch (error) {
        stumble(error);
      }
    }
  }

  global.TotemPhoneClaim = {
    CLAIM_KIND: CLAIM_KIND,
    RETURN_PATH: RETURN_PATH,
    authTemplate: authTemplate,
    signerUri: signerUri,
    plainSignerUri: plainSignerUri,
    callbackUrl: callbackUrl,
    returnedBlob: returnedBlob,
    parseEvent: parseEvent,
    returnedEvent: returnedEvent,
    authorization: authorization,
    challenge: challenge,
    claim: claim,
    init: init,
  };

  // Tests load this file for the pure parts alone; only a real page starts.
  if (global.document) global.document.addEventListener('DOMContentLoaded', init);
})(typeof globalThis === 'undefined' ? this : globalThis);
