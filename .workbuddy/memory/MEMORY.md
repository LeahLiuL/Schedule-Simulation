# MEMORY.md

## 项目概览
航运调度模拟系统：shipping_schedule.html  
GitHub: https://github.com/LeahLiuL/Schedule-Simulation  
线上: https://leahlil.github.io/Schedule-Simulation/shipping_schedule.html

## 船只数据规范
- 文件：`shipping_data/vessels.csv`
- 格式：`vessel_code,vessel_name,speed_knots,lsfo_mt_day,hsfo_mt_day,mgo_mt_day,portstay_lsfo_mt_day,portstay_mgo_mt_day`
- 关键字段：第6列=停泊LSFO，第7列=停泊MGO

## 数据存储架构（2026-04-24 更新）

### ports.csv 新增列
- 第 7 列 `lat`：纬度
- 第 8 列 `lon`：经度
- 格式：`code,name_en,name_cn,man_in,portstay_time,wait_time,lat,lon`
- 243 个港口已从 PORT_COORDS 迁移到 CSV

### PORT_COORDS 构建逻辑
- `let PORT_COORDS = {}` — 初始为空
- `buildPortCoords()` — 从 PORTS_DATA 第 6-7 列（lat/lon）构建坐标表
- `PORT_COORDS_FALLBACK` — 仅保留 CSV 中没有的港口（如 AUBNE, USSEA 等内陆/偏远港）
- 调用时机：init()、loadData()、editDmPort()、deleteDmPort()、addDmPort()、reload 后

### Data Manager Ports 表格
- 新增 Latitude、Longitude 两列，可直接在页面编辑

## Bug 与修复记录

### 推送验证必做（2026-04-15 新增）
git push 后必须执行：
1. `git fetch origin main`
2. `git log --oneline origin/main -1` 确认最新 commit
3. web_fetch 验证 raw.githubusercontent.com 包含目标数据
4. 直到上述验证全部通过才能告诉用户"好了"

### 重要：本地文件必须与 GitHub 同步（2026-04-15）
- `fleet_schedule.json` 在浏览器 commit 时更新的是 GitHub，不自动更新本地
- 每次打开工作区后，用 `git checkout origin/main -- shipping_data/fleet_schedule.json` 同步
- 或者浏览器 commit 后立即 pull，保持本地与 GitHub 一致
- **本地文件 ≠ GitHub 上的文件**，浏览器 commit 不更新本地工作区

### 同步到 Daily 时保留原始数据（2026-04-15）
- syncToDaily 使用 fmtDtLocal() 正确格式化 Date 对象
- 编辑 ETB/ETD 时不再覆盖 waitHrs 和 stayHrs（保留手工值）
- syncToDaily 自动 commit 到 GitHub，无需确认
- **重要修复**：syncToDaily 前必须先从 GitHub 重新加载数据，避免使用损坏的 localStorage 数据

### localStorage 风险（2026-04-15）
- localStorage 可能有损坏/不完整的数据
- syncToDaily 前会强制从 GitHub 重新加载最新数据
- 禁止使用 localStorage 作为数据来源

### Lanes 数据加载（2026-04-15 完）
- LANES_DATA **无静态默认值**，全部从 GitHub 加载
- `loadAllData()` 在页面加载时调用 `loadLanesData()`
- `initDailyPage()` 在切换到 Daily 标签时重新加载
- Data Manager 的 `⬆ Commit` 按钮会提交 lanes.json 到 GitHub
- `loadLanesData()` 使用 GitHub API（无缓存）

### 历史 Bug
| Bug | 原因 | 修复 |
|-----|------|------|
| Port stay 时间不生效 | computeSchedule 读默认值 | 优先用 p.stayHours |
| Port wait 时间丢失 | CSV 只读5列 | 添加第6列 wait_time |
| Sync 后 ETA 为空 | Date 不能用于 datetime-local | 添加 fmtDtLocal() |
| Sync 按钮太小 | CSS 问题 | 加大样式 |
| Sync 流程繁琐 | 多次 prompt | 单航线自动使用 |
| 近1个月过滤无反应 | `String(Date)` 返回非ISO格式 | 用 `toDateStr()` 辅助函数处理 Date/字符串 |
| syncToDaily 覆盖问题 | 加载失败时静默失败，FLEET_DATA 为空导致覆盖 | 添加验证：加载失败时拒绝保存 |

## 核心计算逻辑（最重要，多次确认后固定）

所有涉及时间计算的地方（daily view、单船调度、continuous view、Excel导入）必须严格遵循：

| 字段 | 公式 |
|------|------|
| **run** | dist / speed（纯海上航行时间，**不含 manIn**） |
| **ETA** | 上一港 ETD + run |
| **ETB** | ETA + manIn + wait |
| **ETD** | ETB + portStay |
| **seaDays** | totalRunHrs / 24（不含 manIn） |

**重要**：`run = dist/speed`，不是 `dist/speed + manIn`。这个逻辑在多个地方都要保持一致。

## Daily 船期编辑 speed 的行为（2026-04-23）

### Bug 1：修改 speed 后值跳回原值
- **原因**：`recalcDailyFromPort` 重算后续港口时，会用下一港已有 ETA 反推 speed，覆盖用户刚输入的值
- **修复**：`recalcDailyFromPort` 添加第四个参数 `skipSpeedBackfill`，speed 编辑时传 `true` 跳过反推

### Bug 2：修改 speed 后后续时间没变
- **原因**：`recalcDailyFromPort` 碰到后续已有 ETA 时优先用旧值反推，而不是正向计算
- **修复**：编辑 speed 时，先清除后续所有港口的 ETA/ETB/ETD，再调用重算强制正向推演

## Port man_in 时间表（2026-04-23 更新）

| PORT | Main in | PORT | Main in | PORT | Main in | PORT | Main in |
|------|---------|------|---------|------|---------|------|---------|
| AEJEA | 2 | CNNAS | 3 | CNSWA | 2 | DJJIB | 2 |
| AEKLF | 2 | CNNGB | 3 | CNTAO | 2 | EGALY | 2 |
| EGSOK | 2 | INMUN | 2 | INNSA | 2 | MYPKG | 2 |
| OMSOH | 2 | PHMNL | 3 | PKKHI | 2 | SADMM | 2 |
| SAJED | 2 | SDPZU | 2 | SGSIN | 2 | THBKK | 3 |
| THLCH | 2 | THSCS | 3 | THSSW | 3 | TRALI | 2 |
| TRIST | 2 | TRIZT | 2 | TRMER | 2 | TWKEL | 2 |
| TWKHH | 2 | TWTPE | 2 | TWTXG | 2 | VNHPH | 2 |
| VNSGN | 4 | VNVUT | 2 | YEADE | 2 | CNSHA | 5 |
| CNSHK | 3 | CNYTN | 2 | | | | |

- THSSW (SUKSAWAT, BANGKOK) 是 2026-04-23 新增的港口代码
- man_in 存储在 `ports.csv` 第4列

## 用户偏好
- 报告输出：中文，结构化表格
- UI 标识：保留英文
- 自动化流程：按顺序执行，编号步骤

