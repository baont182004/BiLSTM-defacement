const puppeteer = require("puppeteer");
const fs = require("fs");
const path = require("path");

const START_ID = 41416014;
const OUTPUT_FILE = path.resolve(__dirname, "..", "..", "ml", "data", "urls", "defacement_url.txt");
const NAV_TIMEOUT_MS = 20000;
const CAPTCHA_TIMEOUT_MS = 120000;
const BETWEEN_IDS_DELAY_MS = 200;
const ERROR_DELAY_MS = 1000;

function loadExistingDomains(filePath) {
  const existing = new Set();
  if (!fs.existsSync(filePath)) {
    return existing;
  }
  const fileContent = fs.readFileSync(filePath, "utf-8");
  fileContent.split("\n").forEach((line) => {
    const domain = line.trim();
    if (domain) {
      existing.add(domain);
    }
  });
  return existing;
}

async function getDomainFromPage(page) {
  return page.evaluate(() => {
    const listItems = Array.from(document.querySelectorAll("li"));
    const entry = listItems.find((node) => node.textContent.includes("Domain:"));
    if (!entry) return null;
    const text = entry.textContent;
    const parts = text.split("Domain:");
    if (parts.length < 2) return null;
    return parts[1].split("IP address:")[0].trim() || null;
  });
}

async function waitForCaptcha(page) {
  const hasCaptcha = await page.$('img[src*="captcha"]');
  if (!hasCaptcha) {
    return;
  }
  console.log("CAPTCHA detected. Please solve it in the browser window.");
  await page.waitForFunction(
    () => !document.querySelector('img[src*="captcha"]'),
    { timeout: CAPTCHA_TIMEOUT_MS }
  );
  console.log("CAPTCHA cleared. Resuming scan.");
}

async function scanZoneH() {
  const existingDomains = loadExistingDomains(OUTPUT_FILE);
  if (!fs.existsSync(OUTPUT_FILE)) {
    fs.mkdirSync(path.dirname(OUTPUT_FILE), { recursive: true });
  }

  console.log(`Loaded ${existingDomains.size} existing domains.`);
  console.log(`Scanning backward from ID ${START_ID}. Press Ctrl+C to stop.`);

  const browser = await puppeteer.launch({
    headless: false,
    slowMo: 50,
    defaultViewport: null,
    args: ["--start-maximized"],
  });

  const page = await browser.newPage();

  let fetchedCount = 0;
  let currentId = START_ID;

  while (currentId >= 1) {
    const url = `https://www.zone-h.org/mirror/id/${currentId}`;
    console.log(`\n[added: ${fetchedCount}] scanning ID ${currentId}`);

    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT_MS });
      await waitForCaptcha(page);

      const extracted = await getDomainFromPage(page);
      if (!extracted) {
        console.log("No domain found on page.");
      } else if (existingDomains.has(extracted)) {
        console.log(`Skipped existing: ${extracted}`);
      } else {
        fs.appendFileSync(OUTPUT_FILE, extracted + "\n");
        existingDomains.add(extracted);
        fetchedCount += 1;
        console.log(`Saved new domain: ${extracted}`);
      }
    } catch (err) {
      const message = err && err.message ? err.message.split("\n")[0] : String(err);
      console.log(`Error on ID ${currentId}: ${message}`);
      await new Promise((resolve) => setTimeout(resolve, ERROR_DELAY_MS));
    } finally {
      currentId -= 1;
      await new Promise((resolve) => setTimeout(resolve, BETWEEN_IDS_DELAY_MS));
    }
  }

  console.log("Reached ID 1. Scan complete.");
  await browser.close();
}

process.on("SIGINT", async () => {
  console.log("\nReceived SIGINT. Closing browser...");
  process.exit(0);
});

scanZoneH();
