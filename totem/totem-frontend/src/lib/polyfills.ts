// Ensure crypto polyfill is available globally
import cryptoBrowserify from 'crypto-browserify';
import { Buffer } from 'buffer';

// Polyfill crypto
if (typeof window !== 'undefined' && !window.crypto) {
  // @ts-ignore - Adding crypto to the window object
  window.crypto = cryptoBrowserify;
}

// Polyfill Buffer
if (typeof window !== 'undefined') {
  // @ts-ignore - Adding Buffer to the window object
  window.Buffer = Buffer;
}

export {}; 