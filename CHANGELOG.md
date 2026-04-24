# Changelog - shipping_schedule.html

> 航运调度模拟系统 · 开发历史记录

---

## v2.0 (2026-04-14 ~ 2026-04-24)

### 🐛 Bug 修复

| 日期 | Commit | 内容 |
|------|--------|------|
| 2026-04-23 | `c7711e3` | **修改 speed 后后续时间没变**：编辑 speed 时先清除后续所有港口的 ETA/ETB/ETD，再强制正向推演 |
| 2026-04-23 | `db362d3` | **Daily 船期修改 speed 值跳回原值**：`recalcDailyFromPort` 添加 `skipSpeedBackfill` 参数，跳过反推逻辑 |
| 2026-04-22 | `e28d753` | 修复 btnSyncDaily/tbModBadge/btnReset 元素 null 检查 |
| 2026-04-22 | `f8b7270` | 修复 Vessel Info 弹层 z-index 被 Data Manager 遮挡的问题 |
| 2026-04-22 | `42fdd96` | 修复 `normalizeName` 和 `escapeHtml` 函数缺失问题 |
| 2026-04-22 | `489fbeb` | 修复打开 Vessel Info 面板时未自动选船的问题 |
| 2026-04-22 | `93db1bd` | 修复 `renderViParticular` 返回值未赋值给 body.innerHTML 的问题 |
| 2026-04-22 | `9e01c5e` | 修复 line 2373 处 `catch()` 缺少 `)` 导致 SyntaxError |
| 2026-04-17 | `2b3bc31` | **H728 船名格式支持**：支持含数字的船名（1-5位字母+数字）|
| 2026-04-17 | `70e1978` | 修复 file:// 模式下本地服务器不可用时的 fleet 数据加载 |
| 2026-04-17 | `741ecad` | 修复 GitHub Pages 上 fleet 数据加载（优先本地服务器，失败则回退 GitHub）|
| 2026-04-17 | `11bec1f` | 修复 Import Format B：船名优先匹配 1-5 位字母+数字格式（如 H728）|
| 2026-04-17 | `dd69d03` | 修复 Import 支持含数字船名；file:// 模式跳过本地 fetch；lanes/fleet CDN 路径 |
| 2026-04-17 | `ef3262c` | 恢复 handleImportExcel；修复本地时间解析；支持 H728 船名 |
| 2026-04-17 | `c94367a` | Import/Sync 时保持日期不变，通过调整航速来适配 |
| 2026-04-17 | `e193bfb` | Daily Import 只读取第一个 Excel sheet |
| 2026-04-15 | `3e6497d` | 修复 port wait_times：CNNAS=12, CNNGB=12, CNSHK=12, THBKK=12, MYPKW=24 |
| 2026-04-15 | `8570bbe` | 修复 daily 时间范围筛选的时区 bug |
| 2026-04-15 | `3523e28` | 修复时间筛选：显示过去+未来区间（如 3m=±3个月）|
| 2026-04-15 | `a9bbf6b` | 修复 syncToDaily：保留 manIn/stayHrs/waitHrs 值，commit 后自动推 GitHub |
| 2026-04-15 | `b444b4b` | 修复 localStorage 损坏时 syncToDaily 覆盖全部数据的问题 |
| 2026-04-14 | `13e28af` | 简化 Sync 按钮；优化 syncToDaily 流程 |
| 2026-04-14 | `97db68d` | 加载 CSV 时包含 wait_time 列；computeSchedule 优先使用用户修改的 stay 时间 |
| 2026-04-14 | `3ed688d` | 单船调度优先使用用户修改的 stay 时间而非默认值 |

### ✨ 新功能

