# Sửa lỗi [BR] tự chèn, cắt giữa chữ khi render manga

Đã tích hợp trên nhánh **feat/ollama-auto-translation** của dự án MangaEditor (Phase 2).

## Nguyên nhân

Trước bản sửa, hàm tính bố cục sẽ tự gán `region.translation = ...` sau khi chia dòng theo khung OCR. Luồng **Render → Save JSON** sau đó ghi lại chính giá trị đã ngắt dòng bằng `[BR]`, làm bảng **Translation** xuất hiện những chuỗi như:

```text
Đúng r[BR]ồi đó![BR]
```

Nếu render lại, những dấu xuống dòng tự động cũ bị hiểu nhầm là xuống dòng **bắt buộc**, dẫn đến chữ bị chia giữa một từ.

## Quy tắc mới

- **Translation / Translation Raw:** Giữ nguyên nội dung do dịch/OCR hoặc người dùng nhập; dàn chữ tự động không ghi đè.
- **Layout chỉ dùng khi render:** Thuật toán vẫn tạo `[BR]` trong bản làm việc tạm, tính font/khung và vẽ vào ảnh, sau đó trả lại bản dịch gốc trước khi lưu JSON.
- **Enter / ↵ Xuống dòng của bạn:** Là xuống dòng cố ý; tiếp tục được lưu dưới dạng `[BR]` và trong tài liệu `translation_rich` khi cần.
- **Render lặp lại:** Không tích lũy dấu `[BR]` mới. Khi gặp lỗi render, dữ liệu nguồn vẫn được khôi phục.
- **File JSON được render theo cơ chế mới:** Đánh dấu `render_text_source_version: 2`; lần render sau có thể chạy lại quy tắc thay thế chữ theo cách đúng, không nhận nhầm bố cục tạm là bản dịch đã chỉnh sửa.

### Dữ liệu cũ

Khi đọc JSON **đã từng render bằng bản trước**, chương trình có bước sửa thận trọng cho các ca có thể nhận ra:

- `Đúng r[BR]ồi đó![BR]` → `Đúng rồi đó!`
- Giữ `Đúng rồi[BR]đó!` nếu đó là ngắt dòng giữa các từ.
- Không sửa vùng chưa dịch tiếng Việt hoặc đoạn `translation_rich` có kiểu chữ riêng.
- Không tự sửa JSON ở ổ đĩa khi chỉ mở trang; việc ghi lại được thực hiện qua **Save JSON/Render**.

**Giới hạn:** Trong dữ liệu cũ không có cờ ghi lại ai đã chèn mỗi `[BR]`, nên không thể khôi phục chính xác mọi dấu ngắt sai mà không có nguy cơ xóa dấu xuống dòng của người dùng. Hãy kiểm tra lại những dòng cũ còn bất thường.

## Cập nhật và sử dụng

1. Sao lưu thư mục JSON dự án, ví dụ `D:\app\New folder\maga_02\manga_translator_work\json`.
2. Đóng MangaEditor.
3. Trong PowerShell:

```powershell
cd "D:\app\New folder\MangaEditerV2\MangaEditor_Phase1"
git status --short
git fetch origin
git switch feat/ollama-auto-translation
git pull --ff-only origin feat/ollama-auto-translation
.\Win-Start.bat
```

4. OCR Workspace: mở lại trang lỗi. Nếu bảng Translation còn dấu `[BR]` giữa chữ, chỉnh đúng một lần rồi **Save JSON**. Nếu muốn xuống dòng thủ công, giữ `Đúng rồi[BR]đó!`.
5. Dùng **Render Current / Render All (force)** để tạo lại ảnh đã xuất. Ảnh cũ không tự cập nhật.
6. Với Editor: mở ảnh nguồn, sửa/đặt xuống dòng bằng Enter hoặc `↵ Xuống dòng`, lưu JSON rồi xuất ảnh mới.

Nếu `git status --short` có file mã nguồn đã sửa ở máy, sao lưu hoặc commit trước khi pull. Bản cập nhật không yêu cầu tải lại model Ollama/LaMa.
