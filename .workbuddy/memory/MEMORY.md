# MEMORY.md

## 项目概览
航运调度模拟系统：shipping_schedule.html（仓库根目录）。GitHub: LeahLiuL/Schedule-Simulation；线上 leahlil.github.io。数据目录 shipping_data/。

## ⚠️ Git 操作铁律（最高优先级）
用户只在浏览器端编辑/commit 数据（GitHub API），本地不自动同步。
改前：`git fetch origin main` → `git checkout origin/main -- <文件>` 对齐 → 再改。
禁止 force push、禁止 `--theirs` 盲目覆盖。
改 vessels/ports/cul_vessel_bestmodel.csv 时推送前必须 `python audit_data_loss.py` 退出码 0。
推送后：`git fetch` + `git show origin/main` 验证（raw 有 CDN 缓存，别信 raw）。

## 数据文件格式
- ports.csv：code,name_en,name_cn,man_in,portstay_time,wait_time,lat,lon。
- vessels.csv：vessel_code,vessel_name,speed_knots,lsfo,hsfo,mgo,portstay_lsfo,portstay_mgo,hire_daily。
- distances.csv：from,to,dist_nm,source('manual'/空=实测，'auto'被 L2 剔除)。直接追加即可。
- cul_vessel_bestmodel.csv：按船名匹配页面 Vessel Info；拆 lane（AEM/REX 各行）。
- cul_ship_particular.csv：**转置表**，每列一艘船、16 字段；新增船=每行末尾追加一列；页面按船名模糊匹配无需改 HTML。
- **CRLF 铁坑**：git 内 CRLF、工作树 LF，正常。脚本必须 `splitlines()`+`'\n'.join`，禁止 `split('\n')` 直接拼（残留 \r 会错位）。

## 核心计算（固定）
run=dist/speed（不含 manIn）；ETA=上港ETD+run；ETB=ETA+manIn+wait；ETD=ETB+portStay。

## 距离引擎（三层真实海路，2026-08）
必须真实海路不能直线。L1 distances.csv 直连 → L2 实测图 Dijkstra → L3 basin/gateway 航路点 Dijkstra。融合 MdAPE=1.06%。实现 `srDistance`（SR_BASINS/SR_GATES + srDijkstra）；L2 只收 source!='auto' 且剔除坏边(d<大圆×0.90)。参考 searoute_core.py。坐标审计：actual/haversine<0.95=坐标错（已修 7 港）。

## PTX（2026-07）
ptx_averages.json，三层 fallback：Direct → Similar(≥0.60) → $0。

## Best Model 合并铁律（2026-07）
Excel：`C:\CULINES\Claw Report\CUL Vessel Best Model Report - 2026.xlsx`。以当前 CSV 为基底，Excel 有值才覆盖 cols 2-10（Vessel Name/Lane/Remark 不覆盖），新 vessel/lane 追加，不删 CSV-only 行。复用脚本 `archive/export_excel/merge_bestmodel.py`（默认 dry-run）：norm_key 船名归一、lane_match=raw 相等 or token 子集、consumed 防同名多行重吃。

## Port wait 更新（P盘 Port Condition Week N）
`P:\04 上海操作中心\01 船期管理科\船期管理\VSL Daily Movement\Port Condition\Port condition Year 2026 Week N.xlsx`
- **铁坑**：累积周报档案，必须按 workbook.xml `name='Week N'` 反查 sheet 文件，绝不能 auto-detect。
- 解析 zipfile+xml（openpyxl 报样式错不用）；Python 用 Windows 原生路径 P:/。
- parse_wait 取 **MIN**：`>Xhrs`→X；`X>Yhrs`→X；`<Xhrs`/`N`/`NIL`→0；只采信 C 列 hrs 标记。
- NIL=无船≠0：另有有船码头取其 min；整港无船记 0。
- 只更新已有港。流程：对齐→改第6列(BOM+CRLF 保留)→audit PASS→push→git show 验证。

## Excel 导出（ExcelJS 4.4.0）
要样式必须 ExcelJS（SheetJS 社区版无样式）。**铁坑**：ExcelJS UTC 序列化，GMT+8 少 8 小时 → `xlDate(d)=new Date(d.getTime()-offset*60000)`。
实时公式模式（默认勾选）：ETA/ETB/ETD/Run/Fuel 写 Excel 公式（ROUNDUP 取整到小时=网页 ceilToHour），CHAIN_KEYS 强制导出。验证脚本 archive/export_excel/verify_export_excel.cjs + verify_export_formula.cjs + evaluate_formulas.py；切片前 `.replace(/\r\n/g,'\n')`；exceljs 装在 ~/.workbuddy/binaries/node/workspace。

## TCD 解析器（Paste & Parse）
📋 Paste & Parse / 📤 Upload File → `parseVesselTextClient` → `displayParseResult` → `saveParseVessel`（需 GitHub Token 才 PUT）。
- letter-spaced PDF：必须 `layoutPdfText`（y 聚类成行、gap>0.3em 才插空格）；test_real_tcd_files.cjs 镜像同步。
- 辅机海上油耗**并入**每档（2026-08-13 用户定）：buildFuelTiers 把 seaAdd 并入各档对应油种，fuelRemark 提示防重复。守卫：bumpAdd 同油种首次命中即停；reefer 高负载行跳过；双栏标题不触发 AUX；KR CELEBES 专用抓 Aux. Sailing/Port。
- tabular 油耗表双重守卫：关键词排除备注行 + 数值范围(speed 3-30/foc 1-250)。
- 回归：test_parse_harness(54/54)、test_particular_csv、test_save_integration(25/25) 全绿才上。
- **上线铁律**：用户拿真实样本验收前不 commit/push。
- Excel 上传（2026-08-25 新增）：accept 加 .xlsx/.xls，`parseExcelContent` 用页面已装 SheetJS 逐 sheet 转"行内空格连接"文本（去千分位逗号）再走同一 parser；XLSX 静态加载无需 dynamic load。

## 用户偏好
报告中文、结构化表格；UI 标识英文。距离必须真实海路。导出排版专业且与网页视觉一致。
