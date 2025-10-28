

const puppeteer = require('puppeteer');
const fs = require('fs');

async function getAndSaveDefacedUrl() {
    const browser = await puppeteer.launch({ headless: "new" });
    const page = await browser.newPage();

    try {
        await page.setUserAgent(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        );

        const url = 'https://www.zone-h.org/mirror/id/41471125';
        console.log(`Đang truy cập vào trang: ${url}`);

        await page.goto(url, { waitUntil: 'networkidle2' });

        const xpathSelector = "//li[contains(., 'Domain:')]";
        console.log(`Đang chờ selector XPath "${xpathSelector}"...`);

        await page.waitForSelector(`xpath/${xpathSelector}`);

        const extractedText = await page.evaluate((xpath) => {
            const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            return result.singleNodeValue ? result.singleNodeValue.textContent : null;
        }, xpathSelector);

        if (extractedText) {

            const defacedUrl = extractedText.split('Domain:')[1].split('IP address:')[0].trim();

            fs.appendFileSync('urls.txt', defacedUrl + '\n');

            console.log(`✅ THÀNH CÔNG! Đã lưu URL sạch: ${defacedUrl} vào tệp urls.txt`);
        } else {
            console.log('Không tìm thấy element nào khớp.');
        }

    } catch (error) {
        console.error('Đã xảy ra lỗi:', error);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

getAndSaveDefacedUrl();