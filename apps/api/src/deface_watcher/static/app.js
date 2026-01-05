const form = document.getElementById("predict-form");
const urlInput = document.getElementById("url-input");
const button = document.getElementById("predict-button");
const progress = document.getElementById("progress");
const progressTitle = document.getElementById("progress-title");
const progressDetail = document.getElementById("progress-detail");
const errorMessage = document.getElementById("error-message");
const resultContainer = document.getElementById("result-container");

const resultBadge = document.getElementById("result-badge");
const resultStatus = document.getElementById("result-status");
const resultProb = document.getElementById("result-prob");
const resultUrl = document.getElementById("result-url");
const resultSource = document.getElementById("result-source");
const scrapeTime = document.getElementById("scrape-time");
const predictTime = document.getElementById("predict-time");
const totalTime = document.getElementById("total-time");
const resultText = document.getElementById("result-text");
const textMeta = document.getElementById("text-meta");
const sourceWarning = document.getElementById("source-warning");
const stepScrape = document.getElementById("step-scrape");
const stepPredict = document.getElementById("step-predict");
const stepScrapeDetail = document.getElementById("step-scrape-detail");
const stepPredictDetail = document.getElementById("step-predict-detail");

const textCopy = document.getElementById("text-copy");
const textDownload = document.getElementById("text-download");
const textFullscreen = document.getElementById("text-fullscreen");
const textSearch = document.getElementById("text-search");
const textModal = document.getElementById("text-modal");
const textModalOverlay = document.getElementById("text-modal-overlay");
const textModalBody = document.getElementById("text-modal-body");
const textSearchModal = document.getElementById("text-search-modal");
const textCopyModal = document.getElementById("text-copy-modal");
const textDownloadModal = document.getElementById("text-download-modal");
const textCloseModal = document.getElementById("text-close-modal");

let fullText = "";
let searchTerm = "";
let modalOpen = false;
let previousBodyOverflow = "";
let searchTimer = null;

const statusClassMap = {
  "T?n công Deface": "badge-danger",
  "B?nh thư?ng": "badge-safe",
  "Không đ? d? li?u": "badge-warn",
};

function setLoading(isLoading) {
  button.disabled = isLoading;
  button.classList.toggle("loading", isLoading);
  progress.classList.toggle("hidden", !isLoading);
  progressTitle.textContent = isLoading ? "Đang x? l?" : "";
  progressDetail.textContent = isLoading ? "Chu?n b? cào d? li?u..." : "";
}

