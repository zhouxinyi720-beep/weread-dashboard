#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建看板：完全沿用用户原始 HTML 的视觉/渲染代码，只替换数据源，
并施加四处改动：①浅色主题唯一 ②删除评级(原始本就没有) ③新增"新书核心指标 Top 榜"(≤14天)
④把"建议加推"移到新书 Top 榜下方、仅针对新书、按新门槛筛选。"""
import json, datetime, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
SRC = os.environ.get("WXKB_SRC") or "<本机模板路径>/数据看板_模板.html"
# 兜底：换机器 / 分享包内运行时上面的绝对路径不存在，则依次尝试包内 templates 目录。
# 原路径存在时行为完全不变。
if not os.path.exists(SRC):
    for _alt in (
        os.path.join(HERE, "templates", "数据看板_2026.07.31.html"),
        os.path.join(HERE, "原始模板", "数据看板_2026.07.31.html"),
    ):
        if os.path.exists(_alt):
            SRC = _alt
            print(f"[模板兜底] 原始模板不在原路径，改用：{_alt}")
            break
# 固定输出文件名：每日覆盖更新同一份看板，不每天新增文件
DST = os.path.join(OUT, "数据看板_新版.html")

DATA_DATE = "2026-08-23"   # 快照日 = daily 表最新日期（下面从数据自动覆盖，不再写死）
NEW_DAYS = 14

def to_date(ts):
    try:
        ts = int(ts)
        if ts > 1e12: ts = ts / 1000
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return ""

d = json.load(open(os.path.join(OUT, "dashboard_data.json"), encoding="utf-8"))
raw = json.load(open(os.path.join(OUT, "dashboard_raw.json"), encoding="utf-8"))

# ---- 轻故事合并（数据源：出品ID121 轻故事 sheet，出品人=Annezhou）----
# 与出品书完全平行：dashboard_data_qinggushi.json / dashboard_raw_qinggushi.json
# 由 build_data.py(--ids ids_qinggushi.txt) + extract.py 生成。缺失时优雅降级（仅出品书）。
LIGHT_RAW = os.path.join(OUT, "dashboard_raw_qinggushi.json")
LIGHT_DATA = os.path.join(OUT, "dashboard_data_qinggushi.json")
LIGHT_BIDS_LIST = []
if os.path.exists(LIGHT_DATA) and os.path.exists(LIGHT_RAW):
    d_light = json.load(open(LIGHT_DATA, encoding="utf-8"))
    raw_light = json.load(open(LIGHT_RAW, encoding="utf-8"))
    d["books"] = d["books"] + d_light["books"]
    raw["daily"] = raw["daily"] + raw_light["daily"]
    raw["checkstat"] = raw["checkstat"] + raw_light["checkstat"]
    raw["toplist"] = raw["toplist"] + raw_light["toplist"]
    LIGHT_BIDS_LIST = [str(b["bid"]) for b in d_light["books"]]
    print(f"已合并轻故事数据：{len(d_light['books'])} 本，LIGHT_BIDS={len(LIGHT_BIDS_LIST)}")
else:
    print("未找到轻故事数据文件（dashboard_data_qinggushi.json / dashboard_raw_qinggushi.json），仅出品书。")

# ---- 完整分类路径映射（category 原始结构：「一级:二级:三级;一级:二级:三级;...」）----
# 背景：build_data.py 的 cat1/cat2 只取第一条路径的前两级，且把二级重复成三级，
# 会丢掉真三级和其余分类路径。看板的「分类」与「表格行」需要完整三级全路径。
# 来源1：out/category_full.json（fetch_category_full.py 全量拉取，覆盖出品书+轻故事）
# 来源2：dashboard_raw*.json 的 meta.category_raw（build_data.py 每日刷新，优先级更高）
def _parse_cat_full(raw_cat):
    if not raw_cat:
        return ''
    paths = []
    for seg in str(raw_cat).split(';'):
        seg = seg.strip()
        if not seg:
            continue
        levels = [x.strip() for x in seg.split(':') if x.strip()]
        if levels:
            paths.append('/'.join(levels))
    return ';'.join(paths)


CAT_FULL = {}
_cat_file = os.path.join(OUT, "category_full.json")
if os.path.exists(_cat_file):
    try:
        CAT_FULL = json.load(open(_cat_file, encoding="utf-8")) or {}
    except Exception:
        CAT_FULL = {}
_meta_sources = []
if isinstance(raw, dict) and isinstance(raw.get("meta"), dict):
    _meta_sources.append(raw["meta"])
try:
    if isinstance(raw_light, dict) and isinstance(raw_light.get("meta"), dict):
        _meta_sources.append(raw_light["meta"])
except NameError:
    pass
for _ms in _meta_sources:
    for _bid, _mv in _ms.items():
        _cf = _parse_cat_full((_mv or {}).get("category_raw"))
        if _cf:
            CAT_FULL[str(_bid)] = _cf
print(f"完整分类映射：{len(CAT_FULL)} 本（三级全路径，多路径以 ; 分隔）")

books = d["books"]

# 快照日跟随数据最新日期（daily 表的最大 date），不再写死 08.23，使"时间窗/快照"标签随数据自更新
try:
    _maxdate = max(str(r.get("date", "")) for r in raw.get("daily", []))
    if _maxdate:
        DATA_DATE = _maxdate
except Exception:
    pass

# ---------- 1. 组装 ALL_DATA ----------
all_data = []
for b in books:
    snap = b.get("snap") or {}
    ref = b.get("ref_snap") or {}
    cat1 = b.get("cat1") or "未分类"
    cat2 = b.get("cat2") or ""
    launch = to_date(b.get("ondate"))
    try:
        do = (datetime.datetime.strptime(DATA_DATE, "%Y-%m-%d") - datetime.datetime.strptime(launch, "%Y-%m-%d")).days if launch else 9999
    except Exception:
        do = 9999
    m = {
        "reading_uv": snap.get("reading_uv", 0) or 0,
        "effective_reading_uv": snap.get("eff_uv", 0) or 0,
        "new_reading_uv": b.get("xinjin_uv", 0) or 0,
        "paid_reading_uv": 0,
        "review_count": 0,
        "daily_avg_new": 0,
        "effective_reading_rate": snap.get("eff_rate", 0) or 0,
        "next_day_retention": snap.get("retain1", 0) or 0,
        "day7_retention": snap.get("retain7", 0) or 0,
        "recommendation_rate": b.get("rec_rate", 0) or 0,
        "paid_rate": 0,
        "avg_reading_duration": snap.get("avg_dur_min", 0) or 0,
        # 阅读总量：书籍累计阅读人数（total_reading 口径，随 meta 每日刷新）
        "total_reading": b.get("total_reading", 0) or 0,
        "historical_readers": 0,
        "historical_subscriptions": 0,
    }
    all_data.append({
        "book_id": b["bid"],
        "title": b.get("title", ""),
        "author": b.get("author", ""),
        "launch_date": launch,
        "payment_type": "未知",
        "category_l1": cat1,
        "category_l2": cat2,
        "category_l3": cat2,
        "categories": f"{cat1}:{cat2}" if cat2 else cat1,
        # 完整分类：三级全路径、多条路径以 ; 分隔（如 个人成长/人生哲学/人生哲学;文学/纪实文学/纪实文学）
        "category_full": CAT_FULL.get(str(b["bid"]), "") or (f"{cat1}/{cat2}" if cat2 else cat1),
        "days_online": do,
        "metrics": m,
    })

# ---------- 2. 组装 TIMELINE ----------
rec_rate_map = {b["bid"]: (b.get("rec_rate", 0) or 0) for b in books}
# daily: bid,date,user,valid_user,readtime,retain1,retain7
daily_idx = {}
for r in raw["daily"]:
    daily_idx[(str(r["bid"]), str(r["date"]))] = r
check_idx = {}
for r in raw["checkstat"]:
    check_idx[(str(r["bookid"]), str(r["date"]))] = r

timeline = {}
dates_set = set()
# 轻故事书量大（1600+ 本）：趋势窗口收窄到近 14 天、并剔除恒为 0 的字段，
# 以把单文件 HTML 压到 tPPT 10MB 上限以内；出品书保留完整 21 天全字段。
all_dates_sorted = sorted({d for (_, d) in daily_idx})
RECENT_DATES = set(all_dates_sorted[-14:])
LIGHT_SET = set(LIGHT_BIDS_LIST)
for (bid, date), r in daily_idx.items():
    dates_set.add(date)
    if bid in LIGHT_SET and date not in RECENT_DATES:
        continue
    c = check_idx.get((bid, date), {})
    user = r.get("user", 0) or 0
    vuser = r.get("valid_user", 0) or 0
    eff_rate = round(vuser / user * 100, 1) if user else 0.0
    entry = {
        "reading_uv": user,
        "effective_reading_uv": vuser,
        "effective_reading_rate": eff_rate,
        "avg_reading_duration": round(float(r.get("readtime", 0) or 0), 2),
        "next_day_retention": round(float(r.get("retain1", 0) or 0) * 100, 1),
        "day7_retention": round(float(r.get("retain7", 0) or 0) * 100, 1),
        "new_reading_uv": c.get("xinjin_uv", 0) or 0,
        "historical_readers": 0,
        "recommendation_rate": round(float(rec_rate_map.get(bid, 0) or 0), 1),
        "daily_avg_new": 0,
        "paid_reading_uv": 0,
        "paid_rate": 0,
        "review_count": 0,
        "historical_subscriptions": 0,
    }
    if bid in LIGHT_SET:
        for _k in ("historical_readers", "daily_avg_new", "paid_reading_uv", "paid_rate", "review_count", "historical_subscriptions"):
            entry.pop(_k, None)
    timeline.setdefault(bid, {})[date] = entry
DATES = sorted(dates_set)

# ---------- 3. 组装 CHANGES (snap vs ref_snap) ----------
METRIC_KEYS = ["reading_uv", "effective_reading_uv", "new_reading_uv", "paid_reading_uv",
               "review_count", "daily_avg_new", "effective_reading_rate", "next_day_retention",
               "day7_retention", "recommendation_rate", "paid_rate", "avg_reading_duration",
               "historical_readers", "historical_subscriptions"]
snap_map = {b["bid"]: (b.get("snap") or {}) for b in books}
ref_map = {b["bid"]: (b.get("ref_snap") or {}) for b in books}
changes = {}
for b in books:
    bid = b["bid"]
    s, r = snap_map.get(bid, {}), ref_map.get(bid, {})
    ch = {}
    for k in METRIC_KEYS:
        cur = s.get(k if k != "effective_reading_uv" else "eff_uv", 0) or 0
        # snap 字段命名：eff_uv / eff_rate / avg_dur_min / retain1 / retain7
        if k == "effective_reading_uv": cur = s.get("eff_uv", 0) or 0
        elif k == "effective_reading_rate": cur = s.get("eff_rate", 0) or 0
        elif k == "avg_reading_duration": cur = s.get("avg_dur_min", 0) or 0
        elif k == "next_day_retention": cur = s.get("retain1", 0) or 0
        elif k == "day7_retention": cur = s.get("retain7", 0) or 0
        elif k == "new_reading_uv": cur = b.get("xinjin_uv", 0) or 0
        elif k == "recommendation_rate": cur = b.get("rec_rate", 0) or 0
        pre = 0
        if k == "effective_reading_uv": pre = r.get("eff_uv", 0) or 0
        elif k == "effective_reading_rate": pre = r.get("eff_rate", 0) or 0
        elif k == "avg_reading_duration": pre = r.get("avg_dur_min", 0) or 0
        elif k == "next_day_retention": pre = r.get("retain1", 0) or 0
        elif k == "day7_retention": pre = r.get("retain7", 0) or 0
        elif k == "new_reading_uv": pre = 0
        elif k == "recommendation_rate": pre = 0
        else: pre = r.get(k, 0) or 0
        if pre:
            ch[k] = round((cur - pre) / pre * 100, 1)
        else:
            ch[k] = 0.0
    changes[bid] = ch

# ---------- 4. 其余全局变量 ----------
all_bids = [b["bid"] for b in books]
all_cat1 = sorted({b.get("cat1") or "未分类" for b in books})

BENCHMARKS = {
  "个人成长": {"eff_rate": 31.5, "duration": 8.2, "retention": 26.1},
  "人物传记": {"eff_rate": 36.8, "duration": 12.5, "retention": 23.3},
  "医学健康": {"eff_rate": 28.1, "duration": 7.4, "retention": 27.2},
  "历史": {"eff_rate": 36.5, "duration": 13.9, "retention": 28.5},
  "哲学宗教": {"eff_rate": 66.7, "duration": 5.2, "retention": 28.6},
  "女生小说": {"eff_rate": 50.0, "duration": 27.5, "retention": 28.6},
  "心理": {"eff_rate": 32.1, "duration": 8.2, "retention": 23.8},
  "政治军事": {"eff_rate": 37.0, "duration": 10.0, "retention": 23.0},
  "教育学习": {"eff_rate": 33.7, "duration": 11.3, "retention": 26.1},
  "文学": {"eff_rate": 34.6, "duration": 8.6, "retention": 27.0},
  "漫画": {"eff_rate": 21.6, "duration": 4.2, "retention": 25.0},
  "生活百科": {"eff_rate": 33.3, "duration": 1.9, "retention": 0},
  "男生小说": {"eff_rate": 51.6, "duration": 49.6, "retention": 43.5},
  "社会文化": {"eff_rate": 38.5, "duration": 4.7, "retention": 21.0},
  "科学技术": {"eff_rate": 37.0, "duration": 6.5, "retention": 19.5},
  "精品小说": {"eff_rate": 43.6, "duration": 27.0, "retention": 37.3},
  "经济理财": {"eff_rate": 39.2, "duration": 6.7, "retention": 24.2},
  "计算机": {"eff_rate": 38.9, "duration": 4.2, "retention": 19.8}
}

def js_obj(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))

data_js = []
data_js.append(f"// 自动生成的看板数据文件 —— 由 build_final.py 重写（数据源：某阅读平台内部表，快照 {DATA_DATE}）")
data_js.append(f"// 书籍数: {len(all_data)}  时间窗: {DATES[0]} ~ {DATES[-1]}  共 {len(DATES)} 天")
data_js.append(f"const DATES = {js_obj(DATES)};")
data_js.append(f"const TIMELINE = {js_obj(timeline)};")
data_js.append(f"const ALL_DATA = {js_obj(all_data)};")
data_js.append(f"const CHANGES = {js_obj(changes)};")
data_js.append(f"const ALL_CATEGORIES = {js_obj(all_cat1)};")
data_js.append("const HAS_PREV = true;")
data_js.append(f"const DATA_DATE = {js_obj(DATA_DATE)};")
data_js.append(f"const MY_BIDS = new Set({js_obj(all_bids)});")
# MAIN_BIDS = 出品书（剔除轻故事，互斥）；LIGHT_BIDS = 轻故事
_main_bids = [b for b in all_bids if b not in set(LIGHT_BIDS_LIST)]
data_js.append(f"const MAIN_BIDS = new Set({js_obj(_main_bids)});")
data_js.append(f"const LIGHT_BIDS = new Set({js_obj(LIGHT_BIDS_LIST)});")
data_js.append("const HAS_MY_BOOKS = true;")
data_js.append("const WEREAD_HOME_MONITOR = null;")
data_js.append("const HOTSPOTS_RAW = [];")
data_js.append("const SUMMARIES = {};")
data_js.append(f"const BENCHMARKS = {js_obj(BENCHMARKS)};")

# ---------- 4.5 榜单监测数据（来自 [榜单明细表]，按 bid 过滤）----------
# 语义：实时监测「今日在榜」——取最新快照日(monitor_date)在榜的书×榜单组合，
# 而非 21 天历史上过榜的累计。另算 onboard_days = 该书×榜单在近窗口累计在榜天数（监测连续/累计在榜时长）。
# 数据结构仿原始 WEREAD_HOME_MONITOR.hits：按书聚合，每书带 items[]（各榜单命中条目），
# 并携带该书自身指标（effective_reading_uv / next_day_retention / recommendation_rate）供卡片展示。
_book_map = {b["book_id"]: b for b in all_data}
# 榜单监测 toplist 优先取 dashboard_raw.json（由 build_data.py 确定性生成，含 latest_rank=当日最新位次），
# 回退到 dashboard_data.json（<取数技能> 生成，字段为 best_rank=当日峰值）；两者结构一致。
_lead_raw = (raw.get("toplist") if isinstance(raw, dict) else None) or d.get("toplist") or []
_lead_dates = sorted({str(r.get("date") or "") for r in _lead_raw if str(r.get("date") or "")})
_monitor_date = _lead_dates[-1] if _lead_dates else ""
# 「真实在榜」曝光阈值：[榜单明细表] 会把瞬时进排名计算(极低曝光)的书也记下来，
# 仅监测 飙升榜（新书榜/小说榜 场景与首页真实在榜失真，已弃用），用 uv>=50 剔除噪声。
_LEAD_UV_MIN = {"飙升榜": 50}
# 累计在榜天数：每个 (bid, scene) 在窗口内出现过的不同日期数
_onboard_days = {}
for r in _lead_raw:
    _bid = str(r.get("itemid") or "")
    _scene = r.get("scene_cn") or "其他榜"
    if _bid not in _book_map:
        continue
    _onboard_days.setdefault((_bid, _scene), set()).add(str(r.get("date") or ""))
# 今日在榜（最新快照日），按 (bid, scene) 取最新快照位次(latest_rank)与 uv
# latest_rank = argMax(index_of_page, stime)，即当日最后一次被记入时的位次（最接近当前），
# 取代原先的 min(index_of_page)（当日峰值，会把"当天到过的最高位"误当当前位）。
_today = [r for r in _lead_raw if str(r.get("date") or "") == _monitor_date]
_lead_scene_map = {}  # (bid, scene) -> {rank, uv}
for r in _today:
    _bid = str(r.get("itemid") or "")
    _scene = r.get("scene_cn") or "其他榜"
    if _bid not in _book_map:
        continue
    _rank = r.get("latest_rank") or r.get("best_rank") or 0
    _uv = r.get("uv") or 0
    _key = (_bid, _scene)
    if _key not in _lead_scene_map:
        _lead_scene_map[_key] = {"rank": _rank, "uv": _uv}
    else:
        _a = _lead_scene_map[_key]
        if _rank:
            _a["rank"] = min(_a["rank"], _rank)
        _a["uv"] = max(_a["uv"], _uv)
# 按 uv 阈值过滤后，再按书聚合（仿 WEREAD_HOME_MONITOR.hits 结构）
_lead_books = {}  # bid -> {book info + items[]}
for (_bid, _scene), _s in _lead_scene_map.items():
    if _s["uv"] < _LEAD_UV_MIN.get(_scene, 0):
        continue
    _bk = _book_map[_bid]
    _met = _bk.get("metrics") or {}
    if _bid not in _lead_books:
        _lead_books[_bid] = {
            "book_id": _bid,
            "title": _bk.get("title", ""),
            "author": _bk.get("author", ""),
            "days_online": _bk.get("days_online", 9999),
            "effective_reading_uv": _met.get("effective_reading_uv", 0) or 0,
            "next_day_retention": _met.get("next_day_retention", 0) or 0,
            "recommendation_rate": _met.get("recommendation_rate", 0) or 0,
            "items": [],
        }
    _lead_books[_bid]["items"].append({
        "section_key": _scene,           # 用于排序/标签色：飙升榜=amber
        "section_label": _scene,          # 显示名，如"飙升榜"/"新书榜"
        "rank": _s["rank"],
        "uv": _s["uv"],
        "onboard_days": len(_onboard_days.get((_bid, _scene), set())),
    })
# 展平为列表（前端按书遍历）
_lead_hits = list(_lead_books.values())
# 排序：飙升榜优先 → rank 升序 → 命中榜单数降序 → uv 降序
_lead_hits.sort(key=lambda x: (
    -int(any(it["section_key"] == "飙升榜" for it in x["items"])),
    min((it["rank"] or 999) for it in x["items"]),
    -len(x["items"]),
    -(x["effective_reading_uv"] or 0),
))
data_js.append(f"const LEADERBOARD_HITS = {js_obj(_lead_hits)};")
data_js.append(f"const LEADERBOARD_MONITOR_DATE = {js_obj(_monitor_date)};")
data_js.append(f"const LEADERBOARD_UV_MIN = {js_obj(_LEAD_UV_MIN)};")
print(f"已组装 LEADERBOARD_HITS：{len(_lead_hits)} 本今日在榜（监测日 {_monitor_date}，原始命中 {len(_lead_raw)} 条）。")

# ---- 4.6 老书加推：数据回春（异常回升 / 今日上榜）----
# 数据回春判定（仅老书 days_online>NEW_DAYS）：
#   (A) 今日在某阅读平台飙升榜（_lead_hits 命中且老书）；
#   (B) 近3日有效在读UV 较自身前期基线显著回升（基线<120 且 近期≥60 且 ≥2.0倍）。
_REV_BIDS = set()
REVIVAL_HITS = []
for _h in _lead_hits:
    _bid = _h.get("book_id")
    _bk = _book_map.get(_bid, {})
    if _bk.get("days_online", 9999) > NEW_DAYS and any(it.get("section_key") == "飙升榜" for it in _h.get("items", [])):
        REVIVAL_HITS.append({"book_id": _bid, "kind": "上榜回春",
            "reason": f"老书（上架{_bk.get('days_online')}天）截至快照日登上某阅读平台飙升榜，站内热度明显回暖，建议承接加推。"})
        _REV_BIDS.add(_bid)
for b in books:
    _bid = str(b.get("bid") or "")
    if _bid in _REV_BIDS:
        continue
    _bk = _book_map.get(_bid, {})
    if _bk.get("days_online", 9999) <= NEW_DAYS:
        continue
    _tr = b.get("trend") or {}
    _eff = _tr.get("eff_uv") or []
    if len(_eff) < 14:
        continue
    _base = _eff[3:14]
    _recent = _eff[-3:]
    if not _base:
        continue
    _bm = sum(_base) / len(_base)
    _rm = sum(_recent) / len(_recent)
    if _bm > 0 and _bm < 120 and _rm >= 60 and _rm / _bm >= 2.0:
        REVIVAL_HITS.append({"book_id": _bid, "kind": "数据回春",
            "reason": f"老书（上架{_bk.get('days_online')}天）近3日有效在读UV从约{int(_bm)}回升至{int(_rm)}（≈{_rm/_bm:.1f}倍），数据回春，建议加推承接。"})
        _REV_BIDS.add(_bid)

data_js.append(f"const REVIVAL_HITS = {js_obj(REVIVAL_HITS)};")
print(f"已组装 老书加推（数据回春）：{len(REVIVAL_HITS)} 本。")

DATA_JS = "\n".join(data_js)

# =================== 5. 读取原始 HTML 并改造 ===================
html = open(SRC, encoding="utf-8").read()
print("原始 HTML 大小:", len(html))

# --- 5.1 替换数据块 ---
start = html.index("<script>\n// 自动生成的看板数据文件")
end = html.index("\n\n<script>\n\n/* __DASHBOARD_DATA__ 注入点", start)
new_script = "<script>\n" + DATA_JS + "\n</script>"
html = html[:start] + new_script + html[end:]
print("数据块已替换。")

# --- 5.2 浅色主题唯一：<html> 加 class="light" ---
html = html.replace('<html lang="zh-CN">', '<html lang="zh-CN" class="light">', 1)
# 删除深色 :root 块（仅保留 :root.light）
dark_root = """:root {
  --bg: #0f1117; --card-bg: #1a1d27; --card-border: #2a2d3a;
  --text: #e4e4e7; --text-secondary: #9ca3af;
  --accent: #2454ff; --accent-light: #466dff;
  --green: #247a5d; --red: #bd4664; --amber: #b58a2d; --blue: #3b82f6;
}
"""
if dark_root in html:
    html = html.replace(dark_root, "", 1)
    print("已删除深色 :root 定义。")
# 删除主题切换按钮
theme_btn = '    <button class="scope-btn" onclick="toggleTheme()" id="themeBtn" style="margin-left:12px;">浅色模式</button>\n'
if theme_btn in html:
    html = html.replace(theme_btn, "", 1)
    print("已删除主题切换按钮。")
# 替换主题恢复逻辑
restore_old = """// 恢复上次主题
if (localStorage.getItem('theme') === 'light') {
  document.documentElement.classList.add('light');
  document.getElementById('themeBtn').textContent = '深色模式';
}"""
restore_new = """// 仅保留浅色主题
document.documentElement.classList.add('light');"""
if restore_old in html:
    html = html.replace(restore_old, restore_new, 1)
    print("已固定浅色主题。")

# --- 5.2a 大标题改为 Annezhou 的数据看板（模板原占位名为"[模板占位名]"）---
if '<h1>[模板占位名]的数据看板</h1>' in html:
    html = html.replace('<h1>[模板占位名]的数据看板</h1>', '<h1>Annezhou的数据看板</h1>', 1)
    print("已将大标题改为 Annezhou的数据看板。")
else:
    print("警告：未找到原大标题，跳过标题替换。")
if '<title>内容版权数据看板</title>' in html:
    html = html.replace('<title>内容版权数据看板</title>', '<title>Annezhou的数据看板</title>', 1)
    print("已同步修改浏览器标签标题。")

# --- 5.2b 删除"今日编辑会议" magazine-lead 块（让 overviewWeekly 与 overviewChart 留在原位）---
_md = re.compile(r"  const overview = document\.getElementById\('panel-overview'\);.*?overview\.prepend\(lead\);\n  \}\n", re.DOTALL)
if _md.search(html):
    html = _md.sub("  const chart = document.getElementById('overviewChart');\n", html, count=1)
    print("已删除「今日编辑会议」magazine-lead 块。")
else:
    print("警告：未找到 magazine-lead 块，跳过删除。")

# --- 5.3 把"新书核心指标 Top 榜"插入到 panel-overview 最前面（overviewWeekly 之前）---
old_weekly_div = '  <div id="overviewWeekly" style="margin-bottom:16px;"></div>'
newbook_block = '''  <style>
  /* 新书核心指标 Top 榜列宽（2026-10-16）：书名加宽，数值列收窄 */
  #newbookTopTable { table-layout: fixed; width: 100%; }
  #newbookTopTable th, #newbookTopTable td { padding-left: 8px; padding-right: 8px; }
  #newbookTopTable td.title-cell { width: 300px; max-width: 300px; padding-right: 14px; }
  </style>
  <div id="newbookTopChart" style="margin-bottom:20px;">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
      <div style="font-size:15px;font-weight:700;color:var(--text);">新书核心指标 Top 榜 <span style="font-size:11px;color:var(--text-secondary);font-weight:400;">仅含近 14 天出版的新书 · 与总榜同格式</span></div>
      <select id="newbookMetric" onchange="newbookSortKey=this.value;newbookSortDir=(this.value==='days_online'?'asc':'desc');renderNewbookTopChart()" style="background:var(--card-bg);border:1px solid var(--card-border);color:var(--text);padding:6px 12px;border-radius:8px;font-size:13px;outline:none;">
        <option value="effective_reading_uv">有效在读UV</option>
        <option value="reading_uv">在读UV</option>
        <option value="new_reading_uv">新进UV</option>
        <option value="avg_reading_duration">人均时长(分)</option>
        <option value="next_day_retention">次留</option>
        <option value="day7_retention">次7留</option>
        <option value="recommendation_rate">推荐率</option>
        <option value="effective_reading_rate">有效阅读率</option>
        <option value="launch_date">上架日期</option>
        <option value="days_online">上架天数</option>
      </select>
    </div>
    <div class="table-wrap" style="max-height:none;">
      <table id="newbookTopTable">
        <thead><tr>
          <th data-nbtsort="launch_date" style="width:88px">上架日期</th>
          <th data-nbtsort="title" style="width:300px">书名</th>
          <th data-nbtsort="author" style="width:90px">作者</th>
          <th data-nbtsort="category_l1" style="width:84px">一级分类</th>
          <th data-nbtsort="category_l2" style="width:96px">二级分类</th>
          <th data-nbtsort="days_online" style="width:66px">上架天数</th>
          <th data-nbtsort="reading_uv" style="width:76px">在读UV</th>
          <th data-nbtsort="effective_reading_uv" style="width:92px">有效在读UV</th>
          <th data-nbtsort="effective_reading_rate" style="width:82px">有效阅读率</th>
          <th data-nbtsort="avg_reading_duration" style="width:82px">人均时长(分)</th>
          <th data-nbtsort="next_day_retention" style="width:68px">次留</th>
          <th data-nbtsort="day7_retention" style="width:68px">次7留</th>
          <th data-nbtsort="new_reading_uv" style="width:76px">新进UV</th>
          <th data-nbtsort="recommendation_rate" style="width:72px">推荐率</th>
        </tr></thead>
        <tbody id="newbookTopBody"></tbody>
      </table>
    </div>
    <div id="newbookTopFooter" style="margin-top:8px;font-size:11px;color:var(--text-secondary);"></div>
    <div id="newbookRecommend" style="margin-top:18px;"></div>
  </div>

''' + old_weekly_div
assert old_weekly_div in html, "overviewWeekly 锚点未找到"
html = html.replace(old_weekly_div, newbook_block, 1)
print("已把新书核心指标 Top 榜插入到面板最前。")

# --- 5.4 在 renderOverview 中调用新图表 ---
html = html.replace("  renderGainers();\n", "  renderGainers();\n  renderNewbookTopChart();\n", 1)
print("已挂接 renderNewbookTopChart 调用。")

# --- 5.5 新增 renderNewbookTopChart 函数（插在 renderOverviewChart 之前） ---
newbook_fn = r'''
let newbookSortKey = 'effective_reading_uv';
let newbookSortDir = 'desc';

function renderNewbookTopChart(){
  const body = document.getElementById('newbookTopBody');
  if (!body) return;
  const metricEl = document.getElementById('newbookMetric');
  const metric = metricEl ? metricEl.value : 'effective_reading_uv';
  // 【修复 2026-09-07】原先这里有 `newbookSortKey = metric;`，每次渲染都用下拉框值无条件覆盖排序键。
  // 而下拉框本来就没有 launch_date / days_online 两个选项，导致点表头设好的键在渲染瞬间被覆盖回指标键，
  // 表现为「上架日期 / 上架天数」点了没反应。排序键的唯一写入方应为下拉框 onchange 与表头点击。
  const newBooks = getScopedData().filter(b => b.days_online <= 14 && b.metrics.effective_reading_uv > 0);
  const metricNames = {
    effective_reading_uv:'有效在读UV', reading_uv:'在读UV', new_reading_uv:'新进UV',
    avg_reading_duration:'人均时长(分)', next_day_retention:'次留',
    day7_retention:'次7留', recommendation_rate:'推荐率', effective_reading_rate:'有效阅读率',
    launch_date:'上架日期', days_online:'上架天数'
  };
  const textKeys = ['title','author','category_l1','category_l2','launch_date'];
  const dir = newbookSortDir === 'asc' ? 1 : -1;
  const sk = newbookSortKey;
  const sorted = [...newBooks].sort((a,b)=>{
    let av, bv;
    if (textKeys.includes(sk)) { av=(a[sk]||'').toString(); bv=(b[sk]||'').toString(); return dir*av.localeCompare(bv,'zh'); }
    if (sk==='days_online') { av=a.days_online; bv=b.days_online; }
    else { av=a.metrics[sk]||0; bv=b.metrics[sk]||0; }
    return dir*(av-bv);
  });
  if (!sorted.length) {
    body.innerHTML = '<tr><td colspan="14" style="text-align:center;color:var(--text-secondary);font-size:13px;padding:24px;">近 14 天出版的新书暂无满足条件的有效数据</td></tr>';
    const f=document.getElementById('newbookTopFooter'); if(f) f.textContent='';
    return;
  }
  body.innerHTML = sorted.map((b)=>{
    const m=b.metrics;
    return `<tr onclick="openBookDetail('${b.book_id}')" style="cursor:pointer">
      <td>${b.launch_date}</td>
      <td class="title-cell" title="${b.title}&#10;bid: ${b.book_id}&#10;上架: ${b.launch_date}">${b.title}</td>
      <td>${b.author}</td>
      <td class="cat-cell">${b.category_l1}</td>
      <td class="cat-cell">${b.category_l2}</td>
      <td class="num">${b.days_online}</td>
      <td class="num">${fmt('reading_uv',m.reading_uv)}</td>
      <td class="num">${fmt('effective_reading_uv',m.effective_reading_uv)} ${chg(b.book_id,'effective_reading_uv')}</td>
      <td class="num">${fmt('effective_reading_rate',m.effective_reading_rate)}</td>
      <td class="num">${fmt('avg_reading_duration',m.avg_reading_duration)} ${chg(b.book_id,'avg_reading_duration')}</td>
      <td class="num">${fmt('next_day_retention',m.next_day_retention)} ${chg(b.book_id,'next_day_retention')}</td>
      <td class="num">${fmt('day7_retention',m.day7_retention)}</td>
      <td class="num">${fmt('new_reading_uv',m.new_reading_uv)}</td>
      <td class="num">${fmt('recommendation_rate',m.recommendation_rate)}</td>
    </tr>`;
  }).join('');
  const f=document.getElementById('newbookTopFooter');
  if(f) f.textContent = `共 ${newBooks.length} 本近 14 天新书 · 按${metricNames[newbookSortKey]||newbookSortKey}排序（${newbookSortDir==='asc'?'升序':'降序'}，点表头可切换升降序）`;
  document.querySelectorAll('#newbookTopTable thead th').forEach(th=>{
    th.classList.remove('sort-asc','sort-desc');
    if(th.dataset.nbtsort===newbookSortKey) th.classList.add(newbookSortDir==='asc'?'sort-asc':'sort-desc');
  });
}

document.querySelectorAll('#newbookTopTable thead th[data-nbtsort]').forEach(function(th){
  th.addEventListener('click', function(){
    const k=th.dataset.nbtsort;
    if(newbookSortKey===k){ newbookSortDir = newbookSortDir==='desc'?'asc':'desc'; }
    // days_online 默认升序：天数小=最新上架，符合「看新书」的直觉（降序会把最老的新书排在最前）
    else { newbookSortKey=k; newbookSortDir = (k==='days_online' || ['title','author','category_l1','category_l2'].includes(k)) ? 'asc' : 'desc'; }
    const sel=document.getElementById('newbookMetric');
    if(sel && sel.querySelector('option[value="'+k+'"]')) sel.value=k;
    renderNewbookTopChart();
  });
});

'''
anchor = "function renderOverviewChart(){"
assert anchor in html
ins = html.index(anchor)
html = html[:ins] + newbook_fn + html[ins:]
print("已注入 renderNewbookTopChart 函数。")

# --- 5.6 用新书导向的简化逻辑替换 renderRecommendations ---
new_recommend = r'''
function risingTier(rank) {
  if (!rank) return '';
  if (rank <= 5) return 'Top5';
  if (rank <= 10) return 'Top10';
  if (rank <= 30) return 'Top30';
  if (rank <= 50) return 'Top50';
  return '';
}
function effSurgePct(bid) {
  const tl = (typeof TIMELINE !== 'undefined') ? TIMELINE[bid] : null;
  if (!tl) return null;
  const dates = Object.keys(tl).sort();
  if (dates.length < 8) return null;
  const baseDates = dates.slice(0, 7);
  const base = baseDates.reduce((s, d) => s + (tl[d].effective_reading_uv || 0), 0) / baseDates.length;
  const recDates = dates.slice(-3);
  const rec = recDates.reduce((s, d) => s + (tl[d].effective_reading_uv || 0), 0) / recDates.length;
  if (base <= 0) return null;
  return (rec - base) / base * 100;
}
// 统一生成加推文案：仅列达标项（不输出具体数值）
// 固定优先级（用户 2026-09-01 定稿）：登榜 → 符合push标准 → 数据上涨 → 高于同品类 → 高推荐值
// 不符合或不存在的项一律不写
function buildReason(b, kind, risingRank) {
  const m = b.metrics;
  const eff = m.effective_reading_uv || 0;
  const retain = m.next_day_retention || 0;
  const rec = m.recommendation_rate || 0;
  const bm = getBenchmark(b.category_l1);
  const parts = [];
  // 1) 登榜（最高优先级）
  if (risingRank) {
    const tier = risingTier(risingRank);
    if (tier) parts.push('登上飙升榜' + tier);
  }
  // 2) 符合 push 标准
  const meet = [];
  if (eff >= 100) meet.push('有效在读');
  if (retain >= 25) meet.push('次留');
  if (rec >= 80) meet.push('推荐值');
  if (meet.length) parts.push(meet.join('/') + '符合push标准');
  // 3) 数据上涨（仅定性，不输出数值）
  const surge = effSurgePct(b.book_id);
  if (surge !== null && surge >= 30) parts.push('有效在读明显上涨');
  // 4) 高于同品类
  if (m.effective_reading_rate >= bm.eff_rate * 1.2 && m.next_day_retention >= bm.retention * 1.2) {
    parts.push('有效率和次留均高于' + b.category_l1 + '品类基准线20%以上');
  } else {
    if (m.effective_reading_rate >= bm.eff_rate * 1.2) parts.push('有效阅读率高于' + b.category_l1 + '品类基准线20%以上');
    if (m.next_day_retention >= bm.retention * 1.2) parts.push('次留高于' + b.category_l1 + '品类基准线20%以上');
  }
  // 5) 高推荐值
  if (rec >= 90) parts.push('推荐值极高，读者口碑极佳');
  else if (rec >= 88) parts.push('推荐值高，读者口碑佳');
  if (!parts.length) return '数据表现平稳，可酌情加推。';
  return parts.join('；');
}

function renderRecommendations() {
  const el = document.getElementById('newbookRecommend');
  const allBooks = getScopedData();
  const NEW_DAYS = 14;

  const newBooks = allBooks.filter(b => b.days_online <= NEW_DAYS && b.metrics.effective_reading_uv > 0);
  const oldBooks = allBooks.filter(b => b.days_online > NEW_DAYS && b.metrics.effective_reading_uv > 0);

  const meetCore = (m) => m.effective_reading_uv >= 100 && m.next_day_retention >= 25 && m.recommendation_rate >= 80;

  // 飙升榜 rank 索引（供文案使用）
  const _risingRank = {};
  if (typeof LEADERBOARD_HITS !== 'undefined') {
    LEADERBOARD_HITS.forEach(h => {
      (h.items || []).forEach(it => { if (it.section_key === '飙升榜') _risingRank[h.book_id] = it.rank; });
    });
  }

  const items = [];

  // 14天内新书：有效在读≥100、次留≥25%、推荐率≥80% 满足其中两项即可推；
  // 或有效在读>200 时其他数据一律不用管，直接推。
  // 但若仅靠"次留+推荐率"两项命中（有效在读未达100），须有效在读≥50 作基准线，避免极小样本被误推。
  newBooks.filter(b => {
    const m = b.metrics;
    if (m.effective_reading_uv > 200) return true;
    const cnt = (m.effective_reading_uv >= 100 ? 1 : 0)
              + (m.next_day_retention >= 25 ? 1 : 0)
              + (m.recommendation_rate >= 80 ? 1 : 0);
    // 满足任意两项即推；仅命中 次留+推荐率 时，额外要求 有效在读≥50 基准线
    return cnt >= 2 && m.effective_reading_uv >= 50;
  }).forEach(b => {
    items.push({ book: b, tag: ['green','建议加推'], kind: 'new' });
  });

  oldBooks.filter(b => {
    const m = b.metrics;
    return m.effective_reading_uv >= 300 && m.next_day_retention >= 30 && m.recommendation_rate >= 85;
  }).forEach(b => {
    items.push({ book: b, tag: ['blue','老书优品'], kind: 'old' });
  });

  // 老书加推：数据回春（今日上榜 / 异常回升）
  const _bookMap = {};
  allBooks.forEach(b => { _bookMap[b.book_id] = b; });
  const _rev = (typeof REVIVAL_HITS !== 'undefined') ? REVIVAL_HITS : [];
  _rev.forEach(h => {
    const b = _bookMap[h.book_id];
    if (!b) return;
    if (items.some(it => it.book.book_id === h.book_id)) return;
    items.push({ book: b, tag: ['amber','数据回春'], kind: 'revival' });
  });

  // 统一生成加推文案（紧凑、数据导向）
  items.forEach(it => { it.reason = buildReason(it.book, it.kind, _risingRank[it.book.book_id]); });

  const order = { 'green': 0, 'amber': 1, 'purple': 2, 'blue': 3 };
  items.sort((a,b) => (order[a.tag[0]] - order[b.tag[0]]) || (b.book.metrics.effective_reading_uv - a.book.metrics.effective_reading_uv));

  // 已加推持久化（localStorage）：勾选仅作标记，已加推的书仍显示在列表中
  const pushed = getPushedSet();
  const visible = items;

  function renderRecItem(c, i) {
    const b = c.book, m = b.metrics;
    const wasPushed = pushed.has(b.book_id);
    return `<div class="rec-item" style="display:flex;gap:10px;align-items:flex-start;">
      <input type="checkbox" ${wasPushed?'checked':''} onchange="togglePushed('${b.book_id}', this)" title="已加推请勾选标记（仍显示在列表中）" style="margin-top:5px;width:16px;height:16px;flex:none;cursor:pointer;accent-color:var(--accent);">
      <div style="flex:1;min-width:0;">
        <div class="rec-header" onclick="openBookDetail('${b.book_id}')">
          <span class="rec-title">${i+1}. ${b.title}</span>
          <span style="font-size:11px;color:var(--text-secondary);">${b.category_l1} · 上架${b.days_online}天</span>
        </div>
        <div class="rec-tags"><span class="rec-tag ${c.tag[0]}">${c.tag[1]}</span></div>
        <div class="rec-reason">${c.reason}</div>
        <div class="rec-metrics">
          <span>有效在读UV <span class="val">${m.effective_reading_uv.toLocaleString()}</span></span>
          <span>次留 <span class="val">${m.next_day_retention.toFixed(1)}%</span></span>
          <span>推荐率 <span class="val">${m.recommendation_rate.toFixed(1)}%</span></span>
        </div>
      </div>
    </div>`;
  }

  if (!visible.length) {
    const msg = '当前暂无可加推的新书或老书数据回春书目。';
    el.innerHTML = `<div class="recommend-card"><h3>建议加推 <span style="font-size:11px;color:var(--text-secondary);font-weight:400;">勾选标记已加推（仍显示）</span></h3>
      <p style="color:var(--text-secondary);font-size:13px;line-height:1.8;">${msg}</p></div>`;
    return;
  }

  el.innerHTML = `<div class="recommend-card" style="border-color:rgba(34,197,94,0.3);">
    <h3>建议加推 <span style="font-size:11px;color:var(--text-secondary);font-weight:400;">勾选标记已加推（仍显示）</span></h3>
    ${visible.slice(0, 20).map((c,i) => renderRecItem(c, i)).join('')}
  </div>`;
}

function getPushedSet() {
  try { return new Set(JSON.parse(localStorage.getItem('weread_pushed_bids') || '[]')); }
  catch (e) { return new Set(); }
}
function togglePushed(bid, el) {
  const s = getPushedSet();
  if (el.checked) s.add(bid); else s.delete(bid);
  localStorage.setItem('weread_pushed_bids', JSON.stringify([...s]));
  renderRecommendations();
}
function isSurging(book) {
  const tl = TIMELINE[book.book_id];
  if (!tl) return false;
  const dates = Object.keys(tl).sort();
  if (dates.length < 2) return false;
  const cur = tl[dates[dates.length - 1]].effective_reading_uv || 0;
  const past = tl[dates[Math.max(0, dates.length - 2)]].effective_reading_uv || 0;
  if (past <= 0) return cur >= 50;
  return (cur - past) / past >= 0.5;
}
'''
fn_start = html.index('function renderRecommendations() {')
fn_end = html.index('function scheduleOverviewChartRender')
html = html[:fn_start] + new_recommend + html[fn_end:]
print("已替换 renderRecommendations 为新课门槛逻辑。")

# --- 5.7 把「数据小结」容器放到 数据总览(panel-overview) 页面底部（overviewChart 之后、面板收尾前）---
# 用户要求：数据小结 应位于 数据总览 页底部，而非 近期上线 页。故不再插入 panel-newbooks，改插 panel-overview 末尾。
_ov_anchor = '  <div class="chart-box" id="overviewChart" style="min-height:400px;"></div>'
if _ov_anchor in html:
    html = html.replace(_ov_anchor, _ov_anchor + '\n  <div id="newbookSummary" style="margin-top:20px;"></div>', 1)
    print("已在 数据总览 页面底部插入 数据小结 容器。")
else:
    print("警告：未找到 overviewChart 锚点，跳过 数据小结 容器插入。")

# --- 5.8 「数据小结」渲染目标 = newbookSummary（容器已置于 数据总览 页面底部），并改为 14 天观察期 ---
html = html.replace(
    "  const el = document.getElementById('overviewWeekly');",
    "  const el = document.getElementById('newbookSummary');", 1)
print("已把 数据小结 渲染目标改为 newbookSummary。")

_old_win = "  const firstDate = DATES[0], lastDate = DATES[DATES.length-1];\n  const days = DATES.length;"
_new_win = ("  const obsDays = 14;\n"
            "  const lastDate = DATES[DATES.length-1];\n"
            "  const firstIdx = Math.max(0, DATES.length - obsDays);\n"
            "  const firstDate = DATES[firstIdx];\n"
            "  const days = DATES.length - firstIdx;")
assert _old_win in html, "数据小结日期窗口锚点未找到"
html = html.replace(_old_win, _new_win, 1)
print("已把 数据小结 观察期改为 14 天。")

html = html.replace(
    "  const newBooks = books.filter(b => b.days_online <= days + 3 && b.metrics.effective_reading_uv > 0);",
    "  const newBooks = books.filter(b => b.days_online <= obsDays && b.metrics.effective_reading_uv > 0);", 1)
print("已调整 数据小结 新上架过滤为 14 天。")

# --- 5.9 移除已迁走的空容器：overviewWeekly(数据小结) 与 overviewRecommend(建议加推) ---
_wk = '  <div id="overviewWeekly" style="margin-bottom:16px;"></div>\n'
if _wk in html:
    html = html.replace(_wk, '', 1)
    print("已移除 overviewWeekly 空容器。")
else:
    print("警告：未找到 overviewWeekly 容器。")
_rec = '  <div id="overviewRecommend" style="margin-bottom:20px;"></div>\n'
if _rec in html:
    html = html.replace(_rec, '', 1)
    print("已移除 overviewRecommend 空容器。")
else:
    print("警告：未找到 overviewRecommend 容器。")

# --- 5.10 加固详情弹窗趋势图：切换指标时强制重绘 ---
# 原逻辑复用同一 echarts 实例 + setOption(notMerge)，在弹窗/复用实例场景下真实浏览器常不触发重绘（曲线不随指标切换）。
# 改为每次 drawModalTrend 都 dispose 旧实例并重新 init，保证曲线随指标切换即时刷新。
_modal_init_old = "  let inst = echarts.getInstanceByDom(el);\n  if (!inst) inst = echarts.init(el);"
_modal_init_new = ("  let inst = echarts.getInstanceByDom(el);\n"
                   "  if (inst) inst.dispose();\n"
                   "  inst = echarts.init(el);\n"
                   "  if (inst && inst.resize) inst.resize();")
assert _modal_init_old in html, "drawModalTrend 初始化锚点未找到"
html = html.replace(_modal_init_old, _modal_init_new, 1)
print("已加固 drawModalTrend：切换趋势指标时强制重绘曲线图。")

# --- 5.10b 弹窗趋势指标默认值：由「次留」改为「有效在读UV」 ---
# 原始模板 modalTrendMetric select 默认选中 next_day_retention；按需求改为有效在读UV 默认展示。
# 用正则只命中 modalTrendMetric 这个 select 内的第一个 option，避免误改其他 select。
_modal_eff_old = r'(<select id="modalTrendMetric"[^>]*>\s*<option value="effective_reading_uv")>有效在读UV</option>'
assert re.search(_modal_eff_old, html), "modalTrendMetric 有效在读UV option 锚点未找到"
html = re.sub(_modal_eff_old, r'\1 selected>有效在读UV</option>', html, count=1)
assert '<option value="next_day_retention" selected>次留</option>' in html, "次留 selected 锚点未找到"
html = html.replace('<option value="next_day_retention" selected>次留</option>',
                    '<option value="next_day_retention">次留</option>', 1)
print("已将弹窗趋势指标默认值由「次留」改为「有效在读UV」。")

# --- 5.11 「观察期」标签口径：上架天数 ≤7 改为 ≤14 ---
# 原始模板(数据看板_2026.07.31.html)近期上线表格里给书打「观察期」橙标的判定写死 days_online<=7，
# 与「近期上线观察期=上架天数≤14」的口径不一致。改为 ≤14，使上架 14 天内的书都标观察期。
_obs_tag_old = "const obsTag = b.days_online <= 7"
_obs_tag_new = "const obsTag = b.days_online <= 14"
assert _obs_tag_old in html, "obsTag 锚点未找到"
html = html.replace(_obs_tag_old, _obs_tag_new, 1)
print("已把「观察期」标签口径改为 上架天数 ≤14。")

# --- 5.12 在「建议加推」(newbookRecommend) 容器下方新增「某阅读平台首页榜单监测」容器 ---
_nb_container = '  <div id="newbookRecommend" style="margin-top:18px;"></div>'
assert _nb_container in html, "newbookRecommend 容器锚点未找到"
html = html.replace(_nb_container, _nb_container + '\n  <div id="leaderboardMonitor" style="margin-top:18px;"></div>', 1)
print("已在「建议加推」下方插入 某阅读平台首页榜单监测 容器。")

# --- 5.13 新增 renderLeaderboardMonitor 渲染函数（放在 renderRecommendations 定义之前）---
# 渲染风格对齐原始模板 renderWereadMonitor：按书聚合的卡片式布局，
# 使用 rec-item / rec-tags / rec-reason / rec-metrics 等 CSS 类。
# 数据结构：LEADERBOARD_HITS 已在 §4.5 按书聚合，每条含 items[]（各榜单命中）+ 书自身指标。
_lead_render = r'''
function renderLeaderboardMonitor() {
  const el = document.getElementById('leaderboardMonitor');
  if (!el) return;
  const hits = (typeof LEADERBOARD_HITS !== 'undefined' && LEADERBOARD_HITS) ? LEADERBOARD_HITS : [];
  const monitorDate = (typeof LEADERBOARD_MONITOR_DATE !== 'undefined' && LEADERBOARD_MONITOR_DATE) ? LEADERBOARD_MONITOR_DATE : '';
  const uvMin = (typeof LEADERBOARD_UV_MIN !== 'undefined' && LEADERBOARD_UV_MIN) ? LEADERBOARD_UV_MIN : {};
  // 监测固定反映「今日在榜」快照，不受看板日期筛选影响
  const books = hits;
  const risingBooks = books.filter(b => b.items && b.items.some(it => it.section_key === '飙升榜'));
  const statusText = '仅监测飙升榜（UV≥50 过滤噪声，每日快照·非实时）';
  if (!books.length) {
    el.innerHTML = '<div class="recommend-card" style="border-color:rgba(59,130,246,0.24);">'
      + '<h3>某阅读平台首页榜单监测 <span style="font-size:11px;color:var(--text-secondary);font-weight:400;">'
      + monitorDate + ' · ' + statusText + '</span></h3>'
      + '<p style="color:var(--text-secondary);font-size:13px;line-height:1.8;margin:0;">'
      + '截至 ' + monitorDate + '，数据库中暂无书目进入某阅读平台飙升榜（快照日在榜，UV≥50 过滤后）。</p></div>';
    return;
  }
  const totalHits = books.reduce((s, b) => s + (b.items ? b.items.length : 0), 0);
  el.innerHTML = '<div class="recommend-card" style="border-color:rgba(34,197,94,0.28);background:linear-gradient(135deg,rgba(34,197,94,0.08),rgba(59,130,246,0.04));">'
    + '<h3>某阅读平台首页榜单监测 · 飙升榜 <span style="font-size:11px;color:var(--text-secondary);font-weight:400;">'
    + monitorDate + ' · 在榜 ' + books.length + ' 本'
    + ' · ' + statusText + '</span></h3>'
    + books.map(function(book, i) {
      var hasRising = book.items && book.items.some(function(it){ return it.section_key === '飙升榜'; });
      var exposureTags = (book.items || []).map(function(it) {
        var label = it.rank != null ? it.section_label + ' Top #' + it.rank : it.section_label;
        var cls = it.section_key === '飙升榜' ? 'amber' : 'green';
        return '<span class="rec-tag ' + cls + '">' + escapeHtml(label) + '</span>';
      }).join('');
      var risingRanks = (book.items || []).filter(function(it){ return it.section_key === '飙升榜'; });
      var minRank = risingRanks.length ? Math.min.apply(null, risingRanks.map(function(it){ return it.rank || 999; })) : 0;
      var reason = hasRising
        ? '飙升榜' + risingTier(minRank) + '，站内热度抬升，建议优先加推承接流量。'
        : '已出现在某阅读平台首页榜单，获得站内榜单曝光，建议承接流量加推。';
      var effUV = book.effective_reading_uv || 0;
      var retain = book.next_day_retention || 0;
      var recRate = book.recommendation_rate || 0;
      var hitCount = (book.items || []).length;
      return '<div class="rec-item">'
        + '<div class="rec-header" onclick="openBookDetail(\'' + book.book_id + '\')">'
        + '<span class="rec-title">' + (i + 1) + '. ' + escapeHtml(book.title) + '</span>'
        + '<span style="font-size:11px;color:var(--text-secondary);">命中 ' + hitCount + ' 处 · 上架' + book.days_online + '天</span>'
        + '</div>'
        + '<div class="rec-tags">'
        + (hasRising ? '<span class="rec-tag amber">飙升榜重点监测</span>' : '')
        + exposureTags
        + '<span class="rec-tag blue">建议加推</span>'
        + '</div>'
        + '<div class="rec-reason">' + reason + '</div>'
        + '<div class="rec-metrics">'
        + '<span>有效UV <span class="val">' + effUV.toLocaleString() + '</span></span>'
        + '<span>次留 <span class="val">' + retain.toFixed(1) + '%</span></span>'
        + '<span>推荐率 <span class="val">' + recRate.toFixed(1) + '%</span></span>'
        + '</div>'
        + '</div>';
    }).join('')
    + '</div>';
}
'''
assert 'function renderRecommendations() {' in html, "renderRecommendations 锚点未找到"
html = html.replace('function renderRecommendations() {', _lead_render + '\nfunction renderRecommendations() {', 1)
print("已注入 renderLeaderboardMonitor 渲染函数。")

# --- 5.14 在初始化中调用 renderLeaderboardMonitor（建议加推之后）---
assert '  renderRecommendations();' in html, "renderRecommendations 调用锚点未找到"
html = html.replace('  renderRecommendations();', '  renderRecommendations();\n  renderLeaderboardMonitor();', 1)
print("已在初始化中挂接 renderLeaderboardMonitor 调用。")

# --- 5.15 弹窗「加推文案」：去掉具体数值，只列达标项；飙升榜必注 ---
# dataStr: 不再输出具体数字，改为列出哪些指标符合push标准
_datastr_old = "const dataStr = `当日在读${m.reading_uv.toLocaleString()}，有效阅读率${m.effective_reading_rate.toFixed(1)}%，次留${m.next_day_retention.toFixed(1)}%，人均时长${m.avg_reading_duration.toFixed(1)}分钟，推荐值${m.recommendation_rate.toFixed(1)}%`;"
_datastr_new = """const _meetPush = [];
if (m.effective_reading_uv >= 100) _meetPush.push('有效在读');
if (m.next_day_retention >= 25) _meetPush.push('次留');
if (m.recommendation_rate >= 80) _meetPush.push('推荐值');
const dataStr = _meetPush.length ? _meetPush.join('/') + '符合push标准' : '数据表现平稳';"""
assert _datastr_old in html, "§5.15 dataStr 锚点未找到"
html = html.replace(_datastr_old, _datastr_new)
print("已将弹窗 dataStr 改为仅列达标项（不输出具体数值）。")

# 连涨文案也去掉具体天数
_html = html.replace(
    "'在读UV连涨' + uvStreak + '天，增长势头明显'",
    "'有效在读UV连续上涨，增长势头明显'"
)
if _html != html:
    html = _html
    print("已将弹窗加推文案的「有效在读UV连涨N天」改为不含具体天数。")

# --- 5.16 弹窗「加推文案」：整块重写 reasonParts，按固定优先级生成 ---
# 原 buildCopywriterPayload 的 reasonParts 按「品类基准 → 时长 → 推荐值 → 次7留 → UV连涨 →
# UV日增 → HOTSPOTS」堆砌，顺序与用户要求不符，且完全不读 LEADERBOARD_HITS（登榜信号丢失）。
# 用户 2026-09-01 定稿的固定优先级：登榜 → 符合push标准 → 数据上涨 → 高于同品类 → 高推荐值，
# 不符合或不存在的项一律不写。此处整块替换，不再依赖 §5.13 之外的任何零散注入。
_modal_parts_old = """  const reasonParts = [];

  if (m.effective_reading_rate >= bm.eff_rate * 1.2 && m.next_day_retention >= bm.retention * 1.2) {
    reasonParts.push('有效率和次留均高于' + book.category_l1 + '品类基准线20%以上，内容质量过硬');
  } else {
    if (m.effective_reading_rate >= bm.eff_rate * 1.2) reasonParts.push('有效阅读率高于' + book.category_l1 + '品类均值，开篇抓人能力强');
    if (m.next_day_retention >= bm.retention * 1.2) reasonParts.push('次留高于品类基准，用户粘性好');
  }

  if (m.avg_reading_duration >= bm.duration * 2) reasonParts.push('人均时长是品类均值的' + (m.avg_reading_duration / bm.duration).toFixed(1) + '倍，沉浸度极高');
  else if (m.avg_reading_duration >= bm.duration * 1.5) reasonParts.push('人均时长显著高于品类均值');

  if (m.recommendation_rate >= 90) reasonParts.push('推荐值' + m.recommendation_rate.toFixed(1) + '%，读者口碑极佳');
  if (m.day7_retention >= 25) reasonParts.push('次7留' + m.day7_retention.toFixed(1) + '%，长期留存优秀');
  else if (m.day7_retention >= 15 && !['男生小说', '女生小说'].includes(book.category_l1)) reasonParts.push('次7留' + m.day7_retention.toFixed(1) + '%，长线留存表现不错');

  const uvStreak = getStreak(book.book_id, 'effective_reading_uv');
  if (uvStreak >= 3) reasonParts.push('有效在读UV连续上涨，增长势头明显');
  if (HAS_PREV && ch.effective_reading_uv > 20) reasonParts.push('有效UV日增' + ch.effective_reading_uv.toFixed(1) + '%');

  const matchedHotspots = HOTSPOTS.filter(h => h.matched_bids && h.matched_bids[book.book_id]);
  matchedHotspots.forEach(h => {
    const isSocial = h.tier === '社会热点' || !h.tier;
    reasonParts.push(isSocial ? '近期站外"' + h.topic + '"热度高，可借势拉新' : '某阅读平台飙升榜"' + h.topic + '"同赛道在爆，可顺风跟推');
  });

  if (!reasonParts.length) {
    if (m.effective_reading_rate >= bm.eff_rate && m.next_day_retention >= bm.retention) reasonParts.push('各项数据达到' + book.category_l1 + '品类基准线，整体表现健康');
    else reasonParts.push('数据在品类基准线附近波动，建议持续观察');
  }
