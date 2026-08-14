# MEMORY.md

## 项目概览
航运调度模拟系统：shipping_schedule.html（位于仓库根目录，非 shipping_data/）
GitHub: https://github.com/LeahLiuL/Schedule-Simulation
线上: https://leahlil.github.io/Schedule-Simulation/shipping_schedule.html
数据目录：shipping_data/

## ⚠️ Git 操作铁律（最高优先级）
用户只在浏览器端编辑/commit 数据（GitHub API），本地文件不会自动同步。
任何本地修改前：1) `git fetch origin main` 2) `git checkout origin/main -- <文件>` 对齐 3) 确认一致再改。
禁止：`git push --force`、`git checkout --theirs` 盲目覆盖冲突（会丢浏览器 commit 的数据）。
推送前：跑 `python audit_data_loss.py`（改 vessels/ports/cul_vessel_bestmodel.csv 时，退出码 0 才可推）。
推送后验证：1) `git fetch` 2) `git log --oneline origin/main -1` 3) `web_fetch` raw.githubusercontent.com 确认内容。

## 数据文件格式
- `ports.csv`：code,name_en,name_cn,man_in,portstay_time,wait_time,lat,lon（第7-8列坐标，243+港）。
- `vessels.csv`：vessel_code,vessel_name,speed_knots,lsfo,hsfo,mgo,portstay_lsfo,portstay_mgo,hire_daily。
- `distances.csv`：from_port,to_port,distance_nm,source。CRLF 行尾、无 BOM。source='manual'(实测) / 'auto'(旧 haversine 回填) / 空(原始实测)。只有 'auto' 被 L2 图剔除，空与 manual 都参与。新增实测边直接追加一行即可（文件本身无排序）。
- `cul_vessel_bestmodel.csv`：按船名匹配页面 Vessel Info；lane 用拆 lane（AEM/REX 两行）。
- `cul_ship_particular.csv`：**转置表**——第1行首列是 `VESSEL NAME`，其余每列是一艘船；第2行起每行是一个字段（CALL SIGN/IMO/FLAG/YEAR BUILT/NOMINAL CAPACITY (TEU)/HOMO @14 MT/GRT/NRT/SCANTLING DRAFT (m)/DWT (MT)/LOA (m)/BREADTH (m)/DEPTH (m)/REEFER PLUGS/CLASS）。**新增船 = 在每行末尾追加一列**（16 个字段值）。页面 `loadParticularData()` + `findParticularKey()` 按船名（模糊，含首词子串）动态匹配，无需改 HTML。船名列建议与 vessels.csv 的 vessel_name 一致以便自动匹配；若不一致（如 BZCF 在 vessels.csv 叫 `BZ CHONGFU` 而 particulars 叫 `PMDS BZ CHONGFU`），模糊匹配仍能连上。
- **CRLF 铁坑**：仓库里 CSV（含 cul_ship_particular.csv）git 以 CRLF 存储，checkout 到工作树时转 LF；改完提交时 git 又转回 CRLF（正常，会有 "LF will be replaced by CRLF" 警告，无害）。**追加列脚本必须用 `content.splitlines()` 归一行尾再 `'\n'.join` 写回**，绝不能用 `split('\n')` 后直接拼——否则残留 `\r` 会卡在行中间导致 CSV 解析错位（实测 csv.reader 行数翻倍、字段错乱）。diff 显示 200/200 是行尾归一造成，非真改动。

## 核心计算逻辑（固定）
run = dist/speed（纯海上，不含 manIn）；ETA = 上港ETD + run；ETB = ETA + manIn + wait；ETD = ETB + portStay；seaDays = totalRunHrs/24。

## 距离计算架构（2026-08，三层真实海路引擎）
**第一计算逻辑必须考虑真实海路，不能用直线（用户明确要求）。**
- L1：distances.csv 实测直连（精确，优先）。
- L2：实测距离图 Dijkstra 最短路（真实航段之和），长航线 MdAPE<1%。
- L3：海域(basin)/关口(gateway) 航路点网络 Dijkstra（海峡/运河/海角分段大圆），图外港口兜底，绝不穿越陆地。
- 融合 MdAPE=1.06%（原 haversine×1.08 方案 4.90%）。
- 实现：`fetchHaversineDistance` 调 `srDistance`（SR_BASINS/SR_GATES/SR_RIVER 数据 + srSeaRoute/srDijkstra）。
- L2 图只纳入 source!='auto' 的实测边，剔除坏边(d<大圆直线下限×0.90)。
- `buildDistMap()`/`buildPortCoords()` 置 `SR_DIRTY` 触发路由图重建。
- 源算法参考 `searoute_core.py`（archive/router_engines/），JS 端口经 py_ref.py+validate_js_port.cjs 逐对校验一致(误差0nm)。

