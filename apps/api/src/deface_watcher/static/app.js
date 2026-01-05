function $(id) {
  return document.getElementById(id);
}
function setText(el, value) {
  if (!el) return;
  el.textContent = value;
}
function show(el) {
  if (!el) return;
  el.classList.remove("hidden");
}
function hide(el) {
  if (!el) return;
  el.classList.add("hidden");
}
function clampNumber(n, fallback = 0) {
  const x = Number(n);
  return Number.isFinite(x) ? x : fallback;
}
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ---------- Elements ----------
const form = $("predict-form");
const urlInput = $("url-input");
const button = $("predict-button");

const progress = $("progress");
const progressTitle = $("progress-title");
const progressDetail = $("progress-detail");
const errorMessage = $("error-message");

const resultContainer = $("result-container");
const resultBadge = $("result-badge");
const resultStatus = $("result-status");
const resultProb = $("result-prob");
const resultUrl = $("result-url");
const resultSource = $("result-source");
const totalTime = $("total-time");

const resultText = $("result-text");
const textMeta = $("text-meta");
const sourceWarning = $("source-warning");

const stepScrape = $("step-scrape");
const stepPredict = $("step-predict");
const stepScrapeDetail = $("step-scrape-detail");
const stepPredictDetail = $("step-predict-detail");

const textCopy = $("text-copy");
const textDownload = $("text-download");
const textFullscreen = $("text-fullscreen");
const textSearch = $("text-search");

const textModal = $("text-modal");
const textModalOverlay = $("text-modal-overlay");
const textModalBody = $("text-modal-body");
const textSearchModal = $("text-search-modal");
const textCopyModal = $("text-copy-modal");
const textDownloadModal = $("text-download-modal");
const textCloseModal = $("text-close-modal");

// ---------- State ----------
let fullText = "";
let searchTerm = "";
let modalOpen = false;
let previousBodyOverflow = "";
let searchTimer = null;

const statusClassMap = {
  "Tấn công Deface": "badge-danger",
  "Bình thường": "badge-safe",
  "Không có dữ liệu": "badge-warn",
};

// ---------- UI ----------
function setLoading(isLoading) {
  if (button) {
    button.disabled = isLoading;
    button.classList.toggle("loading", isLoading);
  }
  if (progress) progress.classList.toggle("hidden", !isLoading);

  setText(progressTitle, isLoading ? "Đang xử lý" : "");
  setText(progressDetail, isLoading ? "Chuẩn bị trích xuất..." : "");
}

function resetResult() {
  hide(errorMessage);
  hide(resultContainer);
  hide(sourceWarning);

  if (resultBadge) {
    resultBadge.textContent = "--";
    resultBadge.className = "badge";
  }

  setText(resultStatus, "--");
  setText(resultProb, "--");
  setText(resultUrl, "");
  setText(resultSource, "--");
  setText(totalTime, "--");

  if (stepScrape) stepScrape.classList.remove("done");
  if (stepPredict) stepPredict.classList.remove("done");
  setText(stepScrapeDetail, "--");
  setText(stepPredictDetail, "--");

  if (resultText) resultText.innerHTML = "";
  setText(textMeta, "");

  if (textSearch) textSearch.value = "";
  if (textSearchModal) textSearchModal.value = "";
  fullText = "";
  searchTerm = "";
  closeTextModal();
}

function showError(message) {
  setText(errorMessage, message);
  show(errorMessage);
}

function buildHighlightedHtml(text, term) {
  const safeText = String(text || "");
  const safeTerm = String(term || "").trim();
  if (!safeTerm) return escapeHtml(safeText);

  const lowerText = safeText.toLowerCase();
  const lowerTerm = safeTerm.toLowerCase();

  let startIndex = 0;
  let matchIndex = lowerText.indexOf(lowerTerm, startIndex);
  let html = "";

  while (matchIndex !== -1) {
    html += escapeHtml(safeText.slice(startIndex, matchIndex));
    html += `<mark class="hit">${escapeHtml(
      safeText.slice(matchIndex, matchIndex + safeTerm.length)
    )}</mark>`;
    startIndex = matchIndex + safeTerm.length;
    matchIndex = lowerText.indexOf(lowerTerm, startIndex);
  }

  html += escapeHtml(safeText.slice(startIndex));
  return html;
}

function renderTextInto(target) {
  if (!target) return;
  const textToRender = fullText || "Không có văn bản để hiển thị.";
  target.innerHTML = buildHighlightedHtml(textToRender, searchTerm);
}

