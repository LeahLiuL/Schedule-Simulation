# sftp-vessel-data-update (备份副本)

本目录是 `~/.workbuddy/skills/sftp-vessel-data-update/` 的**版本备份**，用于另一台电脑每天自动更新船期数据时拉取使用。

## 内容
- `scripts/update_vessel_data.py` —— 从 SFTP 拉取 Excel 并生成 `shipping_data/bi_vessel_departure.csv`，已排除 TBN 占位船（TBN1/TBN2...）。
- `scripts/generate_voyage_report.py` —— 生成 CUL 航次报告 HTML，同样排除 TBN 占位船。
- `SKILL.md` —— 技能说明文档。

## 另一台电脑如何同步
WorkBuddy 技能目录（`~/.workbuddy/skills/`）默认不在 git 仓库内，不会随仓库自动同步。请在另一台电脑执行：

```bash
# 在 Schedule-Simulation 仓库目录下
git pull origin main
mkdir -p ~/.workbuddy/skills/sftp-vessel-data-update/scripts
cp sftp-vessel-data-update/scripts/*.py ~/.workbuddy/skills/sftp-vessel-data-update/scripts/
cp sftp-vessel-data-update/SKILL.md       ~/.workbuddy/skills/sftp-vessel-data-update/
```

完成后再跑每日自动化，生成的数据即自动剔除 TBN 占位船。

## 修改流程
1. 在本机修改 `~/.workbuddy/skills/sftp-vessel-data-update/` 下的脚本；
2. 把改动同样复制到本仓库 `sftp-vessel-data-update/`；
3. 提交并推送到 `Schedule-Simulation`；
4. 另一台电脑 `git pull` 后覆盖技能目录。

> 注意：页面 `bi_vessel_departure.html` 的 `dedupeVesselRows()` 仍保留 TBN 显示层过滤作为双保险，即使源 CSV 仍含 TBN，页面也不会展示。
