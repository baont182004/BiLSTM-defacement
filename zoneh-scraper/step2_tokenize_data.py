import json
import numpy as np
import os
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences

# --- CẤU HÌNH ---
INPUT_FILE = 'rawData.json'
OUTPUT_X = 'X_data.npy'
OUTPUT_Y = 'y_data.npy'
OUTPUT_TOKENIZER = 'tokenizer.json'

# Thông số từ bài báo
MAX_LENGTH = 128

# Kích thước từ vựng (chọn một số đủ lớn, 20.000 là phổ biến)
VOCAB_SIZE = 20000 
OOV_TOKEN = "<OOV>" # Token cho các từ chưa biết (Out-of-Vocabulary)
# --------------------

print(f"--- BẮT ĐẦU BƯỚC 2: TOKENIZATION & TIỀN XỬ LÝ ---")

# --- 1. Kiểm tra và Đọc file rawData.json ---
if not os.path.exists(INPUT_FILE):
    print(f"LỖI: Không tìm thấy tệp '{INPUT_FILE}'.")
    print("Vui lòng đảm bảo bạn đã chạy script 'step1_extract_text.py' thành công và tệp 'rawData.json' nằm trong cùng thư mục.")
    exit()

print(f"Đang tải tệp đầu vào: {INPUT_FILE}")
try:
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
except json.JSONDecodeError:
    print(f"LỖI: Tệp '{INPUT_FILE}' bị lỗi định dạng JSON. Không thể đọc.")
    exit()

if not data:
    print(f"LỖI: Tệp '{INPUT_FILE}' bị rỗng. Không có dữ liệu để xử lý.")
    exit()

print(f"Đã tải thành công {len(data)} mẫu dữ liệu.")

# --- 2. Tách văn bản và nhãn ---
# Lọc ra các mẫu có văn bản (không bị rỗng)
valid_data = [item for item in data if item.get('text') and item.get('label') is not None]
texts = [item['text'] for item in valid_data]
labels = [item['label'] for item in valid_data]

if len(texts) != len(data):
    print(f"Cảnh báo: Đã loại bỏ {len(data) - len(texts)} mẫu bị thiếu văn bản hoặc nhãn.")

print(f"Tổng số mẫu hợp lệ để xử lý: {len(texts)}")

# --- 3. Tokenization & Ánh xạ số nguyên ---
print(f"Đang xây dựng từ điển (Tokenizer) với {VOCAB_SIZE} từ...")
# num_words=VOCAB_SIZE: Chỉ giữ lại 20.000 từ phổ biến nhất
tokenizer = Tokenizer(num_words=VOCAB_SIZE, oov_token=OOV_TOKEN)

# Xây dựng từ vựng (ví dụ: 'hacked' -> 1, 'website' -> 2)
# Đây là bước "đi một vòng"
tokenizer.fit_on_texts(texts)

# Chuyển văn bản thành chuỗi các số nguyên
# Đây là bước "quay lại"
sequences = tokenizer.texts_to_sequences(texts)
print("Đã chuyển văn bản thành chuỗi số nguyên.")

# --- 4. Padding & Truncating (Chuẩn hóa độ dài 128) ---
print(f"Đang chuẩn hóa độ dài chuỗi thành {MAX_LENGTH} từ...")
# padding='post': Thêm số 0 vào CUỐI câu nếu thiếu
# truncating='post': Cắt bỏ từ CUỐI câu nếu thừa (để giữ 128 từ đầu)
padded_data = pad_sequences(
    sequences, 
    maxlen=MAX_LENGTH, 
    padding='post', 
    truncating='post'
)

# Chuyển nhãn thành mảng NumPy
labels_array = np.array(labels)

print("Chuẩn hóa hoàn tất.")

# --- 5. Lưu kết quả ---
print(f"Đang lưu dữ liệu đã xử lý ra tệp...")

# Lưu dữ liệu X và Y
np.save(OUTPUT_X, padded_data)
np.save(OUTPUT_Y, labels_array)

# Lưu lại tokenizer
# Đây là bước CỰC KỲ QUAN TRỌNG
# Chúng ta cần chính xác tokenizer này để xử lý các URL mới ở giai đoạn phát hiện
tokenizer_json = tokenizer.to_json()
with open(OUTPUT_TOKENIZER, 'w', encoding='utf-8') as f:
    f.write(json.dumps(tokenizer_json, ensure_ascii=False))

print("\n--- HOÀN TẤT TIỀN XỬ LÝ (BƯỚC 2) ---")
print(f"Đã lưu dữ liệu X (Văn bản đã xử lý) vào: {OUTPUT_X} (Shape: {padded_data.shape})")
print(f"Đã lưu dữ liệu Y (nhãn) vào: {OUTPUT_Y} (Shape: {labels_array.shape})")
print(f"Đã lưu Từ điển (Tokenizer) vào: {OUTPUT_TOKENIZER}")
print(f"\nGiờ bạn đã sẵn sàng cho Bước 3: Huấn luyện mô hình.")