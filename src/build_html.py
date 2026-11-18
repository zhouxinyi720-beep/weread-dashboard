#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取 dashboard_data.json，生成自包含数据看板 HTML。"""
import json, os

OUT = '<工作目录>/weread_dashboard/out'
data = json.load(open(os.path.join(OUT, 'dashboard_data.json'), encoding='utf-8'))
data_json = json.dumps(data, ensure_ascii=False)

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>某阅读平台版权数据看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{
  --bg:#f5f6f8; --card:#ffffff; --ink:#1f2329; --ink2:#646a73; --line:#e7e9ee;
  --blue:#3370ff; --green:#34c759; --amber:#ff9f0a; --red:#ff453a; --teal:#15c5ce; --purple:#7c5cff;
  --shadow:0 1px 3px rgba(0,0,0,.06),0 4px 16px rgba(0,0,0,.04);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.5}
.wrap{max-width:1320px;margin:0 auto;padding:20px 22px 60px}
header{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:18px}
header h1{font-size:22px;font-weight:700;letter-spacing:.5px}
header .meta{color:var(--ink2);font-size:12.5px}
.cards{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}
.card{background:var(--card);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.card .k{color:var(--ink2);font-size:12px;margin-bottom:6px}
.card .v{font-size:22px;font-weight:700}
.card .s{font-size:11.5px;color:var(--ink2);margin-top:4px}
.grade-pill{display:inline-block;padding:1px 8px;border-radius:20px;font-weight:700;font-size:12px;color:#fff}
.g-A{background:var(--green)} .g-B{background:var(--blue)} .g-C{background:var(--amber)} .g-D{background:var(--red)} .g-S{background:#d6336c}
.panel{background:var(--card);border-radius:12px;padding:16px 18px;box-shadow:var(--shadow);margin-bottom:18px}
.panel h3{font-size:15px;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.panel h3 .tag{font-size:11px;font-weight:400;color:var(--ink2)}
.grid-top{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.chart{width:100%;height:300px}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
.toolbar input,.toolbar select{padding:7px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff;color:var(--ink)}
.toolbar input[type=text]{min-width:200px}
.toolbar .sp{flex:1}
.sortbtn{background:#fff;border:1px solid var(--line);border-radius:8px;padding:7px 11px;font-size:12.5px;cursor:pointer}
.sortbtn.on{border-color:var(--blue);color:var(--blue);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:nth-child(-n+4),td:nth-child(-n+4){text-align:left}
th{position:sticky;top:0;background:#fafbfc;cursor:pointer;user-select:none;font-weight:600;color:var(--ink2);z-index:2}
th:hover{color:var(--blue)}
tbody tr:hover{background:#f7f9ff}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--green);font-weight:600} .neg{color:var(--red);font-weight:600}
.badge{display:inline-block;padding:1px 7px;border-radius:6px;font-size:11px;font-weight:600}
.b-hit{background:#fff3e0;color:#c77700}
.b-none{background:#f0f1f3;color:#9aa0aa}
.tabs{display:flex;gap:8px;margin-bottom:12px}
.tab{padding:6px 14px;border-radius:8px;background:#f0f1f3;cursor:pointer;font-size:13px;font-weight:600;color:var(--ink2)}
.tab.on{background:var(--blue);color:#fff}
.rec{display:flex;gap:14px;flex-wrap:wrap}
.rec-col{flex:1;min-width:260px}
.rec-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:9px;margin-bottom:9px;background:#fafbfc;border:1px solid var(--line)}
.rec-item .dot{width:9px;height:9px;border-radius:50%;flex:none}
.d-strong{background:#eafaf0;border-color:#bfe9cc} .d-strong .dot{background:var(--green)}
.d-add{background:#eef3ff;border-color:#cdddff} .d-add .dot{background:var(--blue)}
.d-watch{background:#fff8ec;border-color:#ffe2b0} .d-watch .dot{background:var(--amber)}
.d-cut{background:#fdeeee;border-color:#f7cccc} .d-cut .dot{background:var(--red)}
.rec-item .tt{font-weight:600;font-size:13px}
.rec-item .rs{color:var(--ink2);font-size:11.5px;margin-left:auto;text-align:right}
.note{color:var(--ink2);font-size:12px;line-height:1.7}
@media(max-width:900px){.cards{grid-template-columns:repeat(3,1fr)}.grid-top{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>某阅读平台版权数据看板</h1>
      <div class="meta" id="hdr-meta"></div>
    </div>
    <div class="meta" id="hdr-gen"></div>
  </header>

  <div class="cards" id="cards"></div>

  <div class="panel">
    <h3>核心指标 Top 榜 <span class="tag">取最新数据日快照；点击表头可联动排序</span></h3>
    <div class="grid-top">
      <div><div id="bar-uv" class="chart"></div></div>
      <div><div id="bar-retain" class="chart"></div></div>
      <div><div id="bar-dur" class="chart"></div></div>
      <div><div id="bar-growth" class="chart"></div></div>
    </div>
  </div>

  <div class="panel">
    <h3>有效在读UV 趋势 <span class="tag">默认展示当前有效在读UV最高的 6 本；可切换指标与数量</span></h3>
    <div class="toolbar">
      <select id="trend-metric">
        <option value="eff_uv">有效在读UV</option>
        <option value="reading_uv">在读UV</option>
      </select>
      <select id="trend-topn">
        <option value="6">Top 6</option>
        <option value="10">Top 10</option>
        <option value="15">Top 15</option>
      </select>
      <span class="sp"></span>
      <span class="note">数据区间：<span id="trend-range"></span></span>
    </div>
    <div id="trend" class="chart" style="height:360px"></div>
  </div>

  <div class="panel">
    <h3>明细表 <span class="tag">支持按分类 / 评级 / 书名筛选，点击表头排序</span></h3>
    <div class="toolbar">
      <input type="text" id="f-search" placeholder="搜索书名 / 作者 / bid">
      <select id="f-cat1"><option value="">全部分类</option></select>
      <select id="f-grade"><option value="">全部评级</option><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select>
      <select id="f-sort">
        <option value="eff_uv">按有效在读UV</option>
        <option value="reading_uv">按在读UV</option>
        <option value="eff_rate">按有效阅读率</option>
        <option value="retain1">按次留</option>
        <option value="avg_dur_min">按人均时长</option>
        <option value="growth_eff_uv">按涨幅</option>
        <option value="fusion">按融合分</option>
      </select>
      <button class="sortbtn on" id="f-dir">降序</button>
      <span class="sp"></span>
      <span class="note" id="tbl-count"></span>
    </div>
    <div style="overflow:auto;max-height:620px">
      <table id="tbl">
        <thead><tr>
          <th data-k="title">书名</th><th data-k="author">作者</th><th data-k="cat1">一级分类</th>
          <th data-k="grade">评级</th><th data-k="reading_uv">在读UV</th><th data-k="eff_uv">有效在读UV</th>
          <th data-k="eff_rate">有效阅读率</th><th data-k="avg_dur_min">人均时长(分)</th><th data-k="retain1">次留</th>
          <th data-k="retain7">次7留</th><th data-k="xinjin_uv">新进UV</th><th data-k="rec_rate">推荐值</th>
          <th data-k="growth_eff_uv">涨幅</th><th data-k="age_days">上架天</th><th data-k="toplist">榜单命中</th>
        </tr></thead>
        <tbody id="tbl-body"></tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h3>某阅读平台首页榜单监测 <span class="tag" id="top-note"></span></h3>
    <div id="toplist-box" class="note"></div>
  </div>

  <div class="panel">
    <h3>加推 / 观察 / 减推建议 <span class="tag">基于评级、有效在读UV、次留、涨幅的规则分级（仅供参考）</span></h3>
    <div class="rec" id="rec-box"></div>
  </div>

  <div class="panel">
    <h3>口径说明</h3>
    <div class="note" id="notes"></div>
  </div>
</div>

<script>
const DATA = __DATA__;
const fmt = (n)=> n==null?'—':(n>=10000?(n/10000).toFixed(1)+'w':n.toLocaleString());
const pct = (n)=> n==null?'—':n.toFixed(1)+'%';
const books = DATA.books;

// 概览
document.getElementById('hdr-meta').textContent = `数据日期 ${DATA.data_date} ｜ 监测书籍 ${DATA.bid_count} 本 ｜ 窗口 ${DATA.date_window[0]} ~ ${DATA.date_window[1]}`;
document.getElementById('hdr-gen').textContent = `生成于 ${DATA.generated_at}`;
const sumUV = books.reduce((a,b)=>a+(b.snap?b.snap.eff_uv:0),0);
const valid = books.filter(b=>b.snap);
const avgEff = valid.length? valid.reduce((a,b)=>a+b.snap.eff_rate,0)/valid.length:0;
const avgRet = valid.length? valid.reduce((a,b)=>a+b.snap.retain1,0)/valid.length:0;
const gd = DATA.grade_dist||{};
const cards = [
  ['监测书籍', DATA.bid_count, `窗口 ${DATA.date_window[0]}~${DATA.date_window[1]}`],
  ['累计有效在读UV', fmt(sumUV), `于 ${DATA.data_date}`],
  ['平均有效阅读率', pct(avgEff), `${valid.length} 本有数据`],
  ['平均次留', pct(avgRet), `${valid.length} 本有数据`],
  ['A 级书', gd.A||0, `B ${gd.B||0} · C ${gd.C||0} · D ${gd.D||0}`],
  ['榜单命中书', books.filter(b=>b.toplist.length).length, '近21天露出'],
];
document.getElementById('cards').innerHTML = cards.map(c=>`<div class="card"><div class="k">${c[0]}</div><div class="v">${c[1]}</div><div class="s">${c[2]}</div></div>`).join('');

// 分类下拉
const catSet = [...new Set(books.map(b=>b.cat1).filter(Boolean))].sort();
document.getElementById('f-cat1').innerHTML = '<option value="">全部分类</option>'+catSet.map(c=>`<option>${c}</option>`).join('');

// 颜色
const PAL = ['#3370ff','#34c5ce','#ff9f0a','#7c5cff','#34c759','#ff6b6b','#5b8def','#f7b500','#22c1a4','#e36cc0'];
function hBar(elId,title,arr,valKey,fmtFn){
  const top = arr.slice(0,10).reverse();
  const ch = echarts.init(document.getElementById(elId));
  ch.setOption({
    title:{text:title,left:0,top:0,textStyle:{fontSize:13,fontWeight:600,color:'#1f2329'}},
    grid:{left:8,right:54,top:34,bottom:6,containLabel:true},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},formatter:p=>p[0].name+'<br/>'+fmtFn(p[0].value)},
    xAxis:{type:'value',axisLabel:{formatter:v=>fmtFn(v)}},
    yAxis:{type:'category',data:top.map(b=>b.title.length>9?b.title.slice(0,9)+'…':b.title),axisLabel:{fontSize:11}},
    series:[{type:'bar',data:top.map(b=>valKey(b)),barMaxWidth:18,
      itemStyle:{color:(p)=>PAL[p.dataIndex%PAL.length],borderRadius:[0,4,4,0]},
      label:{show:true,position:'right',fontSize:11,formatter:p=>fmtFn(p.value)}}]
  });
  return ch;
}
const byUV = [...books].filter(b=>b.snap).sort((a,b)=>b.snap.eff_uv-a.snap.eff_uv);
const byRet = [...books].filter(b=>b.snap).sort((a,b)=>b.snap.retain1-a.snap.retain1);
const byDur = [...books].filter(b=>b.snap).sort((a,b)=>b.snap.avg_dur_min-a.snap.avg_dur_min);
const byGro = [...books].filter(b=>b.growth_eff_uv!=null).sort((a,b)=>b.growth_eff_uv-a.growth_eff_uv);
const charts=[];
charts.push(hBar('bar-uv','有效在读UV Top10',byUV,b=>b.snap.eff_uv,fmt));
charts.push(hBar('bar-retain','次留 Top10',byRet,b=>b.snap.retain1,v=>v.toFixed(1)+'%'));
charts.push(hBar('bar-dur','人均时长 Top10',byDur,b=>b.snap.avg_dur_min,v=>v.toFixed(1)+'分'));
charts.push(hBar('bar-growth','有效在读UV 涨幅 Top10',byGro,b=>b.growth_eff_uv,v=>(v>0?'+':'')+v.toFixed(1)+'%'));

// 趋势
const trendEl = document.getElementById('trend');
const trendCh = echarts.init(trendEl);
document.getElementById('trend-range').textContent = DATA.date_window.join(' ~ ');
function drawTrend(){
  const metric = document.getElementById('trend-metric').value;
  const n = +document.getElementById('trend-topn').value;
  const sel = byUV.slice(0,n);
  const dates = sel[0]?sel[0].trend.dates:[];
  const series = sel.map((b,i)=>({
    name:b.title.length>10?b.title.slice(0,10)+'…':b.title,
    type:'line',smooth:true,symbol:'none',
    data:b.trend[metric=='eff_uv'?'eff_uv':'reading_uv'],
    lineStyle:{width:2},itemStyle:{color:PAL[i%PAL.length]}
  }));
  trendCh.setOption({
    tooltip:{trigger:'axis'},
    legend:{type:'scroll',top:0,textStyle:{fontSize:11}},
    grid:{left:8,right:18,top:42,bottom:8,containLabel:true},
    xAxis:{type:'category',data:dates,axisLabel:{fontSize:10,rotate:45}},
    yAxis:{type:'value',axisLabel:{formatter:v=>fmt(v)}},
    series
  },true);
}
document.getElementById('trend-metric').onchange=drawTrend;
document.getElementById('trend-topn').onchange=drawTrend;
drawTrend();

// 明细表
const tbody = document.getElementById('tbl-body');
let sortKey='eff_uv', sortDir=-1;
function getVal(b,k){
  if(k==='grade') return b.rating.grade||'';
  if(k==='age_days') return b.age_days??-1;
  if(k==='toplist') return b.toplist.length;
  if(k==='fusion') return b.rating.fusion??-1;
  if(b.snap) return b.snap[k]??(b[k]??null);
  return b[k]??null;
}
function renderTable(){
  const q=document.getElementById('f-search').value.trim().toLowerCase();
  const cat=document.getElementById('f-cat1').value;
  const grade=document.getElementById('f-grade').value;
  const sk=document.getElementById('f-sort').value;
  sortKey=sk;
  let rows=books.filter(b=>{
    if(cat&&b.cat1!==cat)return false;
    if(grade&&(b.rating.grade||'')!==grade)return false;
    if(q){const t=(b.title+' '+b.author+' '+b.bid).toLowerCase();if(!t.includes(q))return false;}
    return true;
  });
  rows.sort((a,b)=>{
    let va=getVal(a,sk),vb=getVal(b,sk);
    if(va==null)va=-1e9; if(vb==null)vb=-1e9;
    if(typeof va==='string')return sortDir*va.localeCompare(vb,'zh');
    return sortDir*(va-vb);
  });
  tbody.innerHTML=rows.map(b=>{
    const s=b.snap||{};
    const g=b.rating.grade||'';
    const gr = b.growth_eff_uv==null?'—':`<span class="${b.growth_eff_uv>=0?'pos':'neg'}">${b.growth_eff_uv>0?'+':''}${b.growth_eff_uv.toFixed(1)}%</span>`;
    const top = b.toplist.length?`<span class="badge b-hit">${b.toplist.length}次</span>`:`<span class="badge b-none">—</span>`;
    return `<tr>
      <td title="${b.title}">${b.title||'—'}</td>
      <td>${b.author||'—'}</td>
      <td>${b.cat1||'—'}</td>
      <td>${g?`<span class="grade-pill g-${g}">${g}</span>`:'—'}</td>
      <td class="num">${s.reading_uv??'—'}</td>
      <td class="num">${s.eff_uv??'—'}</td>
      <td class="num">${s.eff_rate!=null?pct(s.eff_rate):'—'}</td>
      <td class="num">${s.avg_dur_min!=null?s.avg_dur_min.toFixed(1):'—'}</td>
      <td class="num">${s.retain1!=null?pct(s.retain1):'—'}</td>
      <td class="num">${s.retain7!=null?pct(s.retain7):'—'}</td>
      <td class="num">${b.xinjin_uv??'—'}</td>
      <td class="num">${b.rec_rate??'—'}</td>
      <td class="num">${gr}</td>
      <td class="num">${b.age_days??'—'}</td>
      <td>${top}</td>
    </tr>`;
  }).join('');
  document.getElementById('tbl-count').textContent=`共 ${rows.length} 本`;
}
['f-search','f-cat1','f-grade','f-sort'].forEach(id=>document.getElementById(id).addEventListener('input',renderTable));
document.getElementById('f-dir').onclick=function(){sortDir*=-1;this.textContent=sortDir<0?'降序':'升序';this.classList.toggle('on',sortDir<0);renderTable();};
document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{document.getElementById('f-sort').value=th.dataset.k;renderTable();});
renderTable();

// 榜单监测
const hitBooks = books.filter(b=>b.toplist.length).sort((a,b)=>b.toplist.length-a.toplist.length);
document.getElementById('top-note').textContent=`近21天共 ${hitBooks.length} 本书登上飙升榜/新书榜/小说榜`;
document.getElementById('toplist-box').innerHTML = hitBooks.length? hitBooks.slice(0,40).map(b=>{
  const items=b.toplist.slice(0,3).map(t=>`${t.scene}第${t.rank}位`).join('、');
  return `<div style="padding:5px 0;border-bottom:1px dashed #eee"><b>${b.title}</b> <span style="color:#646a73">(${b.cat1})</span> — <span style="color:#c77700">${items}</span></div>`;
}).join('') : '近21天无榜单命中记录。';

// 加推建议
function classify(b){
  const g=b.rating.grade||''; const s=b.snap||{}; const uv=s.eff_uv||0; const ret=s.retain1||0; const gr=b.growth_eff_uv;
  if((g==='A')&&uv>=200&&(gr==null||gr>=0)) return 'strong';
  if((g==='A'||g==='B')&&uv>=100&&ret>=30) return 'add';
  if(b.age_days!=null&&b.age_days<=30) return 'watch';
  if(g==='D'||(uv<30&&(gr!=null&&gr<=-20))) return 'cut';
  if(g==='B'&&uv>=50) return 'add';
  return 'watch';
}
const rec={strong:[],add:[],watch:[],cut:[]};
books.forEach(b=>rec[classify(b)].push(b));
const recBox=document.getElementById('rec-box');
const cols=[
  ['strong','d-strong','强烈加推',`${rec.strong.length} 本`],
  ['add','d-add','建议加推',`${rec.add.length} 本`],
  ['watch','d-watch','观察名单',`${rec.watch.length} 本`],
  ['cut','d-cut','建议减推',`${rec.cut.length} 本`],
];
recBox.innerHTML=cols.map(([k,cls,name,cnt])=>{
  const list=rec[k].sort((a,b)=>(b.rating.fusion||0)-(a.rating.fusion||0)).slice(0,12)
    .map(b=>{const s=b.snap||{};return `<div class="rec-item"><span class="dot"></span><span class="tt">${b.title}</span><span class="rs">${b.rating.grade||''} · 有效UV ${s.eff_uv??'—'}${b.growth_eff_uv!=null?` · ${b.growth_eff_uv>0?'+':''}${b.growth_eff_uv.toFixed(0)}%`:''}</span></div>`;}).join('');
  return `<div class="rec-col"><div class="note" style="font-weight:700;margin-bottom:8px">${name} <span style="color:#9aa0aa">${cnt}</span></div>${list||'<div class="note">无</div>'}</div>`;
}).join('');

// 口径
document.getElementById('notes').innerHTML=`
  <div>· 数据源：某阅读平台生产库（Redash）。书籍阅读聚合取自 <code>demo.book_daily</code>，书籍元数据取自 <code>demo.book_meta</code>，首页榜单取自 <code>demo.toplist_event</code>，评级取自 <code>weread-newbook-mass-reviewer</code>（历史/分类/同期三维基准融合）。</div>
  <div>· 指标口径：在读UV＝当日累计在读人数；有效在读UV＝阅读时长&gt;5分钟；有效阅读率＝有效在读UV/在读UV；人均时长＝人均阅读时长（分钟）；次留/次7留＝次1/7日留存率；新进UV/推荐值取自新书检查长表（仅自出品/S级书有值，缺失显示—）。</div>
  <div>· 涨幅＝最新日有效在读UV 相对约7天前的环比变化。评级档位：S≥77 / A≥70 / B≥45 / C≥30 / D&lt;30（融合分）。</div>
  <div>· 加推建议为规则初筛，仅供运营参考，最终以人工判断为准。</div>
`;

window.addEventListener('resize',()=>{charts.forEach(c=>c.resize());trendCh.resize();});
</script>
</body>
</html>
"""

html = HTML.replace('__DATA__', data_json)
out_path = os.path.join(OUT, '数据看板_2026.08.23.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('写出:', out_path, '大小:', round(len(html)/1024,1), 'KB')
