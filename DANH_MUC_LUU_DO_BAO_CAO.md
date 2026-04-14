# Danh Mục Lưu Độ Giải Thuật Cho Báo Cáo Tiểu Luận

Mục tiêu tài liệu: cung cấp đặc tả "có thể vẽ lại ngay" cho toàn bộ lưu độ cần đưa vào báo cáo.
Tài liệu này không dùng Mermaid/đồ họa, chỉ mô tả học thuật theo dạng nút + mũi tên.

---

## Quy ước chung để vẽ

- Terminator: Bắt đầu/Kết thúc.
- Process (hình chữ nhật): bước xử lý.
- Decision (hình thoi): câu hỏi Yes/No.
- Data (hình bình hành): dữ liệu vào/ra.
- Connector: nối nhánh/nhảy trang.

Quy tắc đặt tên nút khi vẽ:
- T<n>: Terminator
- P<n>: Process
- D<n>: Decision
- O<n>: Output

---

## I. Lưu Độ Bắt Buộc Phải Có

### I.1 Lưu độ tổng quan hệ thống giải LP

Mục tiêu: mô tả đường đi tổng thể từ người dùng đến kết quả.

Nút để vẽ:
1. T1: Bắt đầu.
2. P1: Người dùng nhập bài toán LP trên giao diện.
3. P2: Frontend đóng gói payload JSON.
4. P3: Gửi POST /api/v1/simplex/solve.
5. P4: Backend validate + chuẩn hóa + giải theo mode.
6. O1: Trả response JSON (learning hoặc production).
7. P5: Frontend render kết quả (table/algebra/production panel).
8. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> P2 -> P3 -> P4 -> O1 -> P5 -> T2

### I.2 Lưu độ định tuyến chế độ giải (Mode Routing)

Mục tiêu: thể hiện nhanh xử lý theo mode.

Nút để vẽ:
1. T1: Bắt đầu.
2. P1: Nhận request mode, goal, objective, constraints, types, rhs.
3. D1: mode == learning?
4. P2: Nhánh learning: Stage 1 -> Stage 2 -> Stage 3.
5. P3: Nhánh production: Stage 1 -> Stage 4 -> Stage 5.
6. O1: Trả response theo contract learning.
7. O2: Trả response theo contract production.
8. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> D1
- Yes -> P2 -> O1 -> T2
- No  -> P3 -> O2 -> T2

### I.3 Lưu độ Stage 1: Tiền xử lý và chuẩn hóa mô hình

Mục tiêu: đưa bài toán về biểu diễn nội bộ hợp lệ trước khi vào bộ giải.

Nút để vẽ:
1. T1: Bắt đầu Stage 1.
2. P1: Chuẩn hóa goal (max/min convention nội bộ).
3. P2: Chuẩn hóa miền đầu biến (nonnegative/free).
4. D1: Có biến free?
5. P3: Tách biến free x = x_plus - x_minus.
6. P4: Duyệt từng ràng buộc.
7. D2: RHS b_i < 0?
8. P5: Nhân -1 cả dòng, đảo chiều bất đẳng thức.
9. P6: Presolve (scaling, loại bỏ dòng dư, phát hiện mâu thuẫn sớm).
10. O1: Xuất normalized model + normalization metadata.
11. T2: Kết thúc Stage 1.

Luồng mũi tên:
T1 -> P1 -> P2 -> D1
- Yes -> P3 -> P4
- No  -> P4
P4 -> D2
- Yes -> P5 -> P6
- No  -> P6
P6 -> O1 -> T2

### I.4 Lưu độ Stage 2: Khởi tạo khả thi (Two-Phase)

Mục tiêu: tạo hệ dạng chuẩn và khởi tạo cơ sở ban đầu.

Nút để vẽ:
1. T1: Bắt đầu Stage 2.
2. P1: Thêm slack/surplus theo loại ràng buộc.
3. P2: Đối cơ sở tự nhiên (natural basis detection).
4. D1: Còn dòng chưa có cột cơ sở đơn vị?
5. P3: Thêm biến nhân tạo a_i cho các dòng cần.
6. D2: Có biến nhân tạo?
7. P4: Tạo objective W cho Phase I.
8. P5: Khởi tạo objective Z gốc cho Phase II.
9. O1: Xuất standard form tableau + basis metadata.
10. T2: Kết thúc Stage 2.

