# MangaEditor Manual Edition — Hướng dẫn sử dụng và kiểm tra tốc độ

Bản thử nghiệm trên nhánh **feat/manual-edition-fast-typesetting**, kế thừa Phase 1 + 2 mà không xóa các tệp dự án hay gộp PR vào \`main\`.

## Mục tiêu

Ứng dụng tập trung vào việc **tự dịch và biên tập manga**:
1. OCR để lấy chữ và vị trí vùng thoại.
2. Bạn tự dịch (hoặc dịch ở một công cụ khác), nhập/dán bản dịch.
3. Điều chỉnh ngắt dòng, font, mask; sửa nền với Paint/Clone.
4. Render ảnh đã dịch, quản lý các trang trong Editor và xuất cả chương.

Các dịch vụ dịch AI, Prompt Manager và màn hình API được **ẩn khỏi thanh điều hướng mặc định**, không bị xóa. Có thể mở giao diện đầy đủ bằng biến môi trường \`MANGA_EDITOR_UI=full\`.

## Sử dụng nhanh

- Mở app → **OCR Workspace** (mặc định).
- **Thêm thư mục dự án** và **Scan OCR Only** nếu chương chưa được quét OCR.
- Chọn một hàng trong bảng OCR; nội dung gốc được tô sáng trên preview.
- Gõ bản dịch vào ô **Bản dịch vùng đang chọn**. **Enter** tạo ngắt dòng cứng; wrap tự động do ô hẹp không tạo \`[BR]\`.
- Dùng nút **↵ Xuống dòng**, **Vùng tiếp →**, **Vùng chưa dịch tiếp theo**; tiến độ **đã dịch/tổng vùng** hiển thị bên cạnh.
- **Ctrl+S** hoặc **Save JSON** để lưu. Dùng Copy All OCR/Paste Batch nếu muốn dịch hàng loạt theo ID.
- **Render trang đang chọn** để xem kết quả; **Render trang đã đổi** cho chương; mở **Editor** để điều chỉnh font, lớp mask, Paint, Clone và xuất ảnh.

Ví dụ ô biên tập:

\`\`\`text
Đúng rồi
đó!
\`\`\`

Dữ liệu được lưu thành \`Đúng rồi[BR]đó!\`; dấu \`[BR]\` xuất hiện chỉ bởi Enter/chỉnh sửa có chủ ý, không phải bởi text wrap trong ô biên tập. Bản sửa ngăn auto-wrap làm thay đổi dữ liệu đã có ở PR #2 vẫn được giữ lại.

## Tốc độ LaMa

- Đánh dấu **Inpainting nhanh (LaMa ≤1024px)** nếu bạn ưu tiên tốc độ. Thiết lập này chỉ áp dụng cho **lượt render từ OCR Workspace**; không ghi đè kích thước LaMa đã lưu trong Settings.
- Tắt đánh dấu trên nếu cần xử lý ở kích thước cao hơn để giữ chi tiết nền. Độ phân giải khác nhau có chữ ký cache khác nhau.
- Sau lần xử lý LaMa đầu tiên, app lưu ảnh nền inpaint và tệp metadata \`*.manual-cache.json\` cạnh ảnh nền. Sửa lời thoại/font không thay đổi chữ ký của nền sạch → render lại không gọi LaMa khi mask còn như cũ.
- Thay ảnh nguồn, mask, model, kích thước hoặc precision → chữ ký đổi → **phải inpaint lại** để tránh chữ gốc còn sót.
- Cache LaMa cũ không có metadata xác minh sẽ được dựng lại một lần. Đừng xóa ảnh nền nếu muốn tăng tốc lần render sau.
- Model vẫn xử lý lần đầu; đây không phải tối ưu tốc độ cho tất cả trường hợp. Nếu dùng CPU, thời gian inpaint lần đầu vẫn có thể lâu. Thử trên cùng trang để đo chênh lệch thực tế.

## Cập nhật dự án trên Windows

Đóng MangaEditor, sao lưu JSON và kiểm tra thay đổi chưa commit:

\`\`\`powershell
cd "D:\app\New folder\MangaEditerV2\MangaEditor_Phase1"
git status --short
git fetch origin feat/manual-edition-fast-typesetting
git switch -c feat/manual-edition-fast-typesetting FETCH_HEAD
uv sync --locked --no-default-groups --group cpu
.\Win-Start.bat
\`\`\`

Nếu nhánh này đã có trên máy, thay lệnh \`git switch -c ...\` bằng:

\`\`\`powershell
git switch feat/manual-edition-fast-typesetting
git pull --ff-only origin feat/manual-edition-fast-typesetting
\`\`\`

Để **chuyển tạm sang giao diện AI đầy đủ** trong cửa sổ PowerShell hiện tại:

\`\`\`powershell
$env:MANGA_EDITOR_UI = "full"
.\Win-Start.bat
\`\`\`

Để quay về Manual Edition:

\`\`\`powershell
Remove-Item Env:MANGA_EDITOR_UI -ErrorAction SilentlyContinue
.\Win-Start.bat
\`\`\`

## Lưu ý

- OCR Workspace và Editor vẫn là hai vùng làm việc; bộ điều khiển và JSON tương thích bản cũ.
- Không xóa Python/Ollama/API modules ngay, vì dịch tự động và thủ công đang dùng chung một số thành phần.
- Các tối ưu chưa thực hiện trong lần này: thay thế hoàn toàn giao diện Editor; bỏ hẳn dịch AI khỏi bản build; GPU benchmark; inpaint chia nhóm thông minh.
- Cần kiểm tra với tập ảnh manga thực tế và trên cấu hình CPU/GPU của bạn trước khi công nhận chất lượng render.
