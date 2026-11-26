#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据更新前「全量对账 + 无丢失确认」脚本
============================================
用途：
  每次修改 shipping_data 下的三个数据文件并推送前，运行本脚本。
  它会对比：
    1) 工作区当前文件  vs  线上 origin/main（刚部署的版本）
    2) 工作区当前文件  vs  该文件【全部历史 commit】（曾经存在过的实体全集）
  任何「曾经存在 / 线上存在，但现在工作区里没了」的船/港，都会被报告，
  并按「是否在【已部署的 git 跟踪文件】中被引用」分类为：
    - 真丢失（被引用）：必须恢复，脚本判定 FAIL
    - 孤儿（未引用）：仅提示，不阻断
    - 改名/垃圾：自动识别并排除

  关键点：
    * 引用检索只在「git 跟踪的部署文件」中进行，不会误伤本地临时脚本/预览文件。
    * Best Model 按「船名」比对（与网页 Vessel Info 弹窗的匹配方式一致），
      避免因航线拆分/合并产生的噪音误报。
    * 冲突标记 / 纯数字 / 表头残留等垃圾 token 自动过滤。

退出码：
  0 = 无真丢失（可放心推送）
  1 = 检测到真丢失（必须先恢复再推送）

用法：
  python audit_data_loss.py                 # 审计全部三个文件
  python audit_data_loss.py --only vessels  # 只审计某个文件
  python audit_data_loss.py --strict        # 孤儿也算 FAIL（更严格）