Luồng mũi tên:
T1 -> P1 -> P2 -> D1
- Yes -> P3 -> D2
- No  -> D2
D2
- Yes -> P4 -> P5 -> O1 -> T2
- No  -> P5 -> O1 -> T2

### I.5 Lưu độ vòng lặp Phase I

Mục tiêu: tìm BFS khả thi bằng objective W.

Nút để vẽ:
1. T1: Bắt đầu Phase I.
2. P1: Tính reduced costs trên dòng W.
3. D1: Điều kiện tối ưu W đạt?
4. D2: W* == 0?
5. O1: W* > 0 -> Infeasible.
6. P2: Chọn cột vào (entering).
7. P3: Ratio test chọn hàng ra (leaving).
8. D3: Có hàng pivot hợp lệ?
9. O2: Không có pivot -> kết luận vô nghiệm trong Phase I.
10. P4: Pivot/Gauss-Jordan, cập nhật basis.
11. Connector C1: Quay lại đầu vòng.
12. T2: Kết thúc Phase I thành công.

Luồng mũi tên:
T1 -> P1 -> D1
- No  -> P2 -> P3 -> D3
- Yes -> P4 -> C1 -> P1
- No  -> O2 -> T2
- Yes -> D2
- Yes -> T2
- No  -> O1 -> T2

### I.6 Lưu độ chuyển Phase I -> Phase II

Mục tiêu: chuyển hệ khả thi sang bài toán gốc.

Nút để vẽ:
1. T1: Bắt đầu chuyển pha.
2. D1: W* == 0?
3. O1: Nếu không, kết luận Infeasible và dừng.
4. P1: Loại bỏ các cột biến nhân tạo.
5. P2: Khôi phục objective Z gốc.
6. P3: Tái chuẩn hóa dòng Z theo cơ sở hiện tại.
7. O2: Xuất tableau đầu vào cho Phase II.
8. T2: Kết thúc.

Luồng mũi tên:
T1 -> D1
- No  -> O1 -> T2
- Yes -> P1 -> P2 -> P3 -> O2 -> T2

### I.7 Lưu độ vòng lặp Simplex Phase II (Full Tableau)

Mục tiêu: tối ưu objective gốc bằng tableau.

Nút để vẽ:
1. T1: Bắt đầu Phase II.
2. P1: Kiểm tra reduced costs trên dòng Z.
3. D1: Đã tối ưu?
4. O1: Optimal.
5. P2: Chọn cột vào.
6. P3: Ratio test chọn hàng ra.
7. D2: Có hàng pivot hợp lệ?
8. O2: Unbounded.
9. P4: Pivot/Gauss-Jordan, cập nhật tableau + basis.
10. Connector C1: Quay lại P1.
11. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> D1
- Yes -> O1 -> T2
- No  -> P2 -> P3 -> D2
- Yes -> P4 -> C1 -> P1
- No  -> O2 -> T2

### I.8 Lưu độ quy tắc Bland cho trường hợp suy biến

Mục tiêu: tránh cycling khi có tie.

Nút để vẽ:
1. T1: Bắt đầu tie-break.
2. D1: Có nhiều entering candidates cùng mức ưu tiên?
3. P1: Chọn entering có chỉ số nhỏ nhất.
4. D2: Có nhiều leaving candidates cùng min ratio?
5. P2: Chọn leaving có chỉ số nhỏ nhất.
6. O1: Trả về cặp pivot (entering, leaving) theo Bland.
7. T2: Kết thúc.

Luồng mũi tên:
T1 -> D1
- Yes -> P1 -> D2
- No  -> D2
D2
- Yes -> P2 -> O1 -> T2
- No  -> O1 -> T2

### I.9 Lưu độ Stage 5 Revised Simplex (Production)

Mục tiêu: tối ưu nhanh, bộ nhớ gọn, output compact.

