# Danh Muc Luu Do Giai Thuat Cho Bao Cao Tieu Luan

Muc tieu tai lieu: cung cap dac ta "co the ve lai ngay" cho toan bo luu do can dua vao bao cao.
Tai lieu nay khong dung Mermaid/do hoa, chi mo ta hoc thuat theo dang nut + mui ten.

---

## Quy uoc chung de ve

- Terminator: Bat dau/Ket thuc.
- Process (hinh chu nhat): buoc xu ly.
- Decision (hinh thoi): cau hoi Yes/No.
- Data (hinh binh hanh): du lieu vao/ra.
- Connector: noi nhanh/nhay trang.

Quy tac dat ten nut khi ve:
- T<n>: Terminator
- P<n>: Process
- D<n>: Decision
- O<n>: Output

---

## I. Luu Do Bat Buoc Phai Co

### I.1 Luu do tong quan he thong giai LP

Muc tieu: mo ta duong di tong the tu nguoi dung den ket qua.

Nut de ve:
1. T1: Bat dau.
2. P1: Nguoi dung nhap bai toan LP tren giao dien.
3. P2: Frontend dong goi payload JSON.
4. P3: Gui POST /api/v1/simplex/solve.
5. P4: Backend validate + chuan hoa + giai theo mode.
6. O1: Tra response JSON (learning hoac production).
7. P5: Frontend render ket qua (table/algebra/production panel).
8. T2: Ket thuc.

Luong mui ten:
T1 -> P1 -> P2 -> P3 -> P4 -> O1 -> P5 -> T2

### I.2 Luu do dinh tuyen che do giai (Mode Routing)

Muc tieu: the hien nhanh xu ly theo mode.

Nut de ve:
1. T1: Bat dau.
2. P1: Nhan request mode, goal, objective, constraints, types, rhs.
3. D1: mode == learning?
4. P2: Nhanh learning: Stage 1 -> Stage 2 -> Stage 3.
5. P3: Nhanh production: Stage 1 -> Stage 4 -> Stage 5.
6. O1: Tra response theo contract learning.
7. O2: Tra response theo contract production.
8. T2: Ket thuc.

Luong mui ten:
T1 -> P1 -> D1
- Yes -> P2 -> O1 -> T2
- No  -> P3 -> O2 -> T2

### I.3 Luu do Stage 1: Tien xu ly va chuan hoa mo hinh

Muc tieu: dua bai toan ve bieu dien noi bo hop le truoc khi vao bo giai.

Nut de ve:
1. T1: Bat dau Stage 1.
2. P1: Chuan hoa goal (max/min convention noi bo).
3. P2: Chuan hoa mien dau bien (nonnegative/free).
4. D1: Co bien free?
5. P3: Tach bien free x = x_plus - x_minus.
6. P4: Duyet tung rang buoc.
7. D2: RHS b_i < 0?
8. P5: Nhan -1 ca dong, dao chieu bat dang thuc.
9. P6: Presolve (scaling, loai dong du, phat hien mau thuan som).
10. O1: Xuat normalized model + normalization metadata.
11. T2: Ket thuc Stage 1.

Luong mui ten:
T1 -> P1 -> P2 -> D1
- Yes -> P3 -> P4
- No  -> P4
P4 -> D2
- Yes -> P5 -> P6
- No  -> P6
P6 -> O1 -> T2

### I.4 Luu do Stage 2: Khoi tao kha thi (Two-Phase)

Muc tieu: tao he dang chuan va khoi tao co so ban dau.

Nut de ve:
1. T1: Bat dau Stage 2.
2. P1: Them slack/surplus theo loai rang buoc.
3. P2: Doi co so tu nhien (natural basis detection).
4. D1: Con dong chua co cot co so don vi?
5. P3: Them bien nhan tao a_i cho cac dong can.
6. D2: Co bien nhan tao?
7. P4: Tao objective W cho Phase I.
8. P5: Khoi tao objective Z goc cho Phase II.
9. O1: Xuat standard form tableau + basis metadata.
10. T2: Ket thuc Stage 2.

Luong mui ten:
T1 -> P1 -> P2 -> D1
- Yes -> P3 -> D2
- No  -> D2
D2
- Yes -> P4 -> P5 -> O1 -> T2
- No  -> P5 -> O1 -> T2

### I.5 Luu do vong lap Phase I

Muc tieu: tim BFS kha thi bang objective W.

Nut de ve:
1. T1: Bat dau Phase I.
2. P1: Tinh reduced costs tren dong W.
3. D1: Dieu kien toi uu W dat?
4. D2: W* == 0?
5. O1: W* > 0 -> Infeasible.
6. P2: Chon cot vao (entering).
7. P3: Ratio test chon hang ra (leaving).
8. D3: Co hang pivot hop le?
9. O2: Khong co pivot -> ket luan vo nghiem trong Phase I.
10. P4: Pivot/Gauss-Jordan, cap nhat basis.
11. Connector C1: Quay lai dau vong.
12. T2: Ket thuc Phase I thanh cong.

Luong mui ten:
T1 -> P1 -> D1
- No  -> P2 -> P3 -> D3
	- Yes -> P4 -> C1 -> P1
	- No  -> O2 -> T2
