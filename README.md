Hướng dẫn sử dụng mã nguồn

Cài đặt các thư viện Python cần thiết:

pip install -r requirements.txt


Cài đặt các gói JavaScript (dùng cho Puppeteer):

npm install


Chạy 3 script huấn luyện mô hình (nếu muốn huấn luyện lại từ đầu):

python step1_extract_text.py
python step2_tokenize_data.py
python step3_train_model.py


Ghi chú: Trong mã nguồn trên GitHub đã bao gồm sẵn mô hình đã được huấn luyện và file tokenizer. Nếu chỉ cần chạy demo, có thể bỏ qua bước 3 và chuyển thẳng sang bước 4.

Khởi động API để sử dụng mô hình:

python app.py