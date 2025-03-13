# Bitmap to Base64 Converter

A simple TypeScript utility to convert bitmap images to base64 encoded strings.

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   npm install
   ```
3. Build the project:
   ```
   npm run build
   ```

## Usage

The utility provides both asynchronous and synchronous functions for converting bitmap files to base64 strings.

### Asynchronous Usage

```typescript
import { bitmapToBase64 } from './bitmapToBase64';

async function example() {
  try {
    const base64String = await bitmapToBase64('./path/to/image.bmp');
    console.log(base64String);
  } catch (error) {
    console.error('Error:', error);
  }
}
```

### Synchronous Usage

```typescript
import { bitmapToBase64Sync } from './bitmapToBase64';

try {
  const base64String = bitmapToBase64Sync('./path/to/image.bmp');
  console.log(base64String);
} catch (error) {
  console.error('Error:', error);
}
```

## How It Works

The utility reads the bitmap file as a binary buffer and then converts it to a base64 encoded string using Node.js's built-in Buffer API.

## Notes

- This utility works with any bitmap file format (.bmp, .png, .jpg, etc.)
- The resulting base64 string can be used in data URLs, for example:
  ```
  const dataUrl = `data:image/bmp;base64,${base64String}`;
  ``` 