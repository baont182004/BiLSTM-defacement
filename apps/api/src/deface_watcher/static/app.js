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
const tokenPreview = document.getElementById("token-preview");
const sourceWarning = document.getElementById("source-warning");
const stepScrape = document.getElementById("step-scrape");
const stepPredict = document.getElementById("step-predict");
const stepScrapeDetail = document.getElementById("step-scrape-detail");
const stepPredictDetail = document.getElementById("step-predict-detail");

const textCopy = document.getElementById("text-copy");
const textDownload = document.getElementById("text-download");
const textFullscreen = document.getElementById("text-fullscreen");
const textSearch = document.getElementById("text-search");
const textPrev = document.getElementById("text-prev");
const textNext = document.getElementById("text-next");
const textMatchCount = document.getElementById("text-match-count");
const textTop = document.getElementById("text-top");
const textShowFull = document.getElementById("text-show-full");
const textViewer = document.querySelector(".text-viewer");
const textModal = document.getElementById("text-modal");
const textModalOverlay = document.getElementById("text-modal-overlay");
const textModalBody = document.getElementById("text-modal-body");
const textSearchModal = document.getElementById("text-search-modal");
const textCopyModal = document.getElementById("text-copy-modal");
const textDownloadModal = document.getElementById("text-download-modal");
const textCloseModal = document.getElementById("text-close-modal");

const tokenCopy = document.getElementById("token-copy");
const tokenDownload = document.getElementById("token-download");
const tokenToggleView = document.getElementById("token-toggle-view");
const tokenStats = document.getElementById("token-stats");
const tokenGrid = document.getElementById("token-grid");

const PREVIEW_LIMIT = 5000;
const MAX_LENGTH = 128;
let fullText = "";
let previewText = "";
let searchTerm = "";
let currentMatches = [];
let currentMatchIndex = -1;
let activeMatch = null;
let tokenSequence = null;
let tokenRawView = false;
let modalOpen = false;
let previousBodyOverflow = "";

const statusClassMap = {
  "Tấn công Deface": "badge-danger",
  "Bình thường": "badge-safe",
  "Không đủ dữ liệu": "badge-warn",
};

function setLoading(isLoading) {
  button.disabled = isLoading;
  button.classList.toggle("loading", isLoading);
  progress.classList.toggle("hidden", !isLoading);
  progressTitle.textContent = isLoading ? "Đang xử lý" : "";
  progressDetail.textContent = isLoading ? "Chuẩn bị cào dữ liệu..." : "";
}