Nút để vẽ:
1. T1: Bắt đầu Stage 5.
2. P1: Khởi tạo basis cho Phase II (hoặc fallback nếu không khởi tạo được).
3. D1: Basis hợp lệ?
4. O1: Fallback full tableau compact result.
5. P2: Giải hệ để tính x_B.
6. P3: Giải hệ song đối để tính y và reduced costs.
7. D2: Có biến cải thiện?
8. O2: Optimal + sensitivity report.
9. P4: Tính hướng d và ratio test.
10. D3: Ratio hợp lệ?
11. O3: Unbounded.
12. P5: Cập nhật basis, tăng iteration.
13. D4: Vượt giới hạn lặp?
14. O4: Iteration limit.
15. Connector C1: Quay lại P2.
16. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> D1
- No  -> O1 -> T2
- Yes -> P2 -> P3 -> D2
- No  -> O2 -> T2
- Yes -> P4 -> D3
- No  -> O3 -> T2
- Yes -> P5 -> D4
- Yes -> O4 -> T2
- No  -> C1 -> P2

### I.10 Lưu độ kết luận trạng thái bài toán

Mục tiêu: chuẩn hóa logic kết thúc và message.

Nút để vẽ:
1. T1: Bắt đầu đánh giá terminal state.
2. D1: Đạt điều kiện tối ưu?
3. O1: Optimal.
4. D2: Ratio test thất bại (không có leaving row)?
5. O2: Unbounded.
6. D3: W* > 0 hoặc ràng buộc mâu thuẫn?
7. O3: Infeasible.
8. D4: Vượt iteration limit?
9. O4: Iteration limit.
10. D5: Lỗi số học/hệ giải thất bại?
11. O5: Numerical error/Fallback.
12. T2: Kết thúc.

Luồng mũi tên:
T1 -> D1
- Yes -> O1 -> T2
- No  -> D2
- Yes -> O2 -> T2
- No  -> D3
- Yes -> O3 -> T2
- No  -> D4
- Yes -> O4 -> T2
- No  -> D5
- Yes -> O5 -> T2
- No  -> O5 -> T2

### I.11 Lưu độ xử lý lỗi và guardrails runtime

Mục tiêu: đảm bảo API an toàn, không quá tải.

Nút để vẽ:
1. T1: Nhận request.
2. P1: Validate schema Pydantic.
3. D1: Schema hợp lệ?
4. O1: HTTP 422/400.
5. P2: Validate kích thước matrix + độ dài mảng.
6. D2: Kích thước hợp lệ?
7. O2: HTTP 400.
8. P3: Kiểm tra guardrails theo mode (vars, constraints, matrix cells).
9. D3: Vượt ngưỡng?
10. O3: HTTP 413.
11. P4: Chạy solver trong timeout mem.
12. D4: Timeout?
13. O4: HTTP 503.
14. O5: HTTP 200 + kết quả.
15. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> D1
- No  -> O1 -> T2
- Yes -> P2 -> D2
- No  -> O2 -> T2
- Yes -> P3 -> D3
- Yes -> O3 -> T2
- No  -> P4 -> D4
- Yes -> O4 -> T2
- No  -> O5 -> T2

### I.12 Lưu độ hiển thị kết quả trên frontend

Mục tiêu: mô tả logic render kết quả và giải thích.

Nút để vẽ:
1. T1: Nhận store_data từ callback.
2. D1: Có lỗi backend?
3. O1: Hiện alert lỗi + input echo.
4. D2: mode == production?
5. P1: Render production panel (status, objective, solution, sensitivity).
6. D3: mode learning và display_mode == algebra?
7. P2: Render algebra đầy đủ.
8. P3: Render table + algebra classic song song.
9. D4: Có cần hiển thị card mô hình chuẩn hóa?
10. P4: Hiển thị notice normalized model + normalization details.
11. O2: Xuất giao diện kết quả hoàn chỉnh.
12. T2: Kết thúc.

Luồng mũi tên:
T1 -> D1
- Yes -> O1 -> T2
- No  -> D2
- Yes -> P1 -> D4
- No  -> D3
- Yes -> P2 -> D4
- No  -> P3 -> D4
D4
- Yes -> P4 -> O2 -> T2
- No  -> O2 -> T2

---

## II. Lưu Độ Cần Thiết Nên Có (Để Báo Cáo Đầy Đủ Và Dễ Hiểu)

