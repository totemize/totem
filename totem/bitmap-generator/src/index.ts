import { chromium } from "playwright";
import fs from 'fs';
import path from 'path';

// Create a variable to store the interval ID for cleanup
let intervalId: NodeJS.Timeout;

const main = async () => {
    console.log('Starting screenshot capture...');
    try {
        const browser = await chromium.launch();
        console.log('Browser launched');
        
        const context = await browser.newContext();
        const page = await context.newPage();
        console.log('Page created');
        
        await page.setViewportSize({ width: 240, height: 480 });
        console.log('Viewport size set to 240x480');
        
        console.log('Navigating to zombo.com...');
        await page.goto('https://zombo.com/', { waitUntil: 'networkidle' });
        console.log('Page loaded');
        
        // Take screenshot directly with Playwright
        const screenshotBuffer = await page.screenshot({ type: 'png' });
        console.log('Screenshot captured');
        
        await browser.close();
        console.log('Browser closed');
        
        // Use a relative path instead of __dirname to avoid linter errors
        const outputPath = '/tmp/totem.png';
        fs.writeFileSync(outputPath, screenshotBuffer);
        console.log(`Screenshot saved to ${path.resolve(outputPath)}`);
    } catch (error) {
        console.error('Error during screenshot capture:', error);
    }
};

// Setup clean shutdown
const cleanup = () => {
    console.log('Cleaning up...');
    if (intervalId) {
        clearInterval(intervalId);
        console.log('Screenshot interval cleared');
    }
    process.exit(0);
};

// Handle termination signals
process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

console.log('Starting screenshot capture interval (every 10 seconds)');
intervalId = setInterval(main, 10000);

// Run once immediately
main().catch(error => {
    console.error('Error in initial screenshot capture:', error);
});