#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽取看板所需原始数据：元数据 + 天级阅读指标 + 榜单监测。

参数化（保持出品书默认行为不变）：
  --ids    BookID 列表文件（默认 ids.txt）
  --out    原始 JSON 输出（默认 out/dashboard_raw.json）
  --tag    日志标签，便于区分来源（如 轻故事）
"""
import sys, json, os, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
# 取数客户端：优先用 <取数技能> 技能本体；技能未安装时回落到包内自带副本 deps/
# （交接包内置 deps/data_client.py，换机器/换人无需先装技能即可取数）
_client_path = None
for _p in ('<技能目录>/<取数技能>/scripts',
           os.path.join(HERE, 'deps')):
    if os.path.isfile(os.path.join(_p, 'data_client.py')):
        sys.path.insert(0, _p)
        _client_path = _p
        break
if _client_path is None:
    sys.exit("找不到 data_client.py：请安装 <取数技能> 技能，或把 deps/ 目录放在脚本旁。")
print(f"[取数客户端] {_client_path}")
from data_client import DataClient

OUT = os.path.join(HERE, 'out')

parser = argparse.ArgumentParser()
parser.add_argument('--ids', default=os.path.join(HERE, 'ids.txt'))
parser.add_argument('--out', default=os.path.join(OUT, 'dashboard_raw.json'))
parser.add_argument('--tag', default='')
args = parser.parse_args()

IDS = [x.strip() for x in open(args.ids, encoding='utf-8') if x.strip()]
print(f"[{args.tag}] bid 数量: {len(IDS)}")

in_list = "', '".join(IDS)
c = DataClient()

# ---- 1. 元数据 ----
meta_sql = f"""
SELECT id,
    argMax(title, create_time) AS title,
    argMax(author, create_time) AS author,
    argMax(publish_time, create_time) AS publish_time,
    argMax(self_produce_on_time, create_time) AS self_ontime,
    argMax(newest_on_time, create_time) AS newest_ontime,
    argMax(cpid, create_time) AS cpid,
    argMax(soldout, create_time) AS soldout,
    splitByChar(':', argMax(category, create_time))[1] AS cat1,
    splitByChar(':', argMax(category, create_time))[2] AS cat2,
    -- category 原始结构为「一级:二级:三级;一级:二级:三级;...」(多路径用 ';' 分隔)，
    -- 上面 cat1/cat2 只取了第一条路径的前两级，会丢掉真三级和其余路径，故保留原始值。
    argMax(category, create_time) AS category_raw,
    -- 阅读总量：书籍累计阅读人数（全生命周期口径，用户 2026-10-16 指定 total_reading）
    argMax(total_reading, create_time) AS total_reading,
    argMax(ispub, create_time) AS ispub
FROM demo.book_meta
WHERE id IN ('{in_list}')
GROUP BY id
"""
print(f"[{args.tag}] == 拉取元数据 ==")
r = c.redash(meta_sql)
print(f"[{args.tag}] meta rows:", r['row_count'], "error:", r['error'])
meta = {row['id']: row for row in r['rows']}

# ---- 2. 天级阅读指标（近 21 天）----
daily_sql = f"""
SELECT date, bid, user, valid_user, readtime, retain1, retain7
FROM demo.book_daily
WHERE date >= today() - 21
  AND bid IN ('{in_list}')
