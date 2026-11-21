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
- Nhập văn bản thuần vào ô **Nội dung bản dịch · Không dàn chữ**. Cột **Translation** và ô nhập không hiển thị mã `[BR]` trong file cũ; **Enter chuyển vùng thoại tiếp theo**, còn khi dán nhiều dòng, hệ thống tự ghép thành câu văn. Ngắt dòng, font và vị trí chữ chỉ được chỉnh trong **Editor**.
- Dùng **Vùng tiếp →**, **Vùng chưa dịch tiếp theo** để di chuyển nhanh; tiến độ **đã dịch/tổng vùng** hiển thị bên cạnh. Nút **↵ Xuống dòng** không còn ở OCR Workspace.
- **Tự lưu (mặc định bật):** sau 1,5 giây không gõ, ứng dụng tự lưu JSON và giữ bản sao `.ocr_workspace.bak`. Có thể tắt bằng ô **Tự lưu bản dịch**. **Ctrl+S** hoặc **Save JSON** vẫn lưu tức thì. Dùng Copy All OCR/Paste Batch nếu muốn dịch hàng loạt theo ID.
- **Render trang đang chọn** để xem kết quả; **Render trang đã đổi** cho chương; mở **Editor** để điều chỉnh font, lớp mask, Paint, Clone và xuất ảnh.

Ví dụ, file cũ có `Đúng rồi[BR]đó!` sẽ hiển thị dưới dạng **Đúng rồi đó!** ở OCR Workspace. Khi chỉ xem và chuyển vùng, **dữ liệu JSON cũ và định dạng Rich Text không bị sửa**. Nếu bạn sửa câu đó, chương trình lưu lại bản dịch thuần không chứa `[BR]`; định dạng cũ của riêng vùng này cần được chỉnh lại trong Editor.

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

## Chương manga đã chỉnh sửa từ trước

- Các dấu `[BR]` của ảnh đã render **chỉ được ẩn khỏi giao diện dịch**; không xóa khỏi file khi mở chương. Editor vẫn nhận đúng nội dung cũ để tiếp tục trình bày.
- Khi có thể, giao diện ghép những mảnh từ bị chia bởi `[BR]`, ví dụ `Ya[BR]mamoto` nếu trong OCR gốc có chữ `YAMAMOTO`; các ranh giới từ không chắc sẽ dùng dấu cách để tránh gộp sai.
- Bảng **Translation**, ô nhập và Export Batch TXT hiển thị/nội dung văn bản thuần, không dùng lệnh định dạng.
- Thay đổi nội dung dịch một vùng đồng nghĩa tạo bản dịch mới cho vùng đó: chỉ khi đó các ngắt dòng/định dạng Rich Text cũ không còn hợp lệ; nên lưu JSON dự phòng trước khi sửa.


## Sửa lỗi còn khoảng trắng sau khi xóa [BR] ở dự án cũ