"""
import subprocess, csv, io, sys, os, re, argparse

REPO = os.path.dirname(os.path.abspath(__file__))

# 每个文件：路径、实体所在列、类型标签、kind
FILES = [
    {"path": "shipping_data/vessels.csv", "col": 0, "kind": "vessel", "label": "Vessels(船)"},
    {"path": "shipping_data/ports.csv", "col": 0, "kind": "port", "label": "Ports(港)"},
    # Best Model 按船名(col0)比对；lane 差异属正常合并，不计入丢失
    {"path": "shipping_data/cul_vessel_bestmodel.csv", "col": 0, "kind": "vesselinfo",
     "label": "Vessel Info(Best Model)"},
]

# 已知改名映射（旧码/旧名 -> 当前码/名），用于自动排除"改名"误报
KNOWN_RENAMES = {
    # 2026-11-26: 船码以 Port Charges 账单 shipCode 为准。
    # 之前按 Full Schedule 去重产生的准码，已改回 Port Charges 旧码，
    # 所以审计白名单方向也反过来（准码 -> Port Charges 码）。
    "vessel": {
        "CSJ": "CSJ8", "SDAL": "SHTG", "RACINE": "RACE",
        "CUST": "SHTG",       # SHENG TANG: 与 Port Charges 一致
        "SDAM": "SHTG",       # 旧混合码（Sidra Ahlam / SHENG TANG）
        "CASR": "ASRR",       # ASR: 与 Port Charges 一致
        "CUML": "CUMN",       # CUL MANILA: Full Schedule 准码 -> Port Charges 码
        "SISO": "SNSO",       # SINAR SOLO: Full Schedule 准码 -> Port Charges 码
        "XHDL": "XHDP",       # XH DOLPHIN: Full Schedule 准码 -> Port Charges 码
        "ZGXA": "ZGOA",       # ZHONG GU XIONG AN: Full Schedule 准码 -> Port Charges 码
        "STBL": "STBE",       # STAR BLESSING: 与 Port Charges 一致
        "KRCB": "KRCL",       # KR CELEBES: 历史无账单，保留 Actual 超集
        "LHMN": "LAHM",       # LOA HARMONY: 数据完全相同
    },
    "port": {"EGSUE": "EGSUZ"},
    "vesselinfo": {},
}

# 明确垃圾 token（冲突标记/纯数字/表头残留/已 revert 的垃圾码），绝不视为实体
GARBAGE = {"CODE", "NEW", "VESSEL_CODE", "ASR", "======", "<<<<<<<", ">>>>>>>",
           "HEAD", "MAIN", "CONFLICT", "MERGE"}


def is_garbage(tok):
    t = (tok or "").replace("\ufeff", "").strip().upper()
    if not t:
        return True
    if t in GARBAGE:
        return True
    if re.fullmatch(r"[=><]+.*", t):   # 冲突标记 ======= / >>>>>>>
        return True
    if re.fullmatch(r"\d+", t):         # 纯数字行
        return True
    if t.startswith(">>>>") or t.startswith("<<<<") or t.startswith("===="):
        return True
    return False


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def git_show(ref, path):
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def parse_entities(text, col):
    """从 csv 文本提取实体集合（去重、过滤垃圾 token）。Best Model 用船名。"""
    if not text:
        return set()
    rows = list(csv.reader(io.StringIO(text)))
    out = set()
    for row in rows[1:]:
        if not row or len(row) <= col:
            continue
        key = row[col].replace("\ufeff", "").strip()
        if not is_garbage(key):
            out.add(key)
    return out


def norm(k):
    return k.replace("\ufeff", "").strip().upper()


def tracked_files():
    out = git("ls-files")
    if not out:
        return []
    return [l for l in out.strip().splitlines() if l]


def repo_references(token, tracked):
    """在【git 跟踪的部署文件】中检索 token 是否被引用（排除 3 个数据文件本身）。"""
    tok_u = token.upper()
    data_files = {"shipping_data/vessels.csv", "shipping_data/ports.csv",
                  "shipping_data/cul_vessel_bestmodel.csv"}
    hits = []
    for rel in tracked:
        if rel in data_files:
            continue
        fp = os.path.join(REPO, rel)
        if not os.path.isfile(fp):
            continue
        try:
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if tok_u in line.upper():
                        hits.append(f"{rel}:{i}")
                        break
        except Exception:
            pass
        if len(hits) >= 5:
            break
    return hits


def audit_file(cfg, tracked, strict=False):
    path = cfg["path"]
    col = cfg["col"]
    kind = cfg["kind"]
    print(f"\n{'='*64}\n  审计：{cfg['label']}  ({path})\n{'='*64}")

    try:
        with open(os.path.join(REPO, path), encoding="utf-8-sig", newline="") as f:
            cur_text = f.read()
    except FileNotFoundError:
        print("  [错误] 文件不存在于工作区")
        return [], []
    cur = {norm(k) for k in parse_entities(cur_text, col)}

    dep_text = git_show("origin/main", path)
    dep = {norm(k) for k in parse_entities(dep_text, col)} if dep_text else set()

    log = git("log", "--all", "--format=%H", "--", path)
    hist = set()
    if log:
        for h in log.strip().splitlines():
            t = git_show(h, path)
            for k in parse_entities(t, col):
                hist.add(norm(k))

    removed_from_deployed = dep - cur
    missing_from_history = hist - cur
    all_missing = sorted(removed_from_deployed | missing_from_history, key=lambda x: x)

    genuine, orphan, renamed = [], [], []

    for kn in all_missing:
        if kn in KNOWN_RENAMES.get(kind, {}):
            newcode = KNOWN_RENAMES[kind][kn]
            if any(norm(c) == newcode for c in cur):
                renamed.append((kn, newcode))
                continue
        refs = repo_references(kn, tracked)
        if refs:
            genuine.append((kn, refs))
        else:
            orphan.append(kn)

    print(f"  当前实体数：{len(cur)}  | 线上：{len(dep)}  | 历史上曾存在：{len(hist)}")
    print(f"  相对线上被移除：{len(removed_from_deployed)}  | 历史中消失：{len(missing_from_history)}")

    if renamed:
        print(f"\n  [自动排除] 改名（非丢失）：")
        for old, new in renamed:
            print(f"    {old} -> {new}")

    if orphan:
        print(f"\n  [提示] 孤儿（部署文件未引用，网页用不到）：{len(orphan)} 项")
        for kn in orphan:
            print(f"    - {kn}")

    if genuine:
        print(f"\n  [!!! 真丢失] 被部署文件引用、必须恢复：{len(genuine)} 项")
        for kn, refs in genuine:
            print(f"    - {kn}  (引用: {refs[0]}{' …' if len(refs) > 1 else ''})")
    else:
        print(f"\n  [OK] 无真丢失。")

    fail = bool(genuine) or (strict and bool(orphan))
    return genuine, orphan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["vessels", "ports", "bestmodel"], default=None)
    ap.add_argument("--strict", action="store_true", help="孤儿也算 FAIL")
    args = ap.parse_args()

    git("fetch", "origin", "main")
    tracked = tracked_files()

    chosen = FILES
    if args.only == "vessels":
        chosen = [f for f in FILES if f["kind"] == "vessel"]
    elif args.only == "ports":
        chosen = [f for f in FILES if f["kind"] == "port"]
    elif args.only == "bestmodel":
        chosen = [f for f in FILES if f["kind"] == "vesselinfo"]

    any_genuine = False
    total_orphan = 0
    for cfg in chosen:
        genuine, orphan = audit_file(cfg, tracked, strict=args.strict)
        if genuine:
            any_genuine = True
        total_orphan += len(orphan)

    print(f"\n{'='*64}")
    if any_genuine:
        print("  审计结果：FAIL —— 检测到真丢失，请先恢复再推送！")
        print(f"{'='*64}")
        sys.exit(1)
    else:
        extra = f"（含 {total_orphan} 个孤儿提示）" if total_orphan else ""
        print(f"  审计结果：PASS —— 无真丢失，可放心推送。{extra}")
        print(f"{'='*64}")
        sys.exit(0)


if __name__ == "__main__":
    main()
