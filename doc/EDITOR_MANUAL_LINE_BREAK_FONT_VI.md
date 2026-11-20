# Gõ xuống dòng thủ công và chỉnh font trực tiếp trong Editor

## Cập nhật

Trong bản Phase 2 (nhánh `feat/ollama-auto-translation`), cửa sổ Rich Text nổi đã có một thanh **Font / Size / ↵ Xuống dòng** ngay bên dưới ô nhập nội dung. Tab **Property Editor** cũng đưa **Style Settings** lên trước phần OCR/Text Content để có thể tìm thấy Font, Font Size, Stroke, Line Spacing, Alignment và Direction.

- **↵ Xuống dòng**: đặt con trỏ vào vị trí muốn tách câu rồi bấm nút hoặc bấm **Enter**. Khi lưu, ngắt dòng được ghi vào trường `translation` dưới dạng `[BR]` và lưu vào `translation_rich` dạng hai đoạn. Ảnh được render theo các dòng bạn chọn chứ không buộc phải kéo dài bóng thoại.
- **Font / Size** trên cửa sổ Rich Text: chỉnh **toàn bộ vùng thoại đang chọn**, sử dụng lịch sử Undo của Editor và giữ nguyên các vùng khác. Nút `F` và `S` trong hàng phím tắt Rich Text vẫn dùng cho **phạm vi ký tự được bôi đen** (có thể ưu tiên kiểu chữ cục bộ hơn font chung của vùng).
- **Property Editor → Style Settings**: cho phép chỉnh thêm màu chữ, viền, khoảng cách dòng/chữ, căn lề và hướng chữ ngang/dọc. Mục này vốn đã có nhưng trước đây nằm rất sâu phía dưới các ô OCR, khiến dễ tưởng là thiếu.

## Ví dụ

Đặt con trỏ trước chữ `đó!`:

```text
Đúng rồi
đó!
```

Bản JSON sẽ lưu nội dung tương ứng `Đúng rồi[BR]đó!`.

## Lưu ý

- Nút xuống dòng tạo ngắt dòng *cứng*; nếu font quá lớn đến mức mỗi dòng vẫn vượt khỏi bóng thoại, hãy giảm Size chứ không kéo giãn khung.
- Font được chọn phải hỗ trợ dấu tiếng Việt. Với font riêng của một đoạn ký tự, `S`/`F` thuộc rich text có thể ghi đè style chung của vùng, cần chỉnh đoạn đó nếu muốn nhất quán.
- Ảnh đã Export từ bản trước không tự cập nhật; mở lại **trang nguồn** qua Editor và Export lại.
- Phải Save Editor State/JSON để giữ chỉnh sửa sau khi đóng ứng dụng.

## Cập nhật trên Windows

Đóng MangaEditor, sao lưu JSON trước khi cập nhật:

```powershell
cd "D:\app\New folder\MangaEditerV2\MangaEditor_Phase1"
git status --short
git fetch origin
git switch feat/ollama-auto-translation
git pull --ff-only origin feat/ollama-auto-translation
.\Win-Start.bat
```

Nếu `git status --short` cho biết có file mã nguồn sửa tại máy, sao lưu/commit trước khi pull. Không cần cài lại Ollama hay model OCR.