| 日期 | Commit | 内容 |
|------|--------|------|
| 2026-04-22 | `0695df6` | **Speed Optimizer**：新增航速优化工具，用图表对比不同航速下的燃油消耗 |
| 2026-04-22 | `da7216d` | Speed Optimizer 表格头部使用深色主题样式区分 |
| 2026-04-22 | `1841df5` | **Vessel Info 面板**：从 GitHub CSVs 加载 Particular + Best Model 容量 + 燃油数据 |
| 2026-04-22 | `050c5cc` | **Vessel Info 面板**（Particular + Best Model + 燃油数据）|
| 2026-04-22 | `f68fb83` | Vessel Info 面板：code↔name 匹配、全部 3 个 tab 正常工作、Max TEU2 列 |
| 2026-04-22 | `6160326` | 重命名重复的 Max TEU 列名为 Max TEU2 |
| 2026-04-21 | `303e3f6` | Data Manager Lanes tab 新增 Ports 列（逗号分隔），支持 Lane-Port 旋转 |
| 2026-04-21 | `826c0bd` | 为 11 条航线添加 port rotations：ST1, HDT, NSX, CST, CCT, NP2, CGX, SGX, IMR, SJA, JPS |
| 2026-04-21 | `1a4332b` | 新增 24 条航线：AG1, AGX, AM1, BC1, CCT, CGS, CHT, CIS, CL1, CL2, CP1, CV2, CVT, CVX, IMR, NP2, NSX, RCS, SC2, SHX, VG1-3, VGX |
| 2026-04-20 | `cccc782` | 修复从 Lane 添加 Ports 的 dist 计算逻辑 |
| 2026-04-17 | `f780822` | Data Manager 端口/船只/航线按 code 升序排序 |
| 2026-04-15 | `3dcace0` | Data Manager Lanes tab 新增 Ports 列，支持内联编辑 |
| 2026-04-15 | `ec92313` | 新增 30 条航线：AEM, AEX, AG2, AG3, CES, CMX, CNX, CPX, CST, CV5, HDT, JPS, REX, SCT, SEG, SGX, SH2, SH3, SJA, SL1, ST1, ST3, STD, STX, SV2, TP1, TPC, TPN, TPX, TST |
| 2026-04-15 | `e2ee0d3` | 修复 CSV_GITHUB URL 拼写错误：leahliul → LeahLiuL |
| 2026-04-14 | `9c9052c` | 新增"近1个月"时间筛选选项 |

### 📊 数据更新

| 类型 | 详情 |
|------|------|
| **新增船只** | ZGCD, ZGNC, RACE (Racine), CASR, MKLA, M/V ASR, NE45 NEW BUILDING 4350, MEDKON LIA, EVERLASTING HARVEST, EXPRESS BERLIN, HOOGE, BZ CHONGFU |
| **船只更新** | ZHONG GU YIN CHUAN / NAN CHANG / CHENG DU：添加 loading capacity、particulars |
| **港口更新** | 更新 38 个港口的 man_in 时间；新增 THSSW (SUKSAWAT, BANGKOK) |
| **等待时间** | 22 个港口的 wait_times：CNNAS=12, CNNGB=12, CNSHK=12, THBKK=12, MYPKW=24 等 |
| **距离更新** | distances.csv 多版本更新 |
| **航线更新** | lanes.json：新增 30+ 条航线，含 port rotations |
| **排期更新** | fleet_schedule.json 持续更新 |

### ⚙️ 系统改进

| 日期 | Commit | 内容 |
|------|--------|------|
| 2026-04-22 | `519b0b6` | 新增本地服务器模式：fetchCSV/loadLanesData 优先使用 /data/ 端点 |
| 2026-04-17 | `1e1a0e5` | 移除 Simulator 工具栏中重复的"添加到 Daily"按钮 |

---

## v1.0 (2026-04-14 之前)

> 初始版本，Git 历史从 2026-04-14 开始记录

### 初始功能
- 单船调度（Simulator）：按航线、航速、ETA 自动计算各港 ETA/ETB/ETD
- Daily 船期视图：多船排期总览，支持时间筛选
- Continuous 视图：连续航次展示
- Data Manager：港口、船只、航线、距离数据管理
- Excel 导入/导出
- GitHub 同步（commit 后自动推送到 GitHub Pages）
- localStorage 本地持久化

---

## 核心计算逻辑（重要）

```
run      = dist / speed    （纯海上航行时间，★不含 manIn★）
ETA      = 上一港 ETD + run
ETB      = ETA + manIn + wait
ETD      = ETB + portStay
seaDays  = totalRunHrs / 24
```

> 此逻辑在 daily view、单船调度、continuous view、Excel 导入中必须保持一致。
> `run ≠ dist/speed + manIn`，manIn 只加在 ETB，不加在 run。
