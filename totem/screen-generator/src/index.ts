import { chromium } from "playwright";
import fs from 'fs';
import path from 'path';

// Create a variable to store the interval ID for cleanup
let intervalId: NodeJS.Timeout;
let browser: any = null;

// Initialize browser asynchronously 
const initBrowser = async () => {
    browser = await chromium.launch();
    console.log('Browser launched');
    return browser;
};

const main = async () => {
    if (!browser) {
        browser = await initBrowser();
    }
    
    console.log('Starting screenshot capture...');
    try {
        const startTime = Date.now();
        const context = await browser.newContext();
        const page = await context.newPage();
        console.log('Page created');
        
        await page.setViewportSize({ width: 240, height: 480 });
        console.log('Viewport size set to 240x480');
        
        console.log('Navigating to totem');
        await page.goto('https://localhost:5173', { waitUntil: 'networkidle' });
        console.log('Page loaded');
        
        // Take screenshot directly with Playwright
        const screenshotBuffer = await page.screenshot({ type: 'png' });
        console.log('Screenshot captured');
        
        const endTime = Date.now();
        console.log(`Time taken: ${endTime - startTime}ms`);
        
        // Use a relative path instead of __dirname to avoid linter errors
        const outputPath = '/tmp/totem.png';
        fs.writeFileSync(outputPath, screenshotBuffer);
        console.log(`Screenshot saved to ${path.resolve(outputPath)}`);
    } catch (error) {
        console.error('Screenshot capture error:', error);
    }
};

// Setup clean shutdown
const cleanup = async () => {
    console.log('Cleaning up...');
    if (intervalId) {
        clearInterval(intervalId);
        console.log('Screenshot interval cleared');
    }
    
    if (browser) {
        await browser.close();
        console.log('Browser closed');
    }
    
    process.exit(0);
};

// Handle termination signals
process.on('SIGINT', () => {
    cleanup().catch(console.error);
});
process.on('SIGTERM', () => {
    cleanup().catch(console.error);
});

// Start the process
const start = async () => {
    // Initialize browser first
    await initBrowser();
    
    // Run once immediately
    await main().catch(error => {
        console.error('Error in initial screenshot capture:', error);
    });
    
    console.log('Starting screenshot capture interval (every 10 seconds)');
    intervalId = setInterval(() => {
        main().catch(error => {
            console.error('Error in scheduled screenshot capture:', error);
        });
    }, 10000);
};

// Start the application
start().catch(error => {
    console.error('Failed to start application:', error);
});