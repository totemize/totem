// This file requires the @types/node package to be installed
// Install it with: npm install --save-dev @types/node
import * as fs from 'fs';
import * as path from 'path';

/**
 * Converts a bitmap file to a base64 encoded string
 * @param bitmapPath - Path to the bitmap file
 * @returns Promise that resolves to the base64 encoded string
 */
export function bitmapToBase64(bitmapPath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    // Verify the file exists
    if (!fs.existsSync(bitmapPath)) {
      reject(new Error(`File not found: ${bitmapPath}`));
      return;
    }

    // Read the file as a buffer
    fs.readFile(bitmapPath, (err, data) => {
      if (err) {
        reject(new Error(`Error reading file: ${err.message}`));
        return;
      }

      // Convert buffer to base64 string
      const base64String = data.toString('base64');
      resolve(base64String);
    });
  });
}

/**
 * Synchronous version of bitmapToBase64
 * @param bitmapPath - Path to the bitmap file
 * @returns The base64 encoded string
 * @throws Error if file cannot be read
 */
export function bitmapToBase64Sync(bitmapPath: string): string {
  // Verify the file exists
  if (!fs.existsSync(bitmapPath)) {
    throw new Error(`File not found: ${bitmapPath}`);
  }

  // Read the file as a buffer
  const data = fs.readFileSync(bitmapPath);
  
  // Convert buffer to base64 string
  return data.toString('base64');
} 