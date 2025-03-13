import { bitmapToBase64, bitmapToBase64Sync } from './utils';
import * as net from 'net';

// Example path to a bitmap file
const image_path = '/tmp/totem.png';

try {
  const action = 'display_image';
  const image_format = 'png';
  const request = { action, image_format, image_path };

  const client = net.createConnection({ path: '/tmp/eink_service.sock' }, () => {
    console.log('Connected to server!');
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