### II.1 Lưu độ chu trình dữ liệu (Data lifecycle)

Mục tiêu: mô tả vòng đời dữ liệu từ input thô đến kết quả hiển thị.

Nút để vẽ:
1. T1: Bắt đầu nhận bài toán LP.
2. P1: Nhận raw model (goal, objective, constraints, types, rhs).
3. P2: Stage 1 tạo normalized model + normalization metadata.
4. P3: Stage 2 tạo standard form + basis metadata.
5. D1: mode == learning?
6. P4: Nhánh learning gọi Stage 3, sinh steps/explanations.
7. P5: Nhánh production gọi Stage 5, sinh compact result + sensitivity.
8. D2: Trạng thái terminal là optimal?
9. O1: Terminal không tối ưu (infeasible/unbounded/iteration limit/error).
10. O2: Terminal tối ưu, đóng gói response contract theo mode.
11. P6: Frontend parse payload, map biến gốc <-> biến nội bộ.
12. P7: Render panel + thuyết minh tương ứng mode.
13. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> P2 -> P3 -> D1
- Yes -> P4 -> D2
- No  -> P5 -> D2
D2
- Yes -> O2 -> P6 -> P7 -> T2
- No  -> O1 -> P6 -> P7 -> T2

### II.2 Lưu độ ánh xạ biến

Mục tiêu: thể hiện cách biến gốc và ràng buộc được ánh xạ sang biến nội bộ.

Nút để vẽ:
1. T1: Bắt đầu ánh xạ mô hình.
2. P1: Duyệt từng biến gốc x_i và miền giá trị.
3. D1: x_i là biến free?
4. P2: Tạo x_i_plus, x_i_minus; ghi công thức x_i = x_i_plus - x_i_minus.
5. P3: Giữ nguyên biến không free theo chuẩn nonnegative.
6. P4: Duyệt từng ràng buộc theo loại dấu.
7. D2: Loại ràng buộc là <=, >= hay = ?
8. P5: Nếu <=, thêm slack s_i.
9. P6: Nếu >=, thêm surplus e_i và artificial a_i khi cần basis.
10. P7: Nếu =, thêm artificial a_i khi không có natural basis.
11. P8: Cập nhật bảng mapping (biến gốc, biến nội bộ, cột tableau).
12. O1: Xuất var mapping table + normalization notes.
13. T2: Kết thúc ánh xạ.

Luồng mũi tên:
T1 -> P1 -> D1
- Yes -> P2 -> P4
- No  -> P3 -> P4
P4 -> D2
- <= -> P5 -> P8
- >= -> P6 -> P8
- =  -> P7 -> P8
P8 -> O1 -> T2

### II.3 Lưu độ so sánh Learning vs Production

Mục tiêu: minh họa sự khác biệt luồng xử lý và output contract giữa 2 mode.

Nút để vẽ:
1. T1: Bắt đầu nhận request.
2. P1: Parse input và tham số mode.
3. D1: mode == learning?
4. P2: Learning path: Stage 1 -> Stage 2 -> Stage 3.
5. P3: Tạo output learning: steps[], tableau snapshots, explanation blocks.
6. O1: Response learning contract.
7. P4: Production path: Stage 1 -> Stage 4 -> Stage 5.
8. P5: Tạo output production: objective, solution, sensitivity, metadata tối giản.
9. O2: Response production contract.
10. P6: Frontend chọn layout và panel theo mode.
11. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> D1
- Yes -> P2 -> P3 -> O1 -> P6 -> T2
- No  -> P4 -> P5 -> O2 -> P6 -> T2

### II.4 Lưu độ phát hiện không bị chặn (Unbounded reasoning)

Mục tiêu: diễn giải logic kết luận bài toán không bị chặn trong Phase II.

Nút để vẽ:
1. T1: Bắt đầu một vòng lặp Phase II.
2. P1: Chọn entering column có reduced cost cải thiện.
3. P2: Thực hiện ratio test trên các dòng có a_ij > 0.
4. D1: Có leaving row hợp lệ?
5. P3: Có -> chọn leaving row (min ratio) và pivot.
6. P4: Cập nhật tableau/basis, quay lại vòng lặp.
7. O1: Không có -> ratio test thất bại.
8. O2: Kết luận Unbounded (tồn tại tia khả thi làm objective tăng vô hạn).
9. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> P2 -> D1
- Yes -> P3 -> P4 -> T2
- No  -> O1 -> O2 -> T2

