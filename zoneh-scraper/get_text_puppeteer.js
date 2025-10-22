/*
 * SCRIPT PHỤ TRỢ (CHUYÊN GIA JS)
 * - Nhận 1 URL từ dòng lệnh.
 * - Dùng Puppeteer để cào dữ liệu (chạy JS).
 * - In văn bản thô ra stdout (cho Python).
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
            timeout: 20000 // 20 giây
        });

        const rawText = await page.evaluate(() => document.body.innerText);
        const cleanedText = rawText.replace(/(\r\n|\n|\r|\t)/gm, " ").replace(/\s+/g, ' ').trim();

        // In kết quả ra stdout để Python bắt được
        console.log(cleanedText);

    } catch (error) {
        // In lỗi ra stderr để Python bắt được
        console.error(`Lỗi Puppeteer khi cào ${url}: ${error.message}`);
        process.exit(1);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

// Lấy URL từ tham số dòng lệnh
const url = process.argv[2];
if (!url) {
    console.error('Lỗi: Không có URL nào được cung cấp.');
    process.exit(1);
}

getTextFromURL(url);