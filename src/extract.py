#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并四份原始数据 -> dashboard_data.json（看板用干净结构）。

参数化（保持出品书默认行为不变）：
  --raw      原始 JSON（默认 out/dashboard_raw.json）
  --summary  评级汇总 JSON（默认 out/mass_summary.json；缺失则评级留空）
  --out      输出 JSON（默认 out/dashboard_data.json）
  --tag      日志标签
"""
import json, os, argparse
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')

parser = argparse.ArgumentParser()
parser.add_argument('--raw', default=os.path.join(OUT, 'dashboard_raw.json'))
parser.add_argument('--summary', default=os.path.join(OUT, 'mass_summary.json'))
parser.add_argument('--out', default=os.path.join(OUT, 'dashboard_data.json'))
parser.add_argument('--tag', default='')
args = parser.parse_args()

raw = json.load(open(args.raw, encoding='utf-8'))

rating_by = {}
if args.summary and os.path.exists(args.summary):
    try:
        summary = json.load(open(args.summary, encoding='utf-8'))
        rating_by = {s['book_id']: s for s in summary}
        print(f"[{args.tag}] 载入评级 {len(rating_by)} 条")
    except Exception as e:
        print(f"[{args.tag}] 评级文件读取失败，评级留空: {e}")
else:
    print(f"[{args.tag}] 未提供评级文件，评级留空")

meta = raw['meta']
daily = raw['daily']
toplist = raw['toplist']
checkstat = raw['checkstat']

# daily 按 bid 归组，并排序
daily_by = {}
for r in daily:
    b = str(r['bid'])
    daily_by.setdefault(b, []).append(r)
for b in daily_by:
    daily_by[b].sort(key=lambda x: str(x['date']))

# checkstat 按 bookid 归组
check_by = {}
for r in checkstat:
    b = str(r['bookid'])
    check_by.setdefault(b, []).append(r)
for b in check_by:
    check_by[b].sort(key=lambda x: str(x['date']))

# toplist 按 itemid 归组
top_by = {}
for r in toplist:
    b = str(r['itemid'])
    top_by.setdefault(b, []).append(r)

# 全局最新日期
all_dates = sorted({str(r['date']) for r in daily})
data_date = all_dates[-1] if all_dates else None
print(f"[{args.tag}] 最新数据日期:", data_date, " 天数:", len(all_dates))

CPID_SELF = {'1000000190', '1000000121', '1000000996', '1000000998', '1000000997'}
def cpid_label(c):
    c = str(c)
    if c in ('1000000190',):
        return '自出品'
    if c in ('1000000121',):
        return '轻故事'
    if c in CPID_SELF:
        return '自出品系'
    return '非出品'

books = []
for bid, m in meta.items():
    bid = str(bid)
    rows = daily_by.get(bid, [])
    # 元数据
    cpid = str(m.get('cpid'))
    # 上架时间
    self_on = str(m.get('self_ontime') or '')
    new_on = str(m.get('newest_ontime') or '')
    ondate = self_on if cpid in CPID_SELF and self_on not in ('', 'None') else (new_on if new_on not in ('', 'None') else '')
    cat1 = m.get('cat1') or ''
    cat2 = m.get('cat2') or ''
    # 最新快照
    cur = rows[-1] if rows else None
    # 昨日快照（对比基准从「7天前」改为「较昨日」）
    ref = None
    if rows:
        target = all_dates[max(0, len(all_dates)-2)]  # 倒数第2个 = 昨日
        for r in rows:
            if str(r['date']) == target:
                ref = r
                break
        if ref is None:
            ref = rows[0]
    def snap(r):
        if not r:
            return None
        user = r.get('user') or 0
        vu = r.get('valid_user') or 0
        rt = r.get('readtime') or 0
        r1 = r.get('retain1') or 0
        r7 = r.get('retain7') or 0
        eff = round(vu / user * 100, 1) if user else 0.0
        return {
            'reading_uv': int(user),
            'eff_uv': int(vu),
            'eff_rate': eff,
            'avg_dur_min': round((rt or 0) / 60.0, 1),
            'retain1': round((r1 or 0) * 100, 1),
            'retain7': round((r7 or 0) * 100, 1),
        }
    cur_snap = snap(cur)
    ref_snap = snap(ref)
    # 新进UV / 推荐值 from checkstat
    xinjin_uv = None
    rec_rate = None
    cr = check_by.get(bid, [])
    if cr:
        ccur = cr[-1]
        xv = ccur.get('xinjin_uv')
        nr = ccur.get('new_rate')
        if xv is not None:
            try: xinjin_uv = int(float(xv))
            except: pass
        if nr is not None:
            try: rec_rate = round(float(nr), 1)
            except: pass
    # 涨幅（有效在读UV）
    growth = None
    if cur_snap and ref_snap and ref_snap['eff_uv']:
        growth = round((cur_snap['eff_uv'] - ref_snap['eff_uv']) / ref_snap['eff_uv'] * 100, 1)
    # 趋势序列
    trend_dates = [str(r['date']) for r in rows]
    trend_eff_uv = [int(r.get('valid_user') or 0) for r in rows]
    trend_reading_uv = [int(r.get('user') or 0) for r in rows]
    # 评级
    rt = rating_by.get(bid, {})
    rating = {
        'fusion': rt.get('fusion'),
        'grade': rt.get('fusion_grade'),
        'hist': rt.get('hist'),
        'cat': rt.get('cat'),
        'peer': rt.get('peer'),
    }
    # 榜单命中
    tops = top_by.get(bid, [])
    tops_sorted = sorted(tops, key=lambda x: str(x['date']), reverse=True)
    toplist_out = [{'date': str(t['date']), 'scene': t['scene_cn'],
                    'rank': t.get('latest_rank') or t.get('best_rank'), 'uv': t.get('uv')} for t in tops_sorted]
    books.append({
        'bid': bid,
        'title': m.get('title') or '',
        'author': m.get('author') or '',
        'cat1': cat1,
        'cat2': cat2,
        'ondate': ondate,
        'cpid': cpid,
        'cpid_label': cpid_label(cpid),
        'ispub': m.get('ispub'),
        'soldout': m.get('soldout'),
        'total_reading': int(m.get('total_reading') or 0),
        'snap': cur_snap,
        'ref_snap': ref_snap,
        'xinjin_uv': xinjin_uv,
        'rec_rate': rec_rate,
        'growth_eff_uv': growth,
        'trend': {'dates': trend_dates, 'eff_uv': trend_eff_uv, 'reading_uv': trend_reading_uv},
        'rating': rating,
        'toplist': toplist_out,
    })

# 排序：按有效在读UV降序
books.sort(key=lambda x: (x['snap']['eff_uv'] if x['snap'] else -1), reverse=True)

grade_dist = {}
for b in books:
    g = b['rating']['grade']
    grade_dist[g] = grade_dist.get(g, 0) + 1

result = {
    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    'data_date': data_date,
    'date_window': [all_dates[0], all_dates[-1]] if all_dates else [],
    'bid_count': len(books),
    'grade_dist': grade_dist,
    'books': books,
    'toplist': toplist,
}
with open(args.out, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, default=str)
print(f"[{args.tag}] 写出 {args.out}, 书籍数:", len(books))
print(f"[{args.tag}] 档位分布:", grade_dist)
# 抽样校验
if books:
    b0 = books[0]
    print(f"[{args.tag}] 样例:", b0['title'], "| 快照:", b0['snap'], "| 评级:", b0['rating'], "| 涨幅:", b0['growth_eff_uv'])