## 坐标审计方法
ports.csv 坐标错误用 distances.csv 实测短边交叉验证：actual/haversine < 0.95 即物理不可能=坐标错。
已修正 7 港：THLCH(13.08,100.88) CNZJG(31.94,120.55) SAJED(21.48,39.19) SDPZU(19.62,37.22) DZALG(36.77,3.06) THSSW(13.63,100.5) CNGCT(23.0,113.5)。

## PTX（Port Charges）计算（2026-07）
`shipping_data/ptx_averages.json`：{shipCode:{portCode:{avg,n,terminals,source}}}。
三层 fallback：Direct → Similar(相似度≥0.60才用) → 写$0。terminalCode[:5]→Simulator港代码。

## Vessel Best Model 合并铁律（2026-07）
每次从 Excel 更新 capacity 必须全量对账（曾丢 CUL BANGKOK+7船）。以当前 bestmodel.csv 为基底；
Excel 有值才覆盖；Excel 用组合 lane(AEM/REX)→按 token 重叠回退匹配拆 lane；命名归一 SHENGTANG↔SHENG TANG。
Excel：C:\CULINES\Claw Report\CUL运营船舶装载Best Model - 2026.xlsx（sheet 装载Best Model），用 zipfile 解析。

## Port wait 更新流程（P盘 Port Condition Week N）
- 数据源：`P:\04 上海操作中心\01 船期管理科\船期管理\VSL Daily Movement\Port Condition\Port condition Year 2026 Week N.xlsx`
- **⚠️ 铁坑**：该 xlsx 是**累积周报档案**，每个 worksheet 对应一周（`sheet1=Week1` … `sheet29=Week30`、`sheet30=Week31`、`sheet31=Received record`）。**绝不能用 auto-detect 选"匹配行最多"的 sheet**（会误选 Week1 等旧周次，解析出 YEADE=192 等错误旧值）。必须按 `workbook.xml` 的 `name='Week N'` 反查对应 sheet 文件（Week 31 → sheet30.xml）。
- 解析：zipfile+xml（openpyxl 报 Fill 样式错误故不用）；sharedStrings + worksheet；A 列端口带终端后缀→取首词前缀作 5 位 code；C/D/E 列 parse_wait。
- parse_wait 规则（沿用 7-28，MIN）：`>Xhrs`→X；`X>Yhrs`→下界 X；`<Xhrs`/`N`/`NIL`→0；同港多码头/多行取 min。D 列 "X-Y HRS" 描述文本**不解析**（历史做法只采信 C 列明确 hrs 标记）。
- 规则选择：7-28 用户确认用 **MIN**（INNSA 当前 6=最小值故不变；MAX 会 6→12）。
- 矛盾处理：C 列 `<6hrs` 但 D 列描述 24-36hrs（如 THLCH/THSCS）→ 信 C 列保持 0（2026-08-07 确认）。
- 仅更新 ports.csv 已有港，不新增（除非用户明确要求）。
- 流程：fetch+checkout 对齐 → 改第6列 wait_time（utf-8-sig+CRLF 保留）→ `audit_data_loss.py` PASS → commit → push → `git show origin/main` 验证（raw 有 CDN 缓存滞后，用 origin/main 对象验证）。

## 数据完整性审计（2026-07，复用）
`audit_data.py` 遍历 git 历史提取实体全集比对当前文件，列出"曾存在但现缺失"。
改前 `git fetch && git checkout origin/main -- <文件>`。`git show` 含 BOM→`h[0]=h[0].lstrip('\ufeff')`。
已知代码不一致：distances.csv/BZ 用 EGSUE，ports.csv 用 EGSUZ（苏伊士，待统一）。
2026-08-06 已固化 `OMDQM,CNTAO,5619,manual`（原待确认项，现命中 L1）。

## Excel 导出（2026-08，ExcelJS）
页面已引入 **ExcelJS 4.4.0**（HTML 第13行）与 SheetJS 两个库。**要样式必须用 ExcelJS**（SheetJS 社区版不支持单元格样式）。
Simulator `exportExcel()` 已改 ExcelJS：`XL_PAL` 色板与表格 CSS 同色，`xlColSpec(col)` 按 `COL_DEFS.key` 决定列格式，自动跟随「☰ Columns」隐藏列。
**铁坑**：ExcelJS 按 UTC 序列化 Date → GMT+8 下时间少 8 小时。写日期一律套 `xlDate(d)=new Date(d.getTime()-d.getTimezoneOffset()*60000)`。
验证脚本 `archive/export_excel/verify_export_excel.cjs`：正则切片提取 HTML 内真实导出源码 → node vm + mock DOM + 真 exceljs 生成 xlsx → openpyxl 读回断言 fill/font/numFmt/merge/formula/freeze。切片前需 `.replace(/\r\n/g,'\n')`（文件 CRLF）。exceljs 装在 `~/.workbuddy/binaries/node/workspace`。

