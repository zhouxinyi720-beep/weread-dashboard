#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从<企业协作平台>在线表格子表增量同步 BookID 列表到本地 ids 文件。

通用、可复用：参数化 docid / sheet_id / 出品人列 / BookID 列，供
「出品书」「轻故事」等多个数据源各自调用，实现「BookID 有更新自动加入检索」。

列定位策略：优先按表头名称（去空格、忽略大小写、子串匹配），
找不到时回退到列字母（A/B/C.../O）。

前置：<表格读取工具> 已安装(>=1.1.0)且已授权(authorized)。
"""
import os, sys, csv, json, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))


def col_letter_to_idx(letter):
    """'A'->0, 'O'->14"""
    n = 0
    for ch in letter.upper():
        n = n * 26 + (ord(ch) - ord('A') + 1)
    return n - 1


def resolve_col_idx(header, name=None, letter=None):
    """按名称(子串,去空格)或字母定位列索引；均失败时抛错。"""
    if name:
        key = name.replace(" ", "")
        for i, h in enumerate(header):
            if key and key in h.replace(" ", ""):
                return i
    if letter:
        return col_letter_to_idx(letter)
    raise ValueError(f"无法定位列：name={name!r} letter={letter!r}；表头={header[:12]}")


def wecom_read_csv(docid, sheet_id):
    """调用 <表格读取工具> 读取子表 CSV，返回 (rows, header)。"""
    cmd = ["<表格读取工具>", "sheet", "ranges", "get", "--json",
           json.dumps({"docid": docid, "sheet_id": sheet_id, "mode": "csv"})]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"<表格读取工具> 失败({out.returncode}): {out.stderr[:300]}")
    meta = json.loads(out.stdout)
    fp = meta.get("file_path")
    if not fp:
        raise RuntimeError(f"<表格读取工具> 未返回 file_path: {out.stdout[:300]}")
    with open(fp, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    header = [c.replace("\n", " ").strip() for c in rows[0]]
    return rows[1:], header


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docid", required=True, help="文档 docid")
    ap.add_argument("--sheet-id", required=True, help="子表 sheet_id")
    ap.add_argument("--producer-col", required=True, help="出品人列名(子串)或字母, 如 出品人 / C")
    ap.add_argument("--producer-val", required=True, help="出品人筛选值, 如 Annezhou")
    ap.add_argument("--bookid-col", required=True, help="BookID 列名(子串)或字母, 如 BookID / O")
    ap.add_argument("--ids-file", required=True, help="本地 BookID 列表文件(每行一个)")
    ap.add_argument("--skip-file", default=os.path.join(HERE, "skip_bids.txt"),
                    help="隐藏/跳过 bid 文件(每行一个), 默认 skip_bids.txt")
    ap.add_argument("--tag", default="", help="日志标签")
    args = ap.parse_args()

    rows, header = wecom_read_csv(args.docid, args.sheet_id)

    # 解析列索引
    prod_letter = args.producer_col if len(args.producer_col) <= 2 and args.producer_col.isalpha() else None
    bid_letter = args.bookid_col if len(args.bookid_col) <= 2 and args.bookid_col.isalpha() else None
    prod_i = resolve_col_idx(header, name=args.producer_col if not prod_letter else None, letter=prod_letter)
    bid_i = resolve_col_idx(header, name=args.bookid_col if not bid_letter else None, letter=bid_letter)
    print(f"[{args.tag}] 出品人列={header[prod_i]!r}(idx {prod_i})  BookID列={header[bid_i]!r}(idx {bid_i})  总行数={len(rows)}")

    # 筛选 + 去重
    seen = set()
    bids = []
    for r in rows:
        if len(r) > prod_i and r[prod_i].strip() == args.producer_val:
            if len(r) > bid_i:
                b = r[bid_i].strip()
                if b and b not in seen:
                    seen.add(b)
                    bids.append(b)
    print(f"[{args.tag}] 出品人={args.producer_val} 去重后 BookID 数: {len(bids)}")

    # 读取已有 + 跳过集
    ids_path = os.path.abspath(args.ids_file)
    existing = set()
    if os.path.exists(ids_path):
        with open(ids_path, encoding="utf-8") as f:
            existing = {x.strip() for x in f if x.strip()}
    skip = set()
    if os.path.exists(args.skip_file):
        with open(args.skip_file, encoding="utf-8") as f:
            skip = {x.strip() for x in f if x.strip()}

    new = [b for b in bids if b not in existing]
    hidden = [b for b in new if b in skip]
    real_new = [b for b in new if b not in skip]
    print(f"[{args.tag}] 已有 {len(existing)} 个；本次新增 {len(new)} 个（其中隐藏跳过 {len(hidden)}，真实新增 {len(real_new)}）")
    for b in hidden:
        print(f"[{args.tag}]   跳过隐藏 bid: {b}")
    for b in real_new:
        print(f"[{args.tag}]   新增 bid: {b}")

    if real_new:
        with open(ids_path, "a", encoding="utf-8") as f:
            for b in real_new:
                f.write(b + "\n")
        print(f"[{args.tag}] 已追加 {len(real_new)} 个到 {ids_path}")
    else:
        print(f"[{args.tag}] 无真实新增，ids 文件保持不变。")
    print(f"[{args.tag}] 完成。当前 ids 文件共 {len(existing) + len(real_new)} 个 BookID。")


if __name__ == "__main__":
    main()
