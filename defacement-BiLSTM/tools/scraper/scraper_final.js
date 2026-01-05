const puppeteer = require('puppeteer');
const fs = require('fs');

async function getAndSaveSequentialDefacedUrls() {

    const START_ID = 41416014;
    const OUTPUT_FILE = 'defacement_url.txt';


    const browser = await puppeteer.launch({
        headless: false,
        slowMo: 50,
        defaultViewport: null,
        args: ['--start-maximized']
    });

    const page = await browser.newPage();

    const existingDomains = new Set();
    if (fs.existsSync(OUTPUT_FILE)) {
        console.log(`📄 Tìm thấy ${OUTPUT_FILE}, sẽ đọc và ghi nối tiếp.`);
        const fileContent = fs.readFileSync(OUTPUT_FILE, 'utf-8');
        fileContent.split('\n').forEach(line => {
            const domain = line.trim();
            if (domain) {
                existingDomains.add(domain);
            }
        });
        console.log(`🔍 Đã tải ${existingDomains.size} domain đã có vào bộ nhớ đệm.`);
    } else {
        console.log(`🆕 Tạo mới tệp ${OUTPUT_FILE}.`);
    }


    let fetchedCount = 0;
    let currentId = START_ID;

    console.log(`🚀 Bắt đầu quét lùi từ ID ${START_ID} và ghi vào ${OUTPUT_FILE}...`);
    console.log("   Nhấn Ctrl+C để dừng.");


    while (currentId >= 1) {
        const url = `https://www.zone-h.org/mirror/id/${currentId}`;
        console.log(`\n[Đã thêm mới: ${fetchedCount}] 📉 Quét ID: ${currentId}`);

        try {
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });

            const isCaptcha = await page.$('img[src*="captcha"]');
            if (isCaptcha) {
                console.log('⏳ Phát hiện CAPTCHA — vui lòng nhập tay và nhấn "Gửi" trong trình duyệt.');
                await page.waitForFunction(
                    () => !document.querySelector('img[src*="captcha"]'),
                    { timeout: 120000 }
                );
                console.log('👍 CAPTCHA đã qua — tiếp tục...');
            }

            const domainText = await page.evaluate(() => {
                const el = [...document.querySelectorAll("li")].find(e =>
                    e.textContent.includes("Domain:")
                );
                return el ? el.textContent : null;
            });

            if (domainText) {
                const extracted = domainText.split('Domain:')[1].split('IP address:')[0].trim();
                if (extracted) {
                    if (!existingDomains.has(extracted)) {
                        fs.appendFileSync(OUTPUT_FILE, extracted + '\n');
                        existingDomains.add(extracted);
                        fetchedCount++;
                        console.log(`✅ Đã lưu (MỚI): ${extracted}`);
                    } else {
                        console.log(`🔄 Bỏ qua (Đã tồn tại): ${extracted}`);
                    }

                } else {
                    console.log('⚠️ Domain trích xuất bị rỗng.');
                }
            } else {
                console.log('🚫 Không tìm thấy mục "Domain:" trên trang (ID có thể không tồn tại).');
            }

        } catch (err) {
            console.log(`❌ Lỗi với ID ${currentId}: ${err.message.split('\n')[0]}`);

            await new Promise(resolve => setTimeout(resolve, 1000));
        } finally {

            currentId--;

            await new Promise(resolve => setTimeout(resolve, 200));
        }
    }

    console.log('\n🏁 Đã quét đến ID 1.');
    await browser.close();
    console.log(`🎉 Script đã hoàn tất quét lùi.`);
}


process.on('SIGINT', async () => {
    console.log("\n🛑 Đã nhận tín hiệu dừng (Ctrl+C). Đang đóng trình duyệt...");

    process.exit(0);
});

getAndSaveSequentialDefacedUrls();