function resetResult() {
  errorMessage.classList.add("hidden");
  resultContainer.classList.add("hidden");
  sourceWarning.classList.add("hidden");
  resultBadge.textContent = "--";
  resultBadge.className = "badge";
  tokenPreview.textContent = "--";
  resultText.textContent = "";
  textMeta.textContent = "";
  stepScrape.classList.remove("done");
  stepPredict.classList.remove("done");
  stepScrapeDetail.textContent = "--";
  stepPredictDetail.textContent = "--";
  textSearch.value = "";
  textSearchModal.value = "";
  textMatchCount.textContent = "0/0";
  textShowFull.checked = false;
  fullText = "";
  previewText = "";
  searchTerm = "";
  currentMatches = [];
  currentMatchIndex = -1;
  activeMatch = null;
  tokenSequence = null;
  tokenRawView = false;
  tokenStats.classList.add("hidden");
  tokenGrid.classList.add("hidden");
  tokenPreview.classList.remove("hidden");
  tokenPreview.classList.remove("token-callout");
  tokenToggleView.disabled = false;
  tokenToggleView.textContent = "Xem JSON";
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

function getActiveTextContainer() {
  return modalOpen ? textModalBody : resultText;
}

function updateMatchCount() {
  if (!currentMatches.length) {
    textMatchCount.textContent = "0/0";
    return;
  }
  textMatchCount.textContent = `${currentMatchIndex + 1}/${currentMatches.length}`;
}

function setActiveMatch(index) {
  if (!currentMatches.length) {
    currentMatchIndex = -1;
    updateMatchCount();
    return;
  }
  if (activeMatch) {
    activeMatch.classList.remove("active");
  }
  currentMatchIndex = index;
  activeMatch = currentMatches[currentMatchIndex];
  activeMatch.classList.add("active");
  activeMatch.scrollIntoView({ block: "center", behavior: "smooth" });
  updateMatchCount();
}

function getDisplayText() {
  return textShowFull.checked ? fullText : previewText;
}

function renderTextInto(target, displayText) {
  const textToRender =
    displayText || (target === textModalBody ? "Không có văn bản để hiển thị." : "");
  target.innerHTML = buildHighlightedHtml(textToRender, searchTerm);

  if (target === getActiveTextContainer()) {
    currentMatches = Array.from(target.querySelectorAll("mark.hit"));
    activeMatch = null;
    if (currentMatches.length) {
      setActiveMatch(0);
    } else {
      currentMatchIndex = -1;
      updateMatchCount();
    }
  }
}

function renderText() {
  const displayText = getDisplayText();
  renderTextInto(resultText, displayText);
  if (modalOpen) {
    renderTextInto(textModalBody, displayText);
  }
}

function updateSearchTerm(value, syncTarget) {
  searchTerm = value.trim();
  if (syncTarget && syncTarget.value !== searchTerm) {
    syncTarget.value = searchTerm;
  }
  renderText();
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
  renderTextInto(textModalBody, getDisplayText());
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
  renderTextInto(resultText, getDisplayText());
}

function renderTokenStats(tokens) {
  const length = tokens.length;
  const nonZero = tokens.filter((value) => value !== 0).length;
  const paddingPct = length ? (((length - nonZero) / length) * 100).toFixed(1) : "0.0";
  tokenStats.innerHTML = `
    <span>MAX_LENGTH=${MAX_LENGTH}</span>
    <span>non_zero=${nonZero}</span>
    <span>padding=${paddingPct}%</span>
  `;
}

function renderTokenGrid(tokens) {
  tokenGrid.innerHTML = "";
  const fragment = document.createDocumentFragment();
  tokens.forEach((value) => {
    const chip = document.createElement("span");
    chip.className = `token-chip${value === 0 ? " token-zero" : ""}`;
    chip.textContent = value;
    fragment.appendChild(chip);
  });
  tokenGrid.appendChild(fragment);
}

async function checkUrl(url) {
  setLoading(true);
  resetResult();
  progressDetail.textContent = "Đang gọi Puppeteer...";

  try {
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Không rõ lỗi từ máy chủ.");
    }

    progressDetail.textContent = "Đang dự đoán BiLSTM...";
    stepScrape.classList.add("done");
    stepScrapeDetail.textContent = `Hoàn tất trong ${data.scrape_time_ms} ms`;
    stepPredict.classList.add("done");
    stepPredictDetail.textContent = `Hoàn tất trong ${data.predict_time_ms} ms`;

    resultStatus.textContent = data.status;
    resultProb.textContent = (data.probability * 100).toFixed(2) + "%";
    resultUrl.textContent = `URL đã kiểm tra: ${data.checked_url}`;
    resultSource.textContent = data.source;
    scrapeTime.textContent = data.scrape_time_ms;
    predictTime.textContent = data.predict_time_ms;
    totalTime.textContent = data.total_time_ms;

    resultBadge.textContent = data.status;
    resultBadge.classList.add(statusClassMap[data.status] || "badge-neutral");

    if (data.source && data.source.toLowerCase().includes("requests")) {
      sourceWarning.classList.remove("hidden");
    }

    fullText = data.extracted_text || "(Không tìm thấy văn bản)";
    previewText =
      fullText.length > PREVIEW_LIMIT
        ? `${fullText.slice(0, PREVIEW_LIMIT)}\n\n... (đang xem preview) ...`
        : fullText;
    renderText();

    const truncatedLabel = data.extracted_text_truncated ? " (đã cắt)" : "";
    textMeta.textContent = `Độ dài: ${fullText.length} ký tự${truncatedLabel}. Dùng ô tìm kiếm để highlight.`;

    if (Array.isArray(data.tokenized_sequence)) {
      tokenSequence = data.tokenized_sequence;
      renderTokenStats(tokenSequence);
      renderTokenGrid(tokenSequence);
      tokenStats.classList.remove("hidden");
      tokenGrid.classList.remove("hidden");
      tokenPreview.classList.add("hidden");
      tokenPreview.classList.remove("token-callout");
      tokenToggleView.disabled = false;
      tokenToggleView.textContent = "Xem JSON";
      tokenPreview.textContent = JSON.stringify(tokenSequence, null, 2);
    } else {
      tokenSequence = null;
      tokenStats.classList.add("hidden");
      tokenGrid.classList.add("hidden");
      tokenPreview.classList.remove("hidden");
      tokenPreview.classList.add("token-callout");
      tokenToggleView.disabled = true;
      tokenPreview.textContent =
        "Chưa có tokenized_sequence. Bật RETURN_TOKENS=1 để xem.\nWindows PowerShell: $env:RETURN_TOKENS=1\nLinux/macOS: export RETURN_TOKENS=1";
    }

    resultContainer.classList.remove("hidden");
  } catch (error) {
    showError(`Lỗi: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) {
    resetResult();
    showError("Vui lòng nhập URL hợp lệ.");
    return;
  }
  checkUrl(url);
});

textSearch.addEventListener("input", (event) => {
  updateSearchTerm(event.target.value, textSearchModal);
});

textSearchModal.addEventListener("input", (event) => {
  updateSearchTerm(event.target.value, textSearch);
});

textPrev.addEventListener("click", () => {
  if (!currentMatches.length) {
    return;
  }
  const nextIndex =
    (currentMatchIndex - 1 + currentMatches.length) % currentMatches.length;
  setActiveMatch(nextIndex);
});

textNext.addEventListener("click", () => {
  if (!currentMatches.length) {
    return;
  }
  const nextIndex = (currentMatchIndex + 1) % currentMatches.length;
  setActiveMatch(nextIndex);
});

textTop.addEventListener("click", () => {
  if (textViewer) {
    textViewer.scrollTop = 0;
  }
});

textShowFull.addEventListener("change", () => {
  renderText();
});

textCopy.addEventListener("click", () => {
  const content = textShowFull.checked ? fullText : previewText;
  copyText(content);
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
  const content = textShowFull.checked ? fullText : previewText;
  copyText(content);
});

textDownloadModal.addEventListener("click", () => {
  downloadFile(fullText, "extracted_text.txt", "text/plain");
});

document.addEventListener("keydown", (event) => {
  if (modalOpen && event.key === "Escape") {
    closeTextModal();
  }
});

tokenCopy.addEventListener("click", () => {
  if (!tokenSequence) {
    copyText(tokenPreview.textContent);
    return;
  }
  const content = tokenRawView
    ? JSON.stringify(tokenSequence)
    : tokenSequence.join(" ");
  copyText(content);
});

tokenDownload.addEventListener("click", () => {
  if (!tokenSequence) {
    return;
  }
  downloadFile(
    JSON.stringify(tokenSequence, null, 2),
    "tokenized_sequence.json",
    "application/json"
  );
});

tokenToggleView.addEventListener("click", () => {
  if (!tokenSequence) {
    return;
  }
  tokenRawView = !tokenRawView;
  if (tokenRawView) {
    tokenGrid.classList.add("hidden");
    tokenPreview.classList.remove("hidden");
    tokenToggleView.textContent = "Xem Grid";
  } else {
    tokenGrid.classList.remove("hidden");
    tokenPreview.classList.add("hidden");
    tokenToggleView.textContent = "Xem JSON";
  }
});