ORDER BY bid, date
"""
print(f"[{args.tag}] == 拉取天级指标 ==")
r = c.redash(daily_sql)
print(f"[{args.tag}] daily rows:", r['row_count'], "error:", r['error'])
daily = r['rows']

# ---- 3. 榜单监测（近 21 天，仅监测飙升榜）----
# 实测发现 [榜单明细表] 的 新书榜/小说榜 场景与某阅读平台首页真实在榜不一致（已失真），
# 故只保留 飙升榜 场景。
#
# 【关键坑 · 2026-09-07 修复】固定 UV 门槛（原 uv>=50）拦不住「陈旧位次残留」：
# 书掉出榜单后，表里仍会残留极少量长尾曝光记录，它们携带的 index_of_page 是掉榜前的旧位次，
# argMax(index_of_page, stime) 取「最后一次」就会把旧位次当成当前位次，造成「显示上榜、实际没上」。
# 实例：3300226230《友谊降级》08-26 真上榜 rank2/uv2169，之后曝光一路衰减
# （08-30 uv182 → 09-01 uv79 → 09-06 uv54 → 09-07 uv20），但 latest_rank 始终卡在 2。
# 判据：真实在榜时「位次越靠前、曝光越高」。09-06 全站飙升榜前 30 的 uv 在 496~2174，
# 而残留噪声的 uv 只有个位数到两百。故改为按位次分档设 UV 水位门槛：
#   rank≤5 → uv≥300 | rank 6~15 → uv≥200 | rank 16~30 → uv≥120 | rank>30 → uv≥60
# 该分档经历史数据回测：08-26/27 真上榜保留，09-01 起各日残留全部剔除。
top_sql = f"""
SELECT date, itemid, scene_cn, argMax(index_of_page, stime) AS latest_rank, uniq(vid) AS uv
FROM (
    SELECT toDate(stime) AS date,
        stime,
        itemid,
        multiIf(
            scene='rising','飙升榜',
            scene='newbook','新书榜',
            scene='general_novel_rising','小说榜',
            scene) AS scene_cn,
        index_of_page,
        vid
    FROM demo.toplist_event
    WHERE toDate(stime) >= today() - 21
      AND itemtype = 'book'
      AND scene = 'rising'
      AND itemid IN ('{in_list}')
)
GROUP BY date, itemid, scene_cn
HAVING uv >= multiIf(
    latest_rank <= 5, 300,
    latest_rank <= 15, 200,
    latest_rank <= 30, 120,
    60
)
ORDER BY date DESC, itemid
"""
print(f"[{args.tag}] == 拉取榜单监测 ==")
r = c.redash(top_sql)
print(f"[{args.tag}] toplist rows:", r['row_count'], "error:", r['error'])
toplist = r['rows']

# ---- 4. 新书检查长表（自出品/S级：新进UV、推荐值、榜单排名等）----
check_sql = f"""
SELECT date, bookid,
    sumIf(value, action='read_xinjin_uv')   AS xinjin_uv,
    sumIf(value, action='new_rate')         AS new_rate,
    sumIf(value, action='read_uv')          AS read_uv,
    sumIf(value, action='valid_read_uv')    AS valid_read_uv,
    sumIf(value, action='read_avg_readtime') AS avg_readtime_min,
    sumIf(value, action='read_retain_r1')   AS retain_r1,
    sumIf(value, action='rising_rank')      AS rising_rank,
    sumIf(value, action='newbook_rank')     AS newbook_rank,
    sumIf(value, action='general_novel_rising_rank') AS novel_rank
FROM demo.check_stat
WHERE date >= today() - 21
  AND type='base'
  AND bookid IN ('{in_list}')
GROUP BY date, bookid
ORDER BY bookid, date
"""
print(f"[{args.tag}] == 拉取新书检查长表 ==")
r = c.redash(check_sql)
print(f"[{args.tag}] checkstat rows:", r['row_count'], "error:", r['error'])
checkstat = r['rows']

result = {
    'meta': meta,
    'daily': daily,
    'toplist': toplist,
    'checkstat': checkstat,
    'bid_count': len(IDS),
}
with open(args.out, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, default=str)
print(f"[{args.tag}] 已写出 {args.out}")
# 简要统计
dates = sorted({str(d['date']) for d in daily})
print(f"[{args.tag}] daily 覆盖日期:", dates[:3], "...", dates[-3:], "共", len(dates), "天")
print(f"[{args.tag}] 有元数据的 bid:", len(meta), "/", len(IDS))
