'use strict'

const byId = id => document.getElementById(id)
const message = text => { byId('owner-message').textContent = text }
let signer = null

async function request(url, options = {}) {
  const response = await fetch(url, { cache: 'no-store', ...options })
  const value = await response.json()
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`)
  return value
}

function nip07() {
  const value = window.nostr
  return value && typeof value.getPublicKey === 'function' && typeof value.signEvent === 'function'
    ? value
    : null
}

async function waitForNip07(timeout = 3000) {
  const deadline = Date.now() + timeout
  do {
    const extension = nip07()
    if (extension) return extension
    await new Promise(resolve => setTimeout(resolve, 50))
  } while (Date.now() < deadline)
  throw new Error('No NIP-07 extension detected. Retry or use the development nsec option.')
}

function selectSigner(next, label) {
  if (signer?.clear && signer !== next) signer.clear()
  signer = next
  byId('signer-state').textContent = label
  byId('signer-logout').hidden = false
}

function forgetSigner() {
  if (signer?.clear) signer.clear()
  signer = null
  byId('signer-state').textContent = 'No signer selected.'
  byId('signer-logout').hidden = true
}

async function selectedSigner() {
  if (signer) return signer
  const extension = await waitForNip07()
  selectSigner(extension, 'NIP-07 extension detected.')
  return extension
}

async function signedRequest(path, method, body) {
  const selected = await selectedSigner()
  const challenge = await request('/api/auth/challenge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, method, body }),
  })
  const event = await selected.signEvent({
    kind: 27235,
    created_at: Math.floor(Date.now() / 1000),
    content: '',
    tags: [
      ['nonce', challenge.nonce],
      ['u', challenge.url],
      ['method', challenge.method],
      ['payload', challenge.payload],
    ],
  })
  return request(path, {
    method,
    headers: {
      'Authorization': `Nostr ${btoa(JSON.stringify(event))}`,
      'Content-Type': 'application/json',
    },
    body,
  })
}

function optional(id) {
  const value = byId(id).value.trim()
  return value || undefined
}

async function load() {
  try {
    const [owner, profile, config] = await Promise.all([
      request('/api/owner'), request('/api/metadata'), request('/api/config'),
    ])
    byId('owner-state').textContent = owner.claimed ? 'Claimed' : 'Unclaimed'
    byId('claim').hidden = owner.claimed
    byId('settings').hidden = !owner.claimed
    byId('metadata-name').value = profile.name || ''
    byId('metadata-display-name').value = profile.display_name || ''
    byId('metadata-about').value = profile.about || ''
    byId('metadata-picture').value = profile.picture || ''
    byId('metadata-website').value = profile.website || ''
    byId('config-sync').checked = Boolean(config.sync)
    byId('config-befriend').value = config.befriend
  } catch (error) {
    message(error.message)
  }
}

byId('use-extension').addEventListener('click', async event => {
  event.currentTarget.disabled = true
  try {
    const extension = await waitForNip07(5000)
    const pubkey = await extension.getPublicKey()
    selectSigner(extension, `NIP-07 signer: ${pubkey}`)
    message('Browser extension signer selected.')
  } catch (error) {
    message(error.message)
  } finally {
    event.currentTarget.disabled = false
  }
})

byId('nsec-form').addEventListener('submit', async event => {
  event.preventDefault()
  const input = byId('nsec')
  const button = event.currentTarget.querySelector('button')
  button.disabled = true
  try {
    if (!globalThis.TotemNsec) throw new Error('Local nsec signer failed to load.')
    const local = globalThis.TotemNsec.signer(input.value)
    const pubkey = await local.getPublicKey()
    input.value = ''
    selectSigner(local, `Development nsec signer: ${pubkey}`)
    message('nsec loaded in page memory only.')
  } catch (error) {
    message(error.message)
  } finally {
    button.disabled = false
  }
})

byId('signer-logout').addEventListener('click', () => {
  forgetSigner()
  message('Signer forgotten.')
})

byId('claim').addEventListener('click', async event => {
  event.currentTarget.disabled = true
  try {
    const selected = await selectedSigner()
    const pubkey = await selected.getPublicKey()
    if (!window.confirm(`Claim this Totem with ${pubkey}?`)) return
    await signedRequest('/api/owner/claim', 'POST', '{}')
    message('Totem claimed.')
    await load()
  } catch (error) {
    message(error.message)
  } finally {
    event.currentTarget.disabled = false
  }
})

byId('metadata-form').addEventListener('submit', async event => {
  event.preventDefault()
  const button = event.currentTarget.querySelector('button')
  button.disabled = true
  const metadata = {
    name: byId('metadata-name').value.trim(),
    display_name: optional('metadata-display-name'),
    about: optional('metadata-about'),
    picture: optional('metadata-picture'),
    website: optional('metadata-website'),
  }
  try {
    const result = await signedRequest('/api/metadata', 'PUT', JSON.stringify(metadata))
    byId('device-name').textContent = result.profile.name
    message('Public profile published.')
  } catch (error) {
    message(error.message)
  } finally {
    button.disabled = false
  }
})

byId('config-form').addEventListener('submit', async event => {
  event.preventDefault()
  const button = event.currentTarget.querySelector('button')
  button.disabled = true
  const config = {
    sync: byId('config-sync').checked,
    befriend: byId('config-befriend').value,
  }
  try {
    await signedRequest('/api/config', 'PUT', JSON.stringify(config))
    message('Policy saved.')
  } catch (error) {
    message(error.message)
  } finally {
    button.disabled = false
  }
})

window.addEventListener('pagehide', forgetSigner)

load()
waitForNip07().then(extension => {
  if (!signer) selectSigner(extension, 'NIP-07 extension detected.')
}).catch(error => {
  if (!signer) byId('signer-state').textContent = error.message
})
