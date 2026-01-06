const puppeteer = require("puppeteer");

const GOTO_TIMEOUT = Number(process.env.PUPPETEER_GOTO_TIMEOUT_MS || 12000);
const SETTLE_MS = Number(process.env.PUPPETEER_SETTLE_MS || 250);
const MAX_CHARS = Number(process.env.MAX_TEXT_LEN || 20000);

function normalizeText(text) {
  if (!text) {
    return "";
  }
  const cleaned = text.replace(/\s+/g, " ").trim();
  return cleaned.length > MAX_CHARS ? cleaned.slice(0, MAX_CHARS) : cleaned;
}

async function getText(url) {
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || undefined;
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1365, height: 768 });

  await page.setRequestInterception(true);
  page.on("request", (req) => {
    const type = req.resourceType();
    if (["image", "stylesheet", "font", "media"].includes(type)) {
      req.abort();
    } else {
      req.continue();
    }
  });

  await page.goto(url, { waitUntil: "domcontentloaded", timeout: GOTO_TIMEOUT });
  await new Promise((resolve) => setTimeout(resolve, SETTLE_MS));
  const text = await page.evaluate(() => (document.body ? document.body.innerText || "" : ""));
  await browser.close();
  return normalizeText(text);
}

const args = process.argv.slice(2);
const url = args.find((arg) => !arg.startsWith("--"));

if (!url) {
  console.error("Missing URL argument.");
  process.exit(1);
}

getText(url)
  .then((text) => {
    process.stdout.write(text);
  })
  .catch((error) => {
    const message = error && error.message ? error.message : String(error);
    console.error(`Puppeteer error: ${message}`);
    process.exit(1);
  });
