import { bitmapToBase64, bitmapToBase64Sync } from './utils';
import * as net from 'net';
import sharp from 'sharp';
import * as fs from 'fs';

// Example path to a bitmap file
const png_path = '/tmp/totem.png';
const bmp_path = '/tmp/totem.bmp';

// Counter for tracking updates to control periodic full refreshes
let updateCounter = 0;
const FULL_REFRESH_INTERVAL = 20; // Match the server-side setting

// Convert the png image to a bmp image to the bmp path 
const convertPngToBmp = async () => {
  try {
    const pngImage = sharp(png_path);
    await pngImage.toFile(bmp_path);
    console.log(`Converted ${png_path} to ${bmp_path}`);
  } catch (error) {
    console.error('Error converting PNG to BMP:', error);
  }
}

// Function to read a file and convert it to base64
const fileToBase64 = (filePath: string): string => {
  try {
    const fileData = fs.readFileSync(filePath);
    return fileData.toString('base64');
  } catch (error) {
    console.error(`Error reading file ${filePath}:`, error);
    return '';
  }
}

const main = async () => {
  try {
    // First convert PNG to BMP if needed
    await convertPngToBmp();
    
    // Read the BMP file and convert to base64
    const imageData = fileToBase64(bmp_path);
    if (!imageData) {
      console.error('Failed to read image data');
      return;
    }
    
    // Increment update counter
    updateCounter++;
    
    // Determine if we need a full refresh based on counter
    const needsFullRefresh = updateCounter >= FULL_REFRESH_INTERVAL;
    
    // Reset counter if we're doing a full refresh
    if (needsFullRefresh) {
      console.log(`Triggering full refresh after ${updateCounter} updates`);
      console.error(`FULL REFRESH TRIGGERED after ${updateCounter} updates`); // Use error log to ensure visibility
      updateCounter = 0;
    }
    
    // Create the proper request format
    const request = {
      action: 'display_image',
      image_data: imageData,
      image_format: 'bmp',
      force_full_refresh: needsFullRefresh // Set to true on the Nth update
    };
    
    // Always output the full refresh status and counter for debugging
    console.log(`Full refresh: ${request.force_full_refresh ? 'Yes' : 'No'}, Counter: ${updateCounter}`);
    console.error(`COUNTER: ${updateCounter}, FULL REFRESH: ${request.force_full_refresh ? 'Yes' : 'No'}`); // Use error log to ensure visibility
    
    console.log('Connecting to e-ink service...');
    
    const client = net.createConnection({ path: '/tmp/eink_service.sock' }, () => {
      console.log('Connected to server!');
      console.log(`Sending display_image request with ${imageData.length} bytes of base64 data`);
      client.write(JSON.stringify(request));
    });
  
    client.on('data', (data) => {
      console.log('Received:', data.toString());
      client.end();
    });
  
    client.on('end', () => {
      console.log('Disconnected from server');
    });
    
    client.on('error', (error) => {
      console.error('Socket connection error:', error);
    });
  
  } catch (error) {
    console.error('Error in main function:', error);
  }
}

// Run once immediately
main();

// Then run every 10 seconds
setInterval(main, 10000);  
