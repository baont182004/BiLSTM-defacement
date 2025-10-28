/*
 * - Nhận 1 URL từ dòng lệnh.
 * - Dùng Puppeteer để cào dữ liệu (chạy JS).
 * - In văn bản thô ra stdout 
 */
const puppeteer = require('puppeteer');

async function getTextFromURL(url) {
    let browser;
    try {
        browser = await puppeteer.launch({
            headless: "new",
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        const page = await browser.newPage();

        await page.setRequestInterception(true);
        page.on('request', (req) => {
            if (['image', 'stylesheet', 'font', 'media'].includes(req.resourceType())) {
                req.abort();
            } else {
                req.continue();
            }
        });

        await page.goto(url, {
            waitUntil: 'networkidle2',
            timeout: 20000
        });

        const rawText = await page.evaluate(() => document.body.innerText);
        const cleanedText = rawText.replace(/(\r\n|\n|\r|\t)/gm, " ").replace(/\s+/g, ' ').trim();

        console.log(cleanedText);

    } catch (error) {
        console.error(`Lỗi Puppeteer khi cào ${url}: ${error.message}`);
        process.exit(1);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

const url = process.argv[2];
if (!url) {
    console.error('Lỗi: Không có URL nào được cung cấp.');
    process.exit(1);
}

getTextFromURL(url);