Một số chương trước đây đã bị thuật toán tự ngắt dòng ghi ngược vào JSON. Chỉ ẩn mã \`[BR]\` có thể làm các từ như \`xon[BR]g\`, \`ch[BR]ị\` trở thành \`xon g\`, \`ch ị\`; đồng thời \`translation_rich\` cũ có thể còn chứa các đoạn \`hu[BR]ấn\`, \`ch[BR]o\`.

Bản sửa mới có hai tầng:

1. **OCR Workspace:** khi hiển thị, tái ghép những mảnh chữ có bằng chứng đủ rõ (ví dụ \`xon g\` → \`xong\`, \`ch ị\` → \`chị\`, \`Ya[BR]mamoto\` → \`Yamamoto\` khi OCR gốc chứa \`YAMAMOTO\`). Việc chỉ mở trang **không tự ghi lại JSON**.
2. **Editor và Render Current/All:** khi đọc dữ liệu cũ, phục hồi những từ bị cắt chắc chắn (bao gồm \`hu[BR]ấn\`, \`ch[BR]o\`) từ \`translation\` và **chỉ hủy các đoạn Rich Text cũ nếu chúng không chứa kiểu chữ riêng** và khớp nguyên văn. Ngắt dòng có chủ ý giữa các từ hoàn chỉnh (ví dụ \`Đúng rồi[BR]đó!\`) được giữ.

**Làm thế nào kiểm tra:** Sao lưu JSON; đóng ứng dụng; cập nhật nhánh và mở lại dự án. Đầu tiên kiểm tra cột Translation, sau đó **Mở/tiếp tục chỉnh sửa** trong Editor từ ảnh nguồn. Kiểm tra bố cục câu và xuất lại ảnh lỗi. Lưu Editor State/JSON nếu kết quả đúng. Ảnh cũ đã xuất không tự sửa.

**Giới hạn:** Khi một người đã thay \`[BR]\` bằng dấu cách rồi lưu, không có cách nào biết chính xác tất cả ranh giới từ đã mất. Bản sửa chỉ tự nối các trường hợp chắc chắn, tránh tự gộp sai câu khác. Vùng có Rich Text tùy chỉnh sẽ không bị xóa kiểu chữ một cách tự động; nếu vùng đó vẫn lỗi, cần kiểm tra và đặt lại ngắt dòng thủ công trong Editor.


## Khung chữ và cỡ chữ độc lập (bản sửa theo video 21/11/2026)

Trong Editor, **khung xanh là diện tích bố trí chữ**, không phải thanh điều chỉnh kích cỡ font:

- **Kéo góc/cạnh khung:** đổi kích thước và vị trí bố cục, **không đổi \`font_size\`** đã chọn.
- **Property Editor → Style Settings → Font Size**, hoặc Font/Size ở Rich Text nổi: thay đổi kích cỡ chữ, **không tự thu/phóng khung** đã căn theo bóng thoại.
- **Độ rộng khung:** chữ ngang dạng văn bản thường tự xuống dòng tại **khoảng trắng giữa từ** theo kích thước font cố định, không tự chèn \`[BR]\` vào JSON. Từ dài hơn cả khung không bị xé thành ký tự; hãy giảm cỡ font hoặc chỉnh câu/dòng thủ công.
- **Khớp chữ với khung (1 lần):** nút mới trong **Style Settings**, chủ động ước tính cỡ font lớn nhất vừa chiều ngang và chiều cao khung. Sau đó bạn vẫn có thể kéo khung hoặc chỉnh font mà hai thao tác không ghi đè nhau.
- **Rich Text có kiểu chữ riêng cho từng ký tự:** giữ nguyên bố cục/định dạng của bạn, không tự làm phẳng style để ép wrap. Đặt lại dòng trong Rich Text nổi nếu font cục bộ không khớp.
- Preview và **Export Image** sử dụng cùng thuật toán wrap cho vùng văn bản không có style cục bộ. \`white_frame_rect_local\` và \`has_custom_white_frame\` cũng được lưu cùng trang, tránh mất kích thước khung sau khi xuất/mở lại.

**Để kiểm tra:** Mở trang có bóng thoại hẹp, ghi nhớ Font Size (ví dụ 21), kéo cạnh phải của khung và xác nhận **Font Size vẫn là 21**. Thu lại khung để chữ tự chuyển dòng nhưng không bị chẻ giữa một từ; tăng cỡ chữ thành 25 và xác nhận khung không tự đổi chiều rộng. Save, mở lại Editor và thử Export. Ảnh đã export trước đây không được sửa tự động.

Bản vá giữ nguyên cơ chế cũ \`font_fit_mode=auto\` cho những cấu hình bật rõ ràng; mặc định trên **Manual Edition** là font cố định, một lần khớp cỡ là hành động riêng.


## Khung thoại và Font Size hoạt động độc lập

Trong Editor, chọn vùng thoại rồi chỉnh trong **Property Editor → Style Settings**:

- **Kéo các nút xanh của khung:** chỉnh chiều rộng, chiều cao và vị trí đặt chữ. Chương trình chỉ dàn lại những từ thành dòng trong khoảng rộng mới. **Không làm thay đổi Font Size**.
- **Font Size / thanh trượt:** thay đổi kích cỡ chữ nhưng **không co giãn khung**. Nếu Rich Text có các cỡ chữ tuyệt đối khác nhau, chúng thay đổi theo cùng tỷ lệ, giữ các định dạng còn lại.
- **Khớp chữ với khung (1 lần):** lệnh *tùy chọn*, tính cỡ chữ phù hợp với khung đang có. Lệnh này không bật lại chế độ tự đổi font mỗi khi bạn kéo.
- **Viền khung màu cam:** báo hiệu chữ vượt phạm vi khung sau khi dàn theo từ. Hãy tự quyết định tăng chiều rộng/chiều cao hoặc giảm Font Size. Phần mềm sẽ không cố chia vụn từng từ Việt hay âm thầm thu nhỏ font để làm vừa.
- **Nhấn Enter trong Rich Text nổi:** chèn ngắt dòng cứng. Những ngắt dòng tự động do khung chỉ dùng để vẽ, không được ghi vào Translation JSON.

**Tương thích:** Nếu JSON cũ mang \`font_fit_mode: auto\`, từ bản này khi bạn kéo/chỉnh khung hoặc chọn cỡ chữ, vùng đó chuyển sang chế độ **fixed**. Phần mềm cũng không lấy font/câu dịch cũ từ đối tượng canvas để ghi đè dữ liệu mới sau thao tác kéo khung. Các thay đổi vẫn có Undo và được lưu khi bạn Save Editor State/JSON.

**Lưu ý:** Với những vùng dùng định dạng Rich Text phức tạp (ruby, nhiều kiểu ký tự), việc tự ngắt dòng có thể bị giới hạn để tránh làm mất định dạng. Khi chữ vượt khung, viền cam giúp bạn nhận ra thay vì xuất ảnh lỗi mà không báo.


## Khung chữ kiểu Microsoft Word (bản xem trước trực tiếp)

- Kéo **cạnh/góc** khung thoại trên canvas: ứng dụng dàn lại từ theo chiều rộng hiện tại ngay trong lúc kéo (tối đa khoảng 13 lần/giây), không tăng/giảm Font Size hay tự ghi dấu [BR] vào bản dịch.
- Kéo **chiều cao** chỉ thay đổi khoảng trống của khung. Viền cam báo khi kích thước chữ hiện tại không đủ vừa.
- Đổi **Font, Font Size** chỉ tác động đến kiểu chữ, không thay kích thước khung. Nút **Khớp chữ với khung (1 lần)** vẫn là thao tác chủ động nếu muốn tự tính một cỡ chữ để vừa khung.
- Rich Text nhiều cỡ chữ, in đậm, đổi màu sẽ được dàn lại tại khoảng trắng giữa các từ, vẫn giữ nguyên định dạng từng đoạn. Ruby/TCY được coi là một đơn vị không thể xé đôi. Ngắt dòng do người dùng nhập được giữ nguyên.
- Dàn dòng khi kéo chỉ là **bản xem trước trong bộ nhớ**. Khi thả chuột, thay đổi hình học mới được đưa vào Undo và lưu qua Save Editor State/JSON. Không ghi đè nội dung dịch cũ.
- Preview có giới hạn tần suất để tránh render trên mỗi sự kiện chuột; với trang phức tạp, máy chậm có thể không đạt tốc độ 13 lần/giây. Cần kiểm tra thực tế trên Windows cùng font và trang truyện trước khi gộp PR.
- Nếu một từ đơn dài hơn cả chiều rộng khung, ứng dụng không tự cắt âm tiết hoặc thu nhỏ font: chỉnh cỡ chữ hoặc nới khung. Các kiểu text đặc biệt không thể ngắt an toàn có thể giữ dòng gốc.

### Kiểm tra nhanh theo video

1. Chọn một vùng có câu dài; ghi Font Size và kéo cạnh phải từ hẹp sang rộng rồi lại hẹp. Số dòng phải thay đổi trong khi kéo; Font Size giữ nguyên.
2. Kéo cạnh dưới cao/thấp: nội dung không phóng đại, font không đổi.
3. Đặt Font Size khác (ví dụ 20 → 32): khung không đổi, số dòng có thể thay đổi theo độ rộng; bấm Undo để quay lại.
4. Tạo Rich Text gồm chữ đậm/chữ đỏ/chữ thường trong một câu, kéo khung, xác nhận kiểu chữ vẫn đúng; lưu, đóng mở lại và xuất ảnh so với preview.
5. Kiểm tra JSON sau khi kéo khung: các ngắt dòng mềm mới không xuất hiện trong translation hoặc translation_rich.

## Lưu toàn bộ chương vào một thư mục (Editor)

Trên thanh công cụ Editor, chọn **Lưu cả chương** bên cạnh **Save** và **Export Image**:

1. Mở chương từ OCR Workspace hoặc thêm thư mục ảnh vào Editor, chỉnh lời thoại, font, khung, mask và lớp vẽ bình thường.
2. Bấm **Lưu cả chương**, chọn một *thư mục cha để chứa bản sao lưu*, nằm **ngoài thư mục nguồn** (ví dụ D:\MangaBackups).
3. Editor lưu JSON và ảnh nền sửa của trang đang mở. Sau đó nó xếp công việc sao lưu vào hàng đợi nền cùng các tác vụ Export đang chạy, để không chép ảnh lúc đang ghi.
4. Khi hoàn thành, thông báo chứa đường dẫn thư mục mới, ví dụ D:\MangaBackups\MangaEditor_Chapter_20261122_013000. Mỗi lần sao lưu tạo thư mục mới; không ghi đè dữ liệu hay bản sao lưu trước.

Trong thư mục mới (một chương/nhóm thư mục nguồn):

- Ảnh gốc giữ nguyên tên và cấu trúc thư mục.
- **manga_translator_work/**: JSON chứa các câu dịch, Rich Text, font, khung chữ, mask, Paint/Stamp/Paste, inpaint và metadata liên quan. Các file phụ trợ có sẵn trong thư mục nguồn cũng được sao chép.
- **mangaeditor_backup_manifest.json**: danh sách trang đã sao lưu và thông tin cấu trúc.
- Ảnh xuất trước đó *nếu đã nằm trong thư mục nguồn* được sao chép như file bình thường. Ảnh xuất ở nơi khác chỉ được đưa vào **manga_translator_work/result/** nếu từng được ghi trong metadata last_export_dir và file còn tồn tại.

**Di chuyển/mở lại:** trên máy gốc, bạn có thể dùng **Thêm thư mục dự án** (OCR Workspace) hoặc **Add Folder** (Editor) trỏ đến thư mục sao lưu. Những JSON _translations.json cũ chứa đường dẫn ảnh tuyệt đối được *chỉ sửa trong bản sao*, để ứng dụng nhận vị trí ảnh mới. File dự án ban đầu không thay đổi. Nếu thư mục sao lưu chứa nhiều chương từ các thư mục nguồn khác nhau, hãy mở các thư mục con trong chapters/.

**Phân biệt các nút:**

- **Save / Ctrl+S**: lưu trang đang mở trong dự án gốc (không xuất ảnh).
- **Export Image / Ctrl+Q**: tạo ảnh thành phẩm của trang đang mở.
- **Lưu cả chương**: tạo bản sao dự án đầy đủ trong một thư mục mới (không tự render lại tất cả các trang). Các trang trước đó phải được Save hoặc đã bật Auto Save khi chuyển trang; không thể khôi phục những thay đổi chưa từng lưu và đã bị bỏ đi.

**Giới hạn:** font cài trong Windows hoặc thư mục fonts riêng của ứng dụng không tự được nhúng trong bản sao lưu. Muốn có kết quả giống hệt trên máy khác, phải cài lại đúng font. Tránh chọn thư mục sao lưu nằm trong chính thư mục ảnh nguồn; ứng dụng sẽ từ chối để không sao chép lồng vô hạn. Link tượng trưng (symlink), .git, .venv, các file tạm không được sao chép. Chỉ xuất hiện thông báo *thành công* khi bản sao lưu đã tạo xong.
