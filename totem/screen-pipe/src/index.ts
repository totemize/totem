import { bitmapToBase64, bitmapToBase64Sync } from './utils';
import * as net from 'net';
import sharp from 'sharp';

// Example path to a bitmap file
const png_path = '/tmp/totem.png';
const bmp_path = '/tmp/totem.bmp';

//convert the png image to a bmp image to the bmp path 
const convertPngToBmp = async () => {
  const pngImage = sharp(png_path);
  await pngImage.toFile(bmp_path);
}

convertPngToBmp();

const action = 'display_image';
const request = { action,  bmp_path };

const main = async () => {
  try {
    const client = net.createConnection({ path: '/tmp/eink_service.sock' }, () => {
      console.log('Connected to server!');
      console.log(`Writing request: ${JSON.stringify(request)}`); 
      client.write(JSON.stringify(request));
    });
  
    client.on('data', (data) => {
      console.log('Received:', data.toString());
      client.end();
    });
  
    client.on('end', () => {
      console.log('Disconnected from server');
    });
  
  } catch (error) {
    console.error('Error in sync example:', error);
  }

}

setInterval(main, 10000);  