"""
# 注意：本替换在 §5.15 之后执行，锚点里的 uvStreak 文案须用 §5.15 已改写过的新措辞
# 「有效在读UV连续上涨，增长势头明显」（原措辞为「在读UV连涨N天」）。
_modal_parts_new = """  // matchedHotspots 仅供下方 basisLines 的「热点匹配」行展示，不进加推文案正文。
  // 不可删除：basisLines 仍引用它，删了会抛 ReferenceError 导致整个文案生成函数挂掉。
  const matchedHotspots = (typeof HOTSPOTS !== 'undefined' && HOTSPOTS)
    ? HOTSPOTS.filter(h => h.matched_bids && h.matched_bids[book.book_id]) : [];
  const reasonParts = [];
  // 加推文案固定优先级（用户 2026-09-01 定稿）：
  // 登榜 → 符合push标准 → 数据上涨 → 高于同品类 → 高推荐值
  // 不符合或不存在的项一律不写

  // 1) 登榜（最高优先级）
  const _risingItem = (typeof LEADERBOARD_HITS !== 'undefined') ? LEADERBOARD_HITS.find(h => String(h.book_id) === String(book.book_id)) : null;
  const _risingRankItem = _risingItem ? (_risingItem.items || []).find(it => it.section_key === '飙升榜') : null;
  if (_risingRankItem && _risingRankItem.rank) {
    const _tier = risingTier(_risingRankItem.rank);
    if (_tier) reasonParts.push('登上飙升榜' + _tier);
  }

  // 2) 符合 push 标准（_meetPush 由 §5.15 定义）
  if (_meetPush.length) reasonParts.push(_meetPush.join('/') + '符合push标准');

  // 3) 数据上涨
  const uvStreak = getStreak(book.book_id, 'effective_reading_uv');
  if (uvStreak >= 3) reasonParts.push('有效在读UV连续上涨，增长势头明显');
  if (HAS_PREV && ch.effective_reading_uv > 20) reasonParts.push('有效UV日增' + ch.effective_reading_uv.toFixed(1) + '%');

  // 4) 高于同品类
  if (m.effective_reading_rate >= bm.eff_rate * 1.2 && m.next_day_retention >= bm.retention * 1.2) {
    reasonParts.push('有效率和次留均高于' + book.category_l1 + '品类基准线20%以上');
  } else {
    if (m.effective_reading_rate >= bm.eff_rate * 1.2) reasonParts.push('有效阅读率高于' + book.category_l1 + '品类基准线20%以上');
    if (m.next_day_retention >= bm.retention * 1.2) reasonParts.push('次留高于' + book.category_l1 + '品类基准线20%以上');
  }

  // 5) 高推荐值
  if (m.recommendation_rate >= 90) reasonParts.push('推荐值极高，读者口碑极佳');
  else if (m.recommendation_rate >= 88) reasonParts.push('推荐值高，读者口碑佳');

  if (!reasonParts.length) reasonParts.push('数据在品类基准线附近波动，建议持续观察');