- Yes -> D2
	- Yes -> T2
	- No  -> O1 -> T2

### I.6 Luu do chuyen Phase I -> Phase II

Muc tieu: chuyen he kha thi sang bai toan goc.

Nut de ve:
1. T1: Bat dau chuyen pha.
2. D1: W* == 0?
3. O1: Neu khong, ket luan Infeasible va dung.
4. P1: Loai bo cac cot bien nhan tao.
5. P2: Khoi phuc objective Z goc.
6. P3: Tai chuan hoa dong Z theo co so hien tai.
7. O2: Xuat tableau dau vao cho Phase II.
8. T2: Ket thuc.

Luong mui ten:
T1 -> D1
- No  -> O1 -> T2
- Yes -> P1 -> P2 -> P3 -> O2 -> T2

### I.7 Luu do vong lap Simplex Phase II (Full Tableau)

Muc tieu: toi uu objective goc bang tableau.

Nut de ve:
1. T1: Bat dau Phase II.
2. P1: Kiem tra reduced costs tren dong Z.
3. D1: Da toi uu?
4. O1: Optimal.
5. P2: Chon cot vao.
6. P3: Ratio test chon hang ra.
7. D2: Co hang pivot hop le?
8. O2: Unbounded.
9. P4: Pivot/Gauss-Jordan, cap nhat tableau + basis.
10. Connector C1: Quay lai P1.
11. T2: Ket thuc.

Luong mui ten:
T1 -> P1 -> D1
- Yes -> O1 -> T2
- No  -> P2 -> P3 -> D2
	- Yes -> P4 -> C1 -> P1
	- No  -> O2 -> T2

### I.8 Luu do quy tac Bland cho truong hop suy bien

Muc tieu: tranh cycling khi co tie.

Nut de ve:
1. T1: Bat dau tie-break.
2. D1: Co nhieu entering candidates cung muc uu tien?
3. P1: Chon entering co chi so nho nhat.
4. D2: Co nhieu leaving candidates cung min ratio?
5. P2: Chon leaving co chi so nho nhat.
6. O1: Tra ve cap pivot (entering, leaving) theo Bland.
7. T2: Ket thuc.

Luong mui ten:
T1 -> D1
- Yes -> P1 -> D2
- No  -> D2
D2
- Yes -> P2 -> O1 -> T2
- No  -> O1 -> T2

### I.9 Luu do Stage 5 Revised Simplex (Production)

Muc tieu: toi uu nhanh, bo nho gon, output compact.

Nut de ve:
1. T1: Bat dau Stage 5.
2. P1: Khoi tao basis cho Phase II (hoac fallback neu khong khoi tao duoc).
3. D1: Basis hop le?
4. O1: Fallback full tableau compact result.
5. P2: Giai he de tinh x_B.
6. P3: Giai he song doi de tinh y va reduced costs.
7. D2: Co bien cai thien?
8. O2: Optimal + sensitivity report.
9. P4: Tinh huong d va ratio test.
10. D3: Ratio hop le?
11. O3: Unbounded.
12. P5: Cap nhat basis, tang iteration.
13. D4: Vuot gioi han lap?
14. O4: Iteration limit.
15. Connector C1: Quay lai P2.
16. T2: Ket thuc.

Luong mui ten:
T1 -> P1 -> D1
- No  -> O1 -> T2
- Yes -> P2 -> P3 -> D2
	- No  -> O2 -> T2
	- Yes -> P4 -> D3
		- No  -> O3 -> T2
		- Yes -> P5 -> D4
			- Yes -> O4 -> T2
			- No  -> C1 -> P2

### I.10 Luu do ket luan trang thai bai toan

Muc tieu: chuan hoa logic ket thuc va message.

Nut de ve:
1. T1: Bat dau danh gia terminal state.
2. D1: Dat dieu kien toi uu?
3. O1: Optimal.
4. D2: Ratio test that bai (khong co leaving row)?
5. O2: Unbounded.
6. D3: W* > 0 hoac rang buoc mau thuan?
7. O3: Infeasible.
8. D4: Vuot iteration limit?
9. O4: Iteration limit.
10. D5: Loi so hoc/he giai that bai?
11. O5: Numerical error/Fallback.
12. T2: Ket thuc.

Luong mui ten:
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

### I.11 Luu do xu ly loi va guardrails runtime

Muc tieu: dam bao API an toan, khong qua tai.

Nut de ve:
1. T1: Nhan request.
2. P1: Validate schema Pydantic.
3. D1: Schema hop le?
4. O1: HTTP 422/400.
5. P2: Validate kich thuoc matrix + do dai mang.
6. D2: Kich thuoc hop le?
7. O2: HTTP 400.
8. P3: Kiem tra guardrails theo mode (vars, constraints, matrix cells).
9. D3: Vuot nguong?
10. O3: HTTP 413.
11. P4: Chay solver trong timeout mem.
12. D4: Timeout?
13. O4: HTTP 503.
14. O5: HTTP 200 + ket qua.
15. T2: Ket thuc.

