#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉取书籍「完整分类路径」映射 → out/category_full.json

背景：demo.book_meta.category 原始结构是
  「一级:二级:三级;一级:二级:三级;...」
即多本书分类路径用 ';' 分隔、每路径内三级用 ':' 分隔。
而 build_data.py 只取了 splitByChar(':', category)[1] / [2]，
丢掉了真三级和第一条以后的所有路径。本脚本把完整分类补全。

输出：out/category_full.json = { bid: "一级/二级/三级;一级/二级/三级" }
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
# 取数客户端：优先技能本体，回落到包内 deps/（同 build_data.py）
_client_path = None
for _p in ('<技能目录>/<取数技能>/scripts',
           os.path.join(HERE, 'deps')):
    if os.path.isfile(os.path.join(_p, 'data_client.py')):
        sys.path.insert(0, _p)
        _client_path = _p
        break
if _client_path is None:
    sys.exit("找不到 data_client.py：请安装 <取数技能> 技能，或把 deps/ 目录放在脚本旁。")
from data_client import DataClient


def parse_full(category_raw):
    """'个人成长:人生哲学:人生哲学;文学:纪实文学:纪实文学'
       -> '个人成长/人生哲学/人生哲学;文学/纪实文学/纪实文学'"""
    if not category_raw:
        return ''
    paths = []
    for seg in str(category_raw).split(';'):
        seg = seg.strip()
        if not seg:
            continue
        levels = [x.strip() for x in seg.split(':') if x.strip()]
        if levels:
            paths.append('/'.join(levels))
    return ';'.join(paths)


def main():
    ids = set()
    for fn in ('ids.txt', 'ids_qinggushi.txt'):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    v = line.strip()
                    if v:
                        ids.add(v)
    ids = sorted(ids)
    print(f"待查 bid 数: {len(ids)}")
    if not ids:
        print("没有 bid，退出。")
        return

    c = DataClient()
    result = {}
    BATCH = 500
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        in_list = "','".join(batch)
        sql = f"""
SELECT id, argMax(category, create_time) AS category_raw
FROM demo.book_meta
WHERE id IN ('{in_list}')
GROUP BY id
"""
        r = c.redash(sql)
        if r.get('error'):
            print(f"  批次 {i//BATCH+1} 查询出错: {r['error']}")
            continue
        for row in r['rows']:
            full = parse_full(row.get('category_raw'))
            if full:
                result[str(row['id'])] = full
        print(f"  批次 {i//BATCH+1}: 已取 {len(r['rows'])} 本，累计 {len(result)} 本")

    path = os.path.join(OUT, 'category_full.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=0)
    print(f"已写出 {path}，共 {len(result)} 本")


if __name__ == '__main__':
    main()