"""
assert _modal_parts_old in html, "§5.16 弹窗 reasonParts 整块锚点未找到"
html = html.replace(_modal_parts_old, _modal_parts_new, 1)
print("已按固定优先级重写弹窗 reasonParts（登榜→push标准→数据上涨→高于同品类→高推荐值）。")

# --- 5.17 弹窗「加推文案」：开头去掉书名，且不再内嵌 dataStr ---
# 用户要求：文案开头不用写书名（弹窗标题区已显示书名，正文开头重复显得累赘）。
_modal_intro_old = (
    "  const introTemplates = [\n"
    "    `《${book.title}》${dataStr}。`,\n"
    "    `今天可重点加推《${book.title}》：${dataStr}。`,\n"
    "    `建议继续放大《${book.title}》的曝光。${dataStr}。`\n"
    "  ];"
)
_modal_intro_new = (
    "  const introTemplates = [\n"
    "    ``,\n"
    "    `今天可重点加推：`,\n"
    "    `建议继续放大曝光：`\n"
    "  ];"
)
assert _modal_intro_old in html, "§5.17 弹窗 introTemplates 锚点未找到"
html = html.replace(_modal_intro_old, _modal_intro_new, 1)
print("已将弹窗「加推文案」开头的书名与 dataStr 去掉（push标准已移入 reasonParts 第2位）。")

# --- 5.18 弹窗「加推文案」：去掉 rotateList 轮换，保持固定优先级 ---
# 原模板用 rotateList(reasonParts, version) 按版本轮换理由顺序，会打乱
# 「登榜→push标准→数据上涨→高于同品类→高推荐值」的固定优先级，故改为直接使用原数组。
_modal_rot_old = "  const rotatedReasons = rotateList(reasonParts, version);"
_modal_rot_new = "  const rotatedReasons = reasonParts;  // 固定优先级，不做版本轮换"
assert _modal_rot_old in html, "§5.18 rotatedReasons 锚点未找到"
html = html.replace(_modal_rot_old, _modal_rot_new, 1)
print("已按固定优先级去掉弹窗文案的版本轮换（rotateList）。")

# --- 5.19 引用自检：防止「重写时删了定义行、但别处仍在引用」的静默崩溃 ---
# 事故复盘（2026-09-02）：§5.16 整块重写 reasonParts 时误删了
# `const matchedHotspots = ...`，而函数末尾 basisLines 的「热点匹配：${matchedHotspots.length...}」
# 仍引用它 → 运行时 ReferenceError，整个加推文案生成不出来。node --check 只查语法不查引用，
# 无法拦截。故在此对 buildCopywriterPayload 做一次轻量引用自检，缺定义直接中止构建。
def _check_payload_refs(html_text):
    _s = html_text.find('function buildCopywriterPayload(')
    assert _s > 0, "未找到 buildCopywriterPayload"
    _m = re.search(r'\nfunction \w+\(', html_text[_s + 10:])
    _body = html_text[_s:(_s + 10 + _m.start()) if _m else len(html_text)]
    _params = {'book', 'version'}
    _declared = set(re.findall(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)', _body))
    # 只看模板字符串 ${...} 里的首个标识符，覆盖「整个变量被删掉」这类致命情况
    _refs = set()
    for _expr in re.findall(r'\$\{([^}]*)\}', _body):
        _mm = re.match(r'\s*([A-Za-z_$][\w$]*)', _expr)
        if _mm:
            _refs.add(_mm.group(1))
    # 也检查裸标识符引用（如 `xxx.length` 出现在普通表达式里）
    _globals = {
        'Math', 'String', 'Number', 'Object', 'Array', 'JSON', 'Date', 'Boolean',
        'getBenchmark', 'risingTier', 'effSurgePct', 'getStreak', 'escapeHtml',
        'LEADERBOARD_HITS', 'LEADERBOARD_MONITOR_DATE', 'LEADERBOARD_UV_MIN',
        'HOTSPOTS', 'CHANGES', 'HAS_PREV', 'TIMELINE', 'BENCHMARKS', 'REVIVAL_HITS',
    }
    _missing = sorted(_refs - (_params | _declared | _globals))
    return _missing, sorted(_declared)

_missing, _declared = _check_payload_refs(html)
if _missing:
    raise SystemExit(
        f"❌ buildCopywriterPayload 引用了未定义的标识符 {_missing}。"
        f"（多半是整块重写时误删了定义行）已声明的局部变量: {_declared}"
    )
print(f"✓ 弹窗文案引用自检通过（局部变量 {len(_declared)} 个，无悬空引用）。")

# --- 5.17 导出CSV null-safety：部分轻故事 metrics 为 null，直接访问会 TypeError 崩溃 ---
_export_csv_old = """function exportDetailCSV() {
  const data = getFilteredData();
  const headers = ['bid','书名','作者','一级分类','二级分类','上架天数','上架日期','在读UV','有效在读UV','有效阅读率(%)','人均时长(分)','次留(%)','次7留(%)','新进UV','推荐率(%)'];
  const rows = data.map(b => {
    const m = b.metrics;
    return [b.book_id, b.title, b.author, b.category_l1, b.category_l2, b.days_online, b.launch_date, m.reading_uv, m.effective_reading_uv, m.effective_reading_rate, m.avg_reading_duration, m.next_day_retention, m.day7_retention, m.new_reading_uv, m.recommendation_rate].map(v => typeof v === 'string' && v.includes(',') ? '"'+v+'"' : v);
  });
  const csv = [headers.join(','), ...rows.map(r=>r.join(','))].join('\\n');
  downloadCSV('明细筛选_' + DATES[DATES.length-1] + '.csv', csv);
}"""
_export_csv_new = """function exportDetailCSV() {
  const data = getFilteredData();
  const headers = ['bid','书名','作者','一级分类','二级分类','上架天数','上架日期','在读UV','有效在读UV','有效阅读率(%)','人均时长(分)','次留(%)','次7留(%)','新进UV','推荐率(%)'];
  const _emptyMet = {reading_uv:0,effective_reading_uv:0,effective_reading_rate:0,avg_reading_duration:0,next_day_retention:0,day7_retention:0,new_reading_uv:0,recommendation_rate:0};
  const rows = data.map(b => {
    const m = b.metrics || _emptyMet;
    return [b.book_id, b.title, b.author, b.category_l1, b.category_l2, b.days_online, b.launch_date, m.reading_uv, m.effective_reading_uv, m.effective_reading_rate, m.avg_reading_duration, m.next_day_retention, m.day7_retention, m.new_reading_uv, m.recommendation_rate].map(v => typeof v === 'string' && v.includes(',') ? '"'+v+'"' : v);
  });
  const csv = [headers.join(','), ...rows.map(r=>r.join(','))].join('\\n');
  downloadCSV('明细筛选_' + DATES[DATES.length-1] + '.csv', csv);
}"""
if _export_csv_old in html:
    html = html.replace(_export_csv_old, _export_csv_new)
    print("已将 exportDetailCSV 改为 null-safe（metrics 为空时用零值兜底，不再崩溃）。")
else:
    print("⚠️ exportDetailCSV 锚点未匹配（可能已被修改过），跳过 null-safety 修复。")

# --- 5.20 加推文案卡片内「表格行」（用户 2026-09-15 需求，2026-09-21 三次修订）---
# 点开每本书 → 生成加推文案 → 表格行随卡片同步直接展示（常驻，无需点「展开依据」）。
# 列顺序：bookid / 书名 / 书籍分类 / 书籍上架时间 / 有效在读 / 次留 / 推荐值
# 口径：次留与推荐值带百分号；书籍分类为完整三级全路径（多条路径以 ; 分隔）；
#       制表符分隔，渲染为 flex 单行块，点一下即全选，Ctrl/Cmd+C 复制，粘贴进表格自动分列。
# (1) 依据「分类」行改为完整分类（三级、全部路径）
_cat_line_old = """    `分类：${book.category_l1}/${book.category_l2 || '-'}${book.category_l3 ? '/' + book.category_l3 : ''}`,"""
_cat_line_new = """    `分类：${book.category_full || [book.category_l1, book.category_l2, book.category_l3].filter(Boolean).join('/')}`,"""
if _cat_line_old in html:
    html = html.replace(_cat_line_old, _cat_line_new, 1)
    print("已将依据「分类」行改为完整分类（三级全路径）。")
else:
    print("⚠️ 依据「分类」行锚点未匹配，跳过完整分类改造。")

# (2) payload 增加 rowText：bookid / 书名 / 书籍分类 / 书籍上架时间 / 有效在读 / 次留 / 推荐值
#     次留与推荐值带百分号；分类取完整三级全路径；制表符分隔便于粘贴进表格自动分列。
_copy_row_ret_old = "return { version: version + 1, text, basisLines };"
_copy_row_ret_new = """  var _pct = function(v) { return (v === null || v === undefined || v === '') ? '' : Number(v).toFixed(1) + '%'; };
  var _rawv = function(v) { return (v === null || v === undefined || v === '') ? '' : v; };
  var _TABc = String.fromCharCode(9);
  var _rowText = [
    _rawv(book.book_id),
    book.title || '',
    book.category_full || [book.category_l1, book.category_l2, book.category_l3].filter(Boolean).join('/'),
    book.launch_date || '',
    _rawv(m.effective_reading_uv),
    _pct(m.next_day_retention),
    _pct(m.recommendation_rate)
  ].join(_TABc);
  return { version: version + 1, text, basisLines, rowText: _rowText };"""
if _copy_row_ret_old in html:
    html = html.replace(_copy_row_ret_old, _copy_row_ret_new, 1)
    print("已让加推文案 payload 携带 rowText（表格行，次留/推荐值带百分号）。")
else:
    print("⚠️ payload return 锚点未匹配，未能注入 rowText。")

# (3) 把「表格行」拆为独立块 rowBlock（不再挂进 basisLines），供 (6) 放到卡片正文区常驻展示
_basis_old = """  const basisHtml = payload.basisLines.map(line => `<li style="margin:0 0 6px 18px;">${escapeHtml(line)}</li>`).join('');"""
_basis_new = """  const basisHtml = payload.basisLines.map(line => `<li style="margin:0 0 6px 18px;">${escapeHtml(line)}</li>`).join('');
  const rowBlock = payload.rowText
    ? `<div style="margin-top:14px;">`
      + `<div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px;">表格行 <span style="font-size:11px;">（点一下即复制，或选中后 Ctrl/Cmd+C）</span></div>`
      + `<div class="tsv-row-box" onclick="selectRowAndCopy(this)" oncopy="copyRowPlain(event, this)"><span>${escapeHtml(payload.rowText)}</span></div>`
      + `</div>`
    : '';"""
if _basis_old in html:
    html = html.replace(_basis_old, _basis_new, 1)
    print("已把「表格行」拆为独立块 rowBlock。")
else:
    print("⚠️ basisHtml 渲染锚点未匹配，未能拆出 rowBlock。")

# (6) 把 rowBlock 放到卡片正文区（文案正文之后、折叠的「生成依据」之前），
#     使其随「生成加推文案」同步直接展示，不再依赖点击「展开依据」。
_row_ins_old = """    <div id="${basisId}" style="display:none;margin-top:14px;padding-top:12px;border-top:1px dashed var(--card-border);font-size:12px;color:var(--text-secondary);">"""
_row_ins_new = """    ${rowBlock}
    <div id="${basisId}" style="display:none;margin-top:14px;padding-top:12px;border-top:1px dashed var(--card-border);font-size:12px;color:var(--text-secondary);">"""
if _row_ins_old in html:
    html = html.replace(_row_ins_old, _row_ins_new, 1)
    print("已把「表格行」移到卡片正文区（生成文案即直接展示，无需展开依据）。")
else:
    print("⚠️ basisId 容器锚点未匹配，未能把「表格行」移出依据区。")

# (4) 表格行样式：加高框高、细滚动条、卡片质感（插入到最后一个 </style> 之前）
_tsv_css = """
/* 加推文案「生成依据」中的表格行：单行 TSV，点框内即全选可复制 */
.tsv-row-box {
  /* 用 flex + align-items:center 让整行上下居中（textarea 的行盒做不到，末几项会显得下沉） */
  display: flex;
  align-items: center;
  width: 100%;
  box-sizing: border-box;
  height: 50px;
  margin: 6px 0 0;
  padding: 0 12px;
  white-space: pre;
  overflow-x: auto;
  overflow-y: hidden;
  user-select: all;
  -webkit-user-select: all;
  cursor: text;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: rgba(127, 127, 127, 0.05);
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  outline: none;
  transition: border-color 0.18s ease, background 0.18s ease;
  scrollbar-width: thin;
  scrollbar-color: rgba(127, 127, 127, 0.3) transparent;
}
/* 禁止收缩，保证整行不被压窄换行；超出部分由容器横向滚动 */
.tsv-row-box > span { flex: 0 0 auto; white-space: pre; }
.tsv-row-box:hover { border-color: rgba(36, 84, 255, 0.35); }
.tsv-row-box:focus { border-color: var(--accent); background: var(--card-bg); }
.tsv-row-box::-webkit-scrollbar { height: 6px; }
.tsv-row-box::-webkit-scrollbar-track { background: transparent; }
.tsv-row-box::-webkit-scrollbar-thumb { background: rgba(127, 127, 127, 0.3); border-radius: 3px; }
.tsv-row-box::-webkit-scrollbar-thumb:hover { background: rgba(127, 127, 127, 0.5); }
"""
_style_idx = html.rfind("</style>")
if _style_idx != -1:
    html = html[:_style_idx] + _tsv_css + html[_style_idx:]
    print("已注入「表格行」样式（加高框高 + 细滚动条）。")
else:
    print("⚠️ 未找到 </style>，「表格行」样式未注入。")

# (5) 表格行复制：必须只往剪贴板写 text/plain。
#     若让浏览器按 DOM 选区自行复制，剪贴板会同时含 text/html，Excel / 飞书会优先按富文本解析，
#     制表符失效 → 粘贴后整行挤在一个格子里，无法按列拆分。
#     copyRowPlain 拦截 copy 事件强制纯文本；selectRowAndCopy 点击即选中并直接写剪贴板。
_select_anchor = "function toggleCopywriterBasis(basisId, button) {"
_select_fn = """function rowFlash(el) {
  var prev = el.style.borderColor;
  el.style.borderColor = 'var(--green)';
  setTimeout(function() { el.style.borderColor = prev; }, 900);
}
function selectRowAndCopy(el) {
  try {
    var r = document.createRange();
    r.selectNodeContents(el);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  } catch (e) {}
  var txt = el.textContent || '';
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(function() { rowFlash(el); }).catch(function() {});
  }
}
function copyRowPlain(e, el) {
  try {
    e.preventDefault();
    if (e.clipboardData) e.clipboardData.setData('text/plain', el.textContent || '');
    rowFlash(el);
  } catch (err) {}
}