### II.5 Lưu độ phát hiện vô nghiệm

Mục tiêu: làm rõ hai điểm chặn vô nghiệm: presolve và cuối Phase I.

Nút để vẽ:
1. T1: Bắt đầu kiểm tra tính khả thi.
2. P1: Presolve rà soát ràng buộc mâu thuẫn/không nhất quán.
3. D1: Presolve phát hiện mâu thuẫn?
4. O1: Có -> Infeasible sớm.
5. P2: Không -> chạy Phase I với objective W.
6. D2: W* == 0?
7. P3: Có -> loại artificial, chuyển sang Phase II.
8. O2: Không -> Infeasible tại cuối Phase I.
9. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> D1
- Yes -> O1 -> T2
- No  -> P2 -> D2
D2
- Yes -> P3 -> T2
- No  -> O2 -> T2

### II.6 Lưu độ tạo báo cáo độ nhạy (Sensitivity report)

Mục tiêu: mô tả pipeline sinh sensitivity object sau khi có nghiệm tối ưu.

Nút để vẽ:
1. T1: Bắt đầu tạo sensitivity report.
2. D1: Terminal status là optimal?
3. O1: Không optimal -> bỏ qua sensitivity, ghi lý do.
4. P1: Có optimal -> tính y (dual prices/shadow prices).
5. P2: Tính reduced costs cho biến không cơ sở.
6. P3: Tính slack và xác định binding constraints.
7. P4: Tổng hợp metrics ổn định số (nếu có).
8. P5: Đóng gói sensitivity object vào response production.
9. P6: Frontend render sensitivity panel.
10. T2: Kết thúc.

Luồng mũi tên:
T1 -> D1
- No  -> O1 -> T2
- Yes -> P1 -> P2 -> P3 -> P4 -> P5 -> P6 -> T2

### II.7 Lưu độ kiểm thử hồi quy

Mục tiêu: chuẩn hóa vòng lặp kiểm thử trước khi chốt release/demo.

Nút để vẽ:
1. T1: Bắt đầu regression test.
2. P1: Chuẩn bị môi trường test và dữ liệu mẫu.
3. P2: Chạy smoke tests (optimal/unbounded/infeasible/mixed constraints).
4. P3: Chạy tests suy biến và stress.
5. D1: Tất cả testcase pass?
6. O1: Yes -> đạt release gate.
7. P4: No -> thu thập log/failing cases.
8. P5: Sửa lỗi hồi quy.
9. P6: Chạy lại testcase lỗi + chạy lại smoke.
10. Connector C1: Quay lại D1.
11. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> P2 -> P3 -> D1
- Yes -> O1 -> T2
- No  -> P4 -> P5 -> P6 -> C1 -> D1

### II.8 Lưu độ startup và vận hành

Mục tiêu: mô tả quy trình chạy hệ thống ổn định cho demo và báo cáo.

Nút để vẽ:
1. T1: Bắt đầu quy trình vận hành local.
2. P1: Kích hoạt virtual environment và cài dependencies.
3. P2: Khởi động backend service.
4. P3: Khởi động frontend service.
5. P4: Kiểm tra health endpoint và gọi API mẫu.
6. D1: Health check đạt?
7. P5: Không đạt -> đọc log, sửa cấu hình, restart dịch vụ.
8. P6: Đạt -> chạy smoke test script.
9. D2: Smoke test pass?
10. O1: Yes -> hệ thống sẵn sàng demo/báo cáo.
11. P7: No -> debug lỗi runtime/test và quay lại bước khởi động.
12. Connector C1: Quay lại P2.
13. T2: Kết thúc.

Luồng mũi tên:
T1 -> P1 -> P2 -> P3 -> P4 -> D1
- No  -> P5 -> C1 -> P2
- Yes -> P6 -> D2
D2
- Yes -> O1 -> T2
- No  -> P7 -> C1 -> P2


