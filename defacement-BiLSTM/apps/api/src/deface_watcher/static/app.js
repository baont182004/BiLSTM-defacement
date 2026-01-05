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
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.classList.remove("hidden");
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

    const extractedText = data.extracted_text || "(Không tìm thấy văn bản)";
    resultText.textContent = extractedText;

    const truncatedLabel = data.extracted_text_truncated ? " (đã giới hạn)" : "";
    textMeta.textContent = `Độ dài: ${extractedText.length} ký tự${truncatedLabel}`;

    if (data.tokenized_sequence_included && Array.isArray(data.tokenized_sequence)) {
      const preview = data.tokenized_sequence.slice(0, 48).join(", ");
      tokenPreview.textContent = preview || "--";
    } else {
      tokenPreview.textContent = "Chưa bật debug hoặc RETURN_TOKENS.";
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