Luong mui ten:
T1 -> P1 -> D1
- No  -> O1 -> T2
- Yes -> P2 -> D2
	- No  -> O2 -> T2
	- Yes -> P3 -> D3
		- Yes -> O3 -> T2
		- No  -> P4 -> D4
			- Yes -> O4 -> T2
			- No  -> O5 -> T2

### I.12 Luu do hien thi ket qua tren frontend

Muc tieu: mo ta logic render ket qua va giai thich.

Nut de ve:
1. T1: Nhan store_data tu callback.
2. D1: Co loi backend?
3. O1: Hien alert loi + input echo.
4. D2: mode == production?
5. P1: Render production panel (status, objective, solution, sensitivity).
6. D3: mode learning va display_mode == algebra?
7. P2: Render algebra full.
8. P3: Render table + algebra classic song song.
9. D4: Co can hien card mo hinh chuan hoa?
10. P4: Hien notice normalized model + normalization details.
11. O2: Xuat giao dien ket qua hoan chinh.
12. T2: Ket thuc.

Luong mui ten:
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

## II. Luu Do Can Thiet Nen Co (De Bao Cao Day Du Va De Hieu)

### II.1 Luu do chu trinh du lieu (Data lifecycle)

Nut de ve:
T1 -> Input raw model -> Stage 1 normalized model -> Stage 2 standard form ->
Stage 3/5 solver state -> terminal result -> frontend explanation/panel -> T2.

Ghi trong o quan trong:
- normalization metadata.
- var mapping.
- response contract theo mode.

### II.2 Luu do anh xa bien

Nut de ve:
1. Input variable x_i.
2. D1: x_i free?
3. Neu Yes: tao x_i_plus, x_i_minus va cong thuc x_i = x_i_plus - x_i_minus.
4. Rang buoc <=: them slack s_i.
5. Rang buoc >=: them surplus e_i va co the them artificial a_i.
6. Output: bang mapping bien goc <-> bien noi bo.

### II.3 Luu do so sanh Learning vs Production

Hai cot song song de ve:

- Nhanh Learning:
	Input -> Stage 1 -> Stage 2 -> Stage 3 -> steps[] + explanation.

- Nhanh Production:
	Input -> Stage 1 -> Stage 4/5 -> compact result + sensitivity.

Nut hop nhat cuoi:
- Frontend render theo panel tuong ung.

### II.4 Luu do phat hien khong bi chan (Unbounded reasoning)

Nut de ve:
1. Chon entering column.
2. D1: Co row nao co a_ij > 0?
3. Neu khong: ratio test that bai.
4. Ket luan: khong co leaving variable.
5. Suy ra ton tai tia kha thi lam objective tang vo han.
6. Output: Unbounded.

### II.5 Luu do phat hien vo nghiem

Nut de ve:
1. Ket thuc Phase I.
2. D1: W* > 0?
3. Neu Yes: Infeasible.
4. Neu No: Chuyen sang Phase II.

Nhanh bo sung:
- Presolve phat hien rang buoc mau thuan som -> Infeasible ngay.

### II.6 Luu do tao bao cao do nhay (Sensitivity report)

Nut de ve:
1. Da co nghiem toi uu production.
2. Tinh y (dual prices).
3. Tinh reduced costs cho cac bien.
4. Tinh slack va binding constraints.
5. Dong goi sensitivity object trong response.
6. Frontend render trong production panel.

### II.7 Luu do kiem thu hoi quy

Nut de ve:
1. Chuan bi test suite.
2. Chay nhom testcase:
	 optimal, unbounded, infeasible, mixed constraints, degeneracy, stress.
3. D1: Tat ca pass?
4. Yes -> dat release gate.
5. No -> fix bug -> chay lai test.

### II.8 Luu do startup va van hanh

Nut de ve:
1. Kich hoat .venv.
2. Chay scripts/dev_up.sh.
3. Khoi dong backend uvicorn.
4. Khoi dong frontend dash.
5. Kiem tra health/goi API thu.
6. Chay scripts/test_smoke.sh.
7. D1: Test pass?
8. Yes -> san sang demo/bao cao.
9. No -> debug va lap lai.

---

## III. Checklist Trinh Bay Trong Bao Cao

### III.1 Checklist noi dung moi luu do

Moi luu do can co du 4 nhom thong tin:

1. Input.
2. Cac nut xu ly chinh.
3. Nut quyet dinh va nhanh Yes/No.
4. Output/terminal state.

### III.2 Checklist hinh thuc

1. Dat ten nhat quan: Stage 1..5, Phase I/II, pivot, ratio test, reduced cost, basis.
2. Co danh so nut neu luu do dai (P1, D1, O1...).
3. Cac nhanh quan trong phai co nhan dieu kien ro rang.

### III.3 Thu tu chen luu do de bai bao cao mach lac

Thu tu de xuat:

1. I.1 -> I.2.
2. I.3 -> I.4 -> I.5 -> I.6 -> I.7 -> I.8 -> I.9.
3. I.10 -> I.11 -> I.12.
4. Bo sung II.1 -> II.8 de tang tinh hoc thuat va tinh thuyet phuc.
