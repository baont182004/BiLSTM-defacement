const puppeteer = require("puppeteer");

const MAX_CHARS = 20000;
const DEFAULT_TIMEOUT = 45000;

function nowMs() {
  return Date.now();
}

function normalizeText(text) {
  if (!text) {
    return "";
  }
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length > MAX_CHARS) {
    return cleaned.slice(0, MAX_CHARS);
  }
  return cleaned;
}

async function autoScroll(page) {
  await page.evaluate(async () => {
    const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const totalRounds = 6;
    const step = Math.max(window.innerHeight * 0.8, 400);
    for (let i = 0; i < totalRounds; i += 1) {
      window.scrollBy(0, step);
      await delay(450);
    }
    window.scrollTo(0, 0);
  });
}

async function waitForRender(page, errors) {
  const start = nowMs();
  const tasks = [
    page.waitForNetworkIdle({ idleTime: 1200, timeout: 30000 }).catch((err) => {
      errors.push(`network_idle:${err.message}`);
    }),
    page
      .waitForFunction(
        () =>
          document.body &&
          document.body.innerText &&
          document.body.innerText.trim().length > 200,
        { timeout: 30000 }
      )
      .catch((err) => {
        errors.push(`text_wait:${err.message}`);
      }),
  ];
  await Promise.race(tasks);
  return nowMs() - start;
}

async function extractText(page) {
  return page.evaluate(() => {
    function collectFromNode(node, parts) {
      if (!node) return;
      if (node.nodeType === Node.TEXT_NODE) {
        const value = node.textContent;
        if (value && value.trim()) {
          parts.push(value.trim());
        }
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) {
        return;
      }
      const element = node;
      if (element.shadowRoot) {
        collectFromNode(element.shadowRoot, parts);
      }
      element.childNodes.forEach((child) => collectFromNode(child, parts));
    }

    function cleanSection(element) {
      if (!element) return "";
      return element.innerText || "";
    }

    const parts = [];
    const bodyText = document.body ? document.body.innerText : "";
    if (bodyText) {
      parts.push(bodyText);
    }

    const htmlText = document.documentElement ? document.documentElement.innerText : "";
    if (htmlText && htmlText.length > bodyText.length) {
      parts.push(htmlText);
    }

    if (document.body) {
      collectFromNode(document.body, parts);
    }

    let combined = parts.join(" ");
    const nav = document.querySelector("nav");
    const footer = document.querySelector("footer");
    const navText = cleanSection(nav);
    const footerText = cleanSection(footer);
    if (navText.length > 1500) {
      combined = combined.replace(navText, " ");
    }
    if (footerText.length > 1500) {
      combined = combined.replace(footerText, " ");
    }
    return combined;
  });
}

async function getTextFromURL(url, asJson) {
  const timings = {};
  const errors = [];
  let browser;
  let page;
  let httpStatus = null;
  let finalUrl = url;
  let text = "";

  try {
    const launchStart = nowMs();
    browser = await puppeteer.launch({
      headless: "new",
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
    });
    timings.launch_ms = nowMs() - launchStart;

    page = await browser.newPage();
    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    );
    await page.setViewport({ width: 1366, height: 768 });
    await page.setDefaultNavigationTimeout(DEFAULT_TIMEOUT);
    await page.setDefaultTimeout(DEFAULT_TIMEOUT);
    await page.setExtraHTTPHeaders({
      "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    });

    await page.setRequestInterception(true);
    page.on("request", (req) => {
      const type = req.resourceType();
      if (["image", "stylesheet", "font", "media"].includes(type)) {
        req.abort();
      } else {
        req.continue();
      }
    });

    page.on("pageerror", (err) => {
      errors.push(`pageerror:${err.message}`);
    });
    page.on("error", (err) => {
      errors.push(`error:${err.message}`);
    });
    page.on("response", (response) => {
      if (response.url() === page.url()) {
        httpStatus = response.status();
      }
    });

    const navStart = nowMs();
    const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: DEFAULT_TIMEOUT });
    timings.goto_ms = nowMs() - navStart;
    if (response) {
      httpStatus = response.status();
    }

    const waitMs = await waitForRender(page, errors);
    timings.wait_render_ms = waitMs;

    let rawText = await extractText(page);
    rawText = rawText || "";

    if (rawText.trim().length < 200) {
      const scrollStart = nowMs();
      await autoScroll(page);
      timings.scroll_ms = nowMs() - scrollStart;
      await page.waitForNetworkIdle({ idleTime: 800, timeout: 12000 }).catch(() => {});
      const afterScroll = await extractText(page);
      if (afterScroll && afterScroll.trim().length > rawText.trim().length) {
        rawText = afterScroll;
      }
    }

    finalUrl = page.url();
    text = normalizeText(rawText);
  } catch (error) {
    const message = error && error.message ? error.message : String(error);
    errors.push(`fatal:${message}`);
    if (!asJson) {
      console.error(`Puppeteer error: ${message}`);
    }
    if (asJson) {
      const payload = {
        ok: false,
        text: "",
        finalUrl,
        timings,
        httpStatus,
        errors,
      };
      console.log(JSON.stringify(payload));
    }
    process.exit(1);
  } finally {
    if (browser) {
      await browser.close();
    }
  }

  if (asJson) {
    const payload = {
      ok: true,
      text,
      finalUrl,
      timings,
      httpStatus,
      errors,
    };
    console.log(JSON.stringify(payload));
  } else {
    if (errors.length) {
      console.error(`Puppeteer warnings: ${errors.join(" | ")}`);
    }
    process.stdout.write(text);
  }
}

const args = process.argv.slice(2);
const url = args[0];
const asJson = args.includes("--json");

if (!url) {
  console.error("Missing URL argument.");
  process.exit(1);
}

getTextFromURL(url, asJson);
