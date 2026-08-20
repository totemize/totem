/*! Browser-only nsec signing: nostr-tools 2.23.1 (Unlicense), @noble/curves and @noble/hashes 2.0.1 (MIT), @scure/base 2.0.0 (MIT). */
import { finalizeEvent, getPublicKey } from 'nostr-tools/pure'
import { decode } from 'nostr-tools/nip19'

function decodeSecret(value) {
  try {
    const decoded = decode(value.trim())
    if (decoded.type === 'nsec' && decoded.data instanceof Uint8Array && decoded.data.length === 32) {
      return decoded.data
    }
  } catch (_) {
    // Keep the entered secret out of parser error messages.
  }
  throw new Error('Invalid nsec')
}

globalThis.TotemNsec = Object.freeze({
  signer(value) {
    const key = decodeSecret(value)
    let cleared = false
    const secret = () => {
      if (cleared) throw new Error('nsec signer is logged out')
      return key
    }
    return Object.freeze({
      getPublicKey: async () => getPublicKey(secret()),
      signEvent: async event => finalizeEvent(event, secret()),
      clear() {
        key.fill(0)
        cleared = true
      },
    })
  },
})
