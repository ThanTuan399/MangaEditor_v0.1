# Bản sửa: Chữ tiếng Việt bị xếp dọc & chữ nguồn còn sót trong Editor

Bản sửa này nằm trên nhánh `feat/ollama-auto-translation` (kế thừa Phase 1).

## Triệu chứng

- Ô Rich Text hiển thị đúng câu tiếng Việt, nhưng chữ trên ảnh bị dựng dọc/tách ký tự.
- Một số bóng thoại vẫn nhìn thấy chữ cũ bên dưới bản dịch, nhất là sau **Scan OCR Only → nhập bản dịch → Render / Editor**.

## Đã thay đổi

### 1. Hướng chữ cho tiếng Việt

MangaEditor trước đây có thể lưu `direction = "v"` từ vùng OCR Nhật Bản vào JSON. Khi ngôn ngữ đích là `VIN` và đã có bản dịch, hướng dọc *kế thừa từ OCR* được tự chuyển sang `h` để chữ tiếng Việt hiển thị ngang.

- Editor, backend đo khung chữ và trình render dùng thống nhất một hướng.
- Nếu bạn chủ động chọn hướng dọc trong Editor, cờ `direction_user_override` sẽ giữ lựa chọn đó, kể cả sau khi lưu và mở lại.
- Vùng chưa dịch hoặc bản tiếng Nhật không bị tự thay đổi hướng.

### 2. Xóa chữ gốc còn sót

Một số trang OCR-only có JSON chứa vùng chữ nhưng thiếu `mask_raw` hoặc thiếu mask cho vài vùng đã được dịch. Khi tải dự án, phần mềm sẽ phát hiện *vùng đã dịch mà không có vùng mask tương ứng* và bổ sung từ **polygon dòng chữ OCR**; các vùng chưa dịch và phần ảnh nằm ngoài các polygon này không bị thêm vào mask.

- Khi mask được sửa, sidecar ảnh đã inpaint trước đó không được dùng lại vì có thể còn sót chữ cũ.
- Với OCR Workspace Render, ảnh inpaint mới được lưu lại để mở trong Editor.
- Tính năng không thể tự sửa mọi trường hợp OCR không phát hiện chữ hoặc nhận diện polygon sai. Những vùng này vẫn cần chỉnh mask thủ công.

## Cập nhật bản vá trên Windows

Đóng MangaEditor. Mở PowerShell:

```powershell
cd "D:\app\New folder\MangaEditerV2\MangaEditor_Phase1"
git status --short
git fetch origin
git switch feat/ollama-auto-translation
git pull --ff-only origin feat/ollama-auto-translation
.\Win-Start.bat
```

Nếu `git status --short` liệt kê file bạn đã tự sửa, lưu lại thay đổi trước khi pull để không mất dữ liệu.

## Sửa lại trang đã render trước đó

**Nếu đang dùng OCR Workspace:** giữ JSON gốc và bản dịch, không chạy lại Scan OCR Only. Dùng **Render All** (bắt buộc render mới thay vì dùng cache) hoặc render lại trang lỗi. Sau đó mở Editor xem và lưu/xuất lại trang.

**Nếu đang dùng Editor:** mở **ảnh nguồn gốc** trong dự án (không mở PNG/JPG đã xuất với chữ lỗi). Chờ inpainting hoàn tất nếu nền đang được tái tạo, kiểm tra chữ hiển thị ngang, rồi **Save JSON** và **Export** lại ảnh. Bản ảnh xuất cũ sẽ không được tự cập nhật.

Nếu đã có hướng dọc được cố ý chọn trong Editor từ bản cũ mà không có cờ `direction_user_override`, cần chọn lại hướng dọc một lần để phần mềm ghi nhận đó là lựa chọn thủ công.

## Trạng thái kiểm chứng

GitHub Actions Windows / Python 3.12: **636 passed, 3 skipped**. Các trường hợp đã kiểm thử gồm: hướng dọc OCR sang tiếng Việt; giữ lựa chọn hướng dọc thủ công; không sửa chữ chưa dịch; dựng mask còn thiếu; bảo toàn mask đã đủ; bỏ qua polygon hỏng; nạp mask mới trong Editor. Chưa kiểm thử trực tiếp với tập ảnh và file JSON cá nhân của người dùng.