function renderText() {
  renderTextInto(resultText);
  if (modalOpen) renderTextInto(textModalBody);
}

function updateSearchTerm(value, syncTarget) {
  searchTerm = String(value || "").trim();
  if (syncTarget && syncTarget.value !== searchTerm) {
    syncTarget.value = searchTerm;
  }
  renderText();
}

function debounceSearch(value, syncTarget) {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => updateSearchTerm(value, syncTarget), 200);
}

// ---------- Clipboard / download ----------
async function copyText(content) {
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
  } catch (err) {
    console.error(err);
  }
}

function downloadFile(content, filename, type) {
  if (!content) return;
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// ---------- Modal ----------
function openTextModal() {
  if (!textModal || modalOpen) return;
  modalOpen = true;

  textModal.classList.add("is-open");
  textModal.setAttribute("aria-hidden", "false");

  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";

  if (textSearchModal) textSearchModal.value = searchTerm;
  renderTextInto(textModalBody);
  if (textSearchModal) textSearchModal.focus();
}

function closeTextModal() {
  if (!textModal || !modalOpen) return;
  modalOpen = false;

  textModal.classList.remove("is-open");
  textModal.setAttribute("aria-hidden", "true");

  document.body.style.overflow = previousBodyOverflow || "";
  renderTextInto(resultText);
}

// ---------- Main request ----------
async function checkUrl(url) {
  setLoading(true);
  resetResult();
  setText(progressDetail, "Đang trích xuất nội dung...");

  try {
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Không rõ lỗi từ máy chủ.");
    }

    // Timeline shows detailed timings
    const scrapeMs = clampNumber(data.scrape_time_ms, 0);
    const predictMs = clampNumber(data.predict_time_ms, 0);

    if (stepScrape) stepScrape.classList.add("done");
    setText(stepScrapeDetail, `Hoàn tất trong ${scrapeMs} ms`);

    if (stepPredict) stepPredict.classList.add("done");
    setText(stepPredictDetail, `Hoàn tất trong ${predictMs} ms`);

    const totalMs = clampNumber(data.total_time_ms, scrapeMs + predictMs);

    setText(resultStatus, data.status || "--");
    setText(resultProb, `${(clampNumber(data.probability, 0) * 100).toFixed(2)}%`);
    setText(resultUrl, `URL đã kiểm tra: ${data.checked_url || url}`);
    setText(resultSource, data.source || "--");
    setText(totalTime, String(totalMs));

    if (resultBadge) {
      resultBadge.textContent = data.status || "--";
      resultBadge.className = "badge";
      resultBadge.classList.add(statusClassMap[data.status] || "badge-neutral");
    }

    if (data.source && String(data.source).toLowerCase().includes("requests")) {
      show(sourceWarning);
    } else {
      hide(sourceWarning);
    }

    fullText = data.extracted_text || "(Không tìm thấy văn bản)";
    renderText();

    const truncatedLabel = data.extracted_text_truncated ? " (đã cắt)" : "";
    setText(textMeta, `Độ dài: ${fullText.length} ký tự${truncatedLabel}.`);

    show(resultContainer);
  } catch (error) {
    showError(`Lỗi: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

// ---------- Events ----------
if (form) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const url = String(urlInput?.value || "").trim();
    if (!url) {
      resetResult();
      showError("Vui lòng nhập URL hợp lệ.");
      return;
    }
    checkUrl(url);
  });
}

if (textSearch) {
  textSearch.addEventListener("input", (event) => {
    debounceSearch(event.target.value, textSearchModal);
  });
}
if (textSearchModal) {
  textSearchModal.addEventListener("input", (event) => {
    debounceSearch(event.target.value, textSearch);
  });
}

if (textCopy) textCopy.addEventListener("click", () => copyText(fullText));
if (textDownload) textDownload.addEventListener("click", () => downloadFile(fullText, "extracted_text.txt", "text/plain"));
if (textFullscreen) textFullscreen.addEventListener("click", openTextModal);

if (textModalOverlay) {
  textModalOverlay.addEventListener("click", (event) => {
    if (event.target === textModalOverlay) closeTextModal();
  });
}
if (textCloseModal) textCloseModal.addEventListener("click", closeTextModal);

if (textCopyModal) textCopyModal.addEventListener("click", () => copyText(fullText));
if (textDownloadModal) textDownloadModal.addEventListener("click", () => downloadFile(fullText, "extracted_text.txt", "text/plain"));

document.addEventListener("keydown", (event) => {
  if (modalOpen && event.key === "Escape") closeTextModal();
});