function resetResult() {
  errorMessage.classList.add("hidden");
  resultContainer.classList.add("hidden");
  sourceWarning.classList.add("hidden");
  resultBadge.textContent = "--";
  resultBadge.className = "badge";
  resultText.textContent = "";
  textMeta.textContent = "";
  stepScrape.classList.remove("done");
  stepPredict.classList.remove("done");
  stepScrapeDetail.textContent = "--";
  stepPredictDetail.textContent = "--";
  textSearch.value = "";
  textSearchModal.value = "";
  fullText = "";
  searchTerm = "";
  closeTextModal();
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.classList.remove("hidden");
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildHighlightedHtml(text, term) {
  if (!term) {
    return escapeHtml(text);
  }
  const lowerText = text.toLowerCase();
  const lowerTerm = term.toLowerCase();
  let startIndex = 0;
  let matchIndex = lowerText.indexOf(lowerTerm, startIndex);
  let html = "";

  while (matchIndex !== -1) {
    html += escapeHtml(text.slice(startIndex, matchIndex));
    html += `<mark class="hit">${escapeHtml(
      text.slice(matchIndex, matchIndex + term.length)
    )}</mark>`;
    startIndex = matchIndex + term.length;
    matchIndex = lowerText.indexOf(lowerTerm, startIndex);
  }

  html += escapeHtml(text.slice(startIndex));
  return html;
}

function renderTextInto(target) {
  const textToRender =
    fullText || (target === textModalBody ? "Không có văn b?n đ? hi?n th?." : "");
  target.innerHTML = buildHighlightedHtml(textToRender, searchTerm);
}

function renderText() {
  renderTextInto(resultText);
  if (modalOpen) {
    renderTextInto(textModalBody);
  }
}

function updateSearchTerm(value, syncTarget) {
  searchTerm = value.trim();
  if (syncTarget && syncTarget.value !== searchTerm) {
    syncTarget.value = searchTerm;
  }
  renderText();
}

function debounceSearch(value, syncTarget) {
  if (searchTimer) {
    clearTimeout(searchTimer);
  }
  searchTimer = setTimeout(() => {
    updateSearchTerm(value, syncTarget);
  }, 250);
}

async function copyText(content) {
  if (!content) {
    return;
  }
  try {
    await navigator.clipboard.writeText(content);
  } catch (error) {
    console.error(error);
  }
}

function downloadFile(content, filename, type) {
  if (!content) {
    return;
  }
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

function openTextModal() {
  if (modalOpen) {
    return;
  }
  modalOpen = true;
  textModal.classList.add("is-open");
  textModal.setAttribute("aria-hidden", "false");
  previousBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  textSearchModal.value = searchTerm;
  renderTextInto(textModalBody);
  if (textSearchModal) {
    textSearchModal.focus();
  }
}

function closeTextModal() {
  if (!modalOpen) {
    return;
  }
  modalOpen = false;
  textModal.classList.remove("is-open");
  textModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = previousBodyOverflow;
  renderTextInto(resultText);
}

async function checkUrl(url) {
  setLoading(true);
  resetResult();
  progressDetail.textContent = "Đang g?i Puppeteer...";

  try {
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Không r? l?i t? máy ch?.");
    }

    progressDetail.textContent = "Đang d? đoán BiLSTM...";
    stepScrape.classList.add("done");
    stepScrapeDetail.textContent = `Hoàn t?t trong ${data.scrape_time_ms} ms`;
    stepPredict.classList.add("done");
    stepPredictDetail.textContent = `Hoàn t?t trong ${data.predict_time_ms} ms`;

    resultStatus.textContent = data.status;
    resultProb.textContent = (data.probability * 100).toFixed(2) + "%";
    resultUrl.textContent = `URL đ? ki?m tra: ${data.checked_url}`;
    resultSource.textContent = data.source;
    scrapeTime.textContent = data.scrape_time_ms;
    predictTime.textContent = data.predict_time_ms;
    totalTime.textContent = data.total_time_ms;

    resultBadge.textContent = data.status;
    resultBadge.classList.add(statusClassMap[data.status] || "badge-neutral");

    if (data.source && data.source.toLowerCase().includes("requests")) {
      sourceWarning.classList.remove("hidden");
    }

    fullText = data.extracted_text || "(Không t?m th?y văn b?n)";
    renderText();

    const truncatedLabel = data.extracted_text_truncated ? " (đ? c?t)" : "";
    textMeta.textContent = `Đ? dài: ${fullText.length} k? t?${truncatedLabel}.`;

    resultContainer.classList.remove("hidden");
  } catch (error) {
    showError(`L?i: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) {
    resetResult();
    showError("Vui l?ng nh?p URL h?p l?.");
    return;
  }
  checkUrl(url);
});

textSearch.addEventListener("input", (event) => {
  debounceSearch(event.target.value, textSearchModal);
});

textSearchModal.addEventListener("input", (event) => {
  debounceSearch(event.target.value, textSearch);
});

textCopy.addEventListener("click", () => {
  copyText(fullText);
});

textDownload.addEventListener("click", () => {
  downloadFile(fullText, "extracted_text.txt", "text/plain");
});

textFullscreen.addEventListener("click", () => {
  openTextModal();
});

textModalOverlay.addEventListener("click", (event) => {
  if (event.target === textModalOverlay) {
    closeTextModal();
  }
});
textCloseModal.addEventListener("click", closeTextModal);

textCopyModal.addEventListener("click", () => {
  copyText(fullText);
});

textDownloadModal.addEventListener("click", () => {
  downloadFile(fullText, "extracted_text.txt", "text/plain");
});

document.addEventListener("keydown", (event) => {
  if (modalOpen && event.key === "Escape") {
    closeTextModal();
  }
});