### 实时公式模式（2026-08-06 新增）
Export Excel 按钮旁新增「实时公式」勾选框（默认勾选）。勾选时 `exportExcel()` 把 ETA/ETB/ETD/Run/Fuel 写成 **Excel 公式**而非静态值，改任一时间下游自动联动：
- `ETA_i(i>0) = IFERROR(ROUNDUP((ETD_{i-1}+dist_{i-1}/speed_{i-1}/24)*24,0)/24, ETD_{i-1})`（ROUNDUP 取整到小时 = 网页 ceilToHour）
- `ETB_i = ETA_i + (manIn_i+wait_i)/24`，`ETD_i = ETB_i + stay_i/24`
- `Run = dist/speed`，`Fuel = dist/speed * lsfo/24`（lsfo 常数内联）
- 首港 ETA 为可编辑静态种子；Summary 首/末 ETA 与合计也用 `'Voyage Schedule'!...` 公式引用主表。
- **强制携带链路列**（CHAIN_KEYS = eta/etb/etd/dist/speed/manIn/wait/stayHrs/runHrs，即使网页隐藏也导出）以保证公式不破链；其余列仍跟随「☰ Columns」隐藏设置。
- 取消勾选 → 退回原静态快照行为（0 公式）。
- 验证：`archive/export_excel/verify_export_formula.cjs`（node 提取真实源码，FORMULA 环境变量切静态/公式）+ `archive/export_excel/evaluate_formulas.py`（自写最小公式求值器，直接 eval xlsx 内真实公式，验证数值自洽与 +5h 联动）。

## TCD 解析器（Paste & Parse，shipping_schedule.html）
Data Manager → Vessels → 📋 Paste & Parse / 📤 Upload File：文本经 `parseVesselTextClient` 解析 → `displayParseResult` 填 modal → `saveParseVessel`（需 GitHub Token 才 PUT，否则 `showParsePreview` 复制 CSV）。
- **letter-spaced PDF**：某些 TCD 把每个字形当独立 item 吐出、词被拆字母。必须用 `layoutPdfText`（按 y 聚类成行、行内仅当横向 gap>0.3em 才插空格）而非 `items.map(it=>it.str).join(' ')`。`test_real_tcd_files.cjs` 内镜像须同步。
- **辅机海上油耗并入主机档（2026-08-13 用户定）**：`buildFuelTiers` 现把 `seaAdd`（辅机海上油耗，约恒定）**并入每一航速档**的对应油种列（主+辅=真实总海上油耗）；`result.fuelRemark` 输出"已并入≈X MT/天(:油种)，若 TCD 每档已含辅机请勿重复计算"。vessels.csv 无独立 aux-at-sea 列，故合并进 lsfo/hsfo/mgo。
  - **防重复/误判守卫**（缺一不可）：① `bumpAdd` 对 `seaAdd` 同油种**首次命中即停**（KOTA 散文"about 10 m/t"+A/E表"10.0"重复，避免 10+10=20）；② 海上辅机行含 `\breefer\b` 跳过（KOTA "A/E WITH/REEFER 15.5" 是高负载点非基础值）；③ 双栏标题 `MAINENGINE,AUXILIARYENGINE,...` **不触发** AUX 小节（否则 KR CELEBES 把主机 NCR 21.7 错当辅机）；④ KR CELEBES 风格辅机负载表用专用正则抓 `Aux. Sailing/Port` 基数（1.4/1.0 HSFO），`docHSFO` 决定油种。
  - **在港辅机**：`portAdd` 一直计入 `portstay_lsfo/portstay_mgo`（HSFO 折进重油港列），无变化。
- **tabular 油耗表**：表头 `Ship Speed[knots]FOC(MT)Rpm`，数据行 `9.8 6.6 107`。守卫必须双重：`/fuel|lcv|kcal|kg|consumption|based|cst|reef|remarks?|note/i` 关键词排除备注行 + 数值范围（speed 3–30kn、foc 1–250MT）排除 "LCV 10200" 类备注被当数据行。
- **DWT 粘连（letter-spaced）**：`DEADWEIGHTANDCAPACITY` 与值分行（值 `Atdesigndraught(Summer)=10700.8mt`）。去空格二次 pass 用 `/deadweight/i`（无 `\b` 尾边界）向后扫 5 行匹配 `draught(...)[=:]X\s*mt`（mt 区分 draft 的 m）。
- 验收：`node --check` 抽取 script 块；三大回归 `test_parse_harness`(54/54)、`test_particular_csv`、`test_save_integration`(25/25) 全绿方可上。
- **⚠️ 上线铁律**：本地充分测准，**用户拿真实 PDF/Word 样本验收前不 commit/push**（用户原话"先测准再上线"）。

## 用户偏好
- 报告：中文、结构化表格；UI 标识保留英文；自动化按顺序编号执行。
- 距离/航线计算：必须真实海路，误差最小化。
- 导出文件：要求排版专业，且**视觉与网页显示保持一致**（同配色/同结构）。
