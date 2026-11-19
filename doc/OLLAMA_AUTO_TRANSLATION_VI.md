# Giai đoạn 2 — Ollama cho dịch manga hoàn toàn tự động

Ollama được triển khai như một **translator độc lập** trong luồng **Normal Translation**:
phát hiện chữ → OCR → **Ollama** → xóa chữ (inpaint) → chèn chữ (render) → Editor.

Chức năng này **không sửa** luồng OCR Workspace thủ công của giai đoạn 1.

## Yêu cầu

- Ollama đã cài trên cùng máy tính chạy MangaEditor.
- Đã tải model văn bản, ví dụ: `ollama pull qwen3:4b`.
- Kiểm tra trong PowerShell: `ollama list`; nếu Ollama chưa mở thì dùng `ollama serve`.
- Ứng dụng MangaEditor được cài thư viện và chạy từ nhánh `feat/ollama-auto-translation` (kế thừa Phase 1).

## Thiết lập trong giao diện

1. Vào **Settings → Basic Settings → Translator**.
2. Chọn **Ollama (Local · Qwen3)**.
3. Trong nhóm translator, kiểm tra các trường:
   - **Ollama model**: `qwen3:4b` (phải khớp với tên trong `ollama list`).
   - **Ollama API URL**: `http://127.0.0.1:11434/v1`.
   - **Ollama: disable thinking**: bật (mặc định, giảm phần suy luận không cần thiết khi dịch).
   - **Ollama: streaming response**: tắt (mặc định; có thể bật sau khi thử nghiệm).
4. Trở về **Normal Translation**, nhấn **Kiểm tra Ollama**. Thông báo kết nối thành công và tên model sẽ xuất hiện bên cạnh nút.
5. Chọn ngôn ngữ đích **VIN**, chọn detector/OCR/inpainter/renderer như trước.
6. Thêm toàn bộ ảnh hoặc thư mục chương truyện, đặt output folder rồi chọn **Normal Translation → Start Translation**.
7. Khi hoàn thành, mở toàn bộ trang trong Editor. Tính năng nhiều trang và resume của Phase 1 vẫn được giữ nguyên.

## Lưu ý cấu hình

- **Không cần** OpenAI API Key, OpenAI Model hay OpenAI API Base.
- Không sửa `OPENAI_* ` trong `.env`; Ollama có **cấu hình độc lập** được lưu trong cài đặt dự án.
- `qwen3:4b` là **model văn bản**, chỉ nhận các vùng chữ đã nhận dạng OCR; nó không tự đọc ảnh, xóa chữ hay vẽ chữ. Các bước đó vẫn dùng bộ xử lý của MangaEditor.
- API URL chỉ chấp nhận `http://localhost`, `http://127.0.0.1` hoặc `http://[::1]` với hậu tố `/v1`. Không thể vô tình gửi manga sang API bên ngoài trong chế độ Ollama.
- Nút thử kết nối gọi `GET /v1/models` trên một luồng riêng, không phát sinh dịch và không tải mô hình qua mạng ngoài.
- Nếu model chưa có: `ollama pull <tên-model>`. Nếu không thấy server: mở Ollama hoặc thử `ollama serve`.
- Giới hạn retry mặc định của Ollama là **3 lần**, tránh vòng lặp vô tận khi server không khả dụng. Cài đặt retry CLI cụ thể vẫn được tôn trọng.
- Thay đổi model, API URL hoặc tuỳ chọn thinking tại Settings rồi thử kết nối lại trước khi dịch.
- `ollama_streaming` mặc định tắt để ổn định cho các phản hồi JSON nhiều vùng thoại; bật được nếu máy và model hỗ trợ.

## Nếu bạn đã có MangaEditor_Phase1 trên Windows

Sao lưu các thư mục dữ liệu/JSON cần giữ, dừng ứng dụng rồi trong PowerShell:

```powershell
cd "D:\app\New folder\MangaEditerV2\MangaEditor_Phase1"
git fetch origin
git checkout -b feat/ollama-auto-translation origin/feat/ollama-auto-translation
uv sync --locked --no-default-groups --group cpu
.\Win-Start.bat
```

Lưu ý: `git checkout` không xoá dữ liệu chưa theo dõi nhưng có thể bị từ chối nếu file nguồn đã bị sửa tại máy; hãy `git status` trước khi chuyển nhánh. Bạn không cần chuyển nhánh hoặc cài đặt lại nếu đang dùng mã nguồn từ thư mục khác và chọn clone riêng.