"""
if _select_anchor in html:
    html = html.replace(_select_anchor, _select_fn + _select_anchor, 1)
    print("已注入表格行复制函数（强制纯文本，保证粘贴可按制表符分列）。")
else:
    print("⚠️ toggleCopywriterBasis 锚点未匹配，未能注入复制函数。")

# --- 5.21 修复弹窗单本书趋势图 hover 不显示数据（用户 2026-09-21 反馈）---
# 根因：TIMELINE 里部分日期缺记录，series data 出现 null/undefined；
# 而 tooltip formatter 直接 p.value.toFixed() / p.value.toLocaleString()，遇空值抛 TypeError，
# 整个 tooltip 直接不渲染（不只是缺数据的那一个点）。
# 修法：① 取值把 undefined 归一为 null（ECharts 会断线而不报错）② formatter 加空值保护显示「—」。
_trend_tip_old = "formatter: params => params.map(p => p.marker + ' ' + p.seriesName + ': ' + (isPct ? p.value.toFixed(1)+'%' : p.value.toLocaleString())).join('<br/>')"
_trend_tip_new = """formatter: params => params.map(p => {
      const _v = p.value;
      const _txt = (_v === null || _v === undefined || _v === '') ? '—'
        : (isPct ? Number(_v).toFixed(1) + '%' : Number(_v).toLocaleString());
      return p.marker + ' ' + p.seriesName + ': ' + _txt;
    }).join('<br/>')"""
if _trend_tip_old in html:
    html = html.replace(_trend_tip_old, _trend_tip_new, 1)
    print("已修复趋势图 tooltip：空值不再抛异常。")
else:
    print("⚠️ 趋势图 tooltip 锚点未匹配，跳过修复。")

_trend_data_old = "        return td && td[d] ? td[d][metric] : null;"
_trend_data_new = """        const _tv = td && td[d] ? td[d][metric] : null;
        return (_tv === undefined) ? null : _tv;"""
if _trend_data_old in html:
    html = html.replace(_trend_data_old, _trend_data_new, 1)
    print("已把趋势图数据里的 undefined 归一为 null。")
else:
    print("⚠️ 趋势图 data 取值锚点未匹配，跳过修复。")

# --- 5.18 新增「阅读总量」维度（2026-10-16）：近期上线表列 + Top10 榜 + 分类分布下拉 ---
# 口径：demo.book_meta.total_reading（书籍累计阅读人数），经 build_data.py
# meta SQL -> extract.py book.total_reading -> 本文件 §1 metrics.total_reading 全链路注入。

# 1) MF 格式化器：加 total_reading（千分位）
_mf_old = "  new_reading_uv: v=>v.toLocaleString(), recommendation_rate: v=>v.toFixed(1)+'%',"
_mf_new = "  new_reading_uv: v=>v.toLocaleString(), recommendation_rate: v=>v.toFixed(1)+'%',\n  total_reading: v=>v.toLocaleString(),"
assert _mf_old in html, "§5.18 MF 锚点未找到"
html = html.replace(_mf_old, _mf_new, 1)
print("已给 MF 格式化器加 total_reading（千分位）。")

# 2) 近期上线书籍概况表：新进UV 后加「阅读总量」列（表头 + 行单元格）
_th_old = '<th data-nbsort="new_reading_uv" style="width:80px">新进UV</th>'
_th_new = _th_old + '\n        <th data-nbsort="total_reading" style="width:80px">阅读总量</th>'
assert _th_old in html, "§5.18 newBooksTable th 锚点未找到"
html = html.replace(_th_old, _th_new, 1)

_td_old = "<td class=\"num\">${fmt('new_reading_uv', m.new_reading_uv)} ${chg(b.book_id,'new_reading_uv')}</td>"
_td_new = _td_old + "\n      <td class=\"num\">${fmt('total_reading', m.total_reading)}</td>"
assert _td_old in html, "§5.18 renderNewBooks td 锚点未找到"
html = html.replace(_td_old, _td_new, 1)
print("已在近期上线书籍概况表加「阅读总量」列（可排序）。")

# 3) 数据总览 Top 10 卡片区：用「阅读总量 Top 10」替换掉「推荐率 Top 10」（2026-10-16 用户要求移除推荐率榜）
#    只动 renderOverview 内的 byRec 定义与卡片；智能分析里另有一处同名 byRec，不能碰。
_byrec_old = "const byRec=[...books].filter(b=>b.metrics.effective_reading_uv>=10).sort((a,b)=>b.metrics.recommendation_rate-a.metrics.recommendation_rate).slice(0,10);"
_byrec_new = "const byTotal=[...books].slice().sort((a,b)=>(b.metrics.total_reading||0)-(a.metrics.total_reading||0)).slice(0,10);"
assert _byrec_old in html, "§5.18 byRec 锚点未找到"
html = html.replace(_byrec_old, _byrec_new, 1)

_card_old = "<div class=\"summary-card\"><h3>推荐率 Top 10</h3><div class=\"items\">${rl(byRec,'recommendation_rate')}</div></div>`;"
_card_new = "<div class=\"summary-card\"><h3>阅读总量 Top 10</h3><div class=\"items\">${rl(byTotal,'total_reading')}</div></div>`;"
assert _card_old in html, "§5.18 推荐率卡片锚点未找到"
html = html.replace(_card_old, _card_new, 1)
print("已移除「推荐率 Top 10」，改为「阅读总量 Top 10」。")

# 4) 分类分布维度下拉 + metricNames：加 total_reading（求和聚合，走默认 else 分支）
_opt_old = """      <option value="new_reading_uv">新进UV</option>
      <option value="recommendation_rate">平均推荐率</option>
    </select>"""
_opt_new = """      <option value="new_reading_uv">新进UV</option>
      <option value="recommendation_rate">平均推荐率</option>
      <option value="total_reading">阅读总量</option>
    </select>"""
assert _opt_old in html, "§5.18 overviewMetric 下拉锚点未找到"
html = html.replace(_opt_old, _opt_new, 1)

_mn_old = "day7_retention:'平均次7留(%)', new_reading_uv:'新进UV', recommendation_rate:'平均推荐率(%)'"
_mn_new = "day7_retention:'平均次7留(%)', new_reading_uv:'新进UV', recommendation_rate:'平均推荐率(%)',\n    total_reading:'阅读总量'"
assert _mn_old in html, "§5.18 metricNames 锚点未找到"
html = html.replace(_mn_old, _mn_new, 1)
print("已在分类分布维度加「阅读总量」（按一级分类求和）。")

# --- 6. 写出 ---
open(DST, "w", encoding="utf-8").write(html)
print("已写出:", DST, "大小:", len(html))
