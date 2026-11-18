// 验证「新书核心指标 Top 榜」表头排序（上架日期 / 上架天数）是否真的生效
// 从成品 HTML 提取真实函数体，用 DOM stub 跑，不做语法层面的假验证
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');

// ---- 提取 renderNewbookTopChart 函数体（括号扫描，严格匹配栈顶）----
function extractFn(src, name) {
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('未找到函数 ' + name);
  const open = src.indexOf('{', i);
  const stack = [];
  for (let p = open; p < src.length; p++) {
    const c = src[p];
    if (c === '{' || c === '(' || c === '[') stack.push(c);
    else if (c === '}' || c === ')' || c === ']') {
      const top = stack[stack.length - 1];
      const want = c === '}' ? '{' : c === ')' ? '(' : '[';
      if (top === want) stack.pop();          // 严格匹配栈顶，注释里的孤立括号不乱 pop
    }
    if (!stack.length) return src.slice(i, p + 1);
  }
  throw new Error('函数 ' + name + ' 括号未闭合');
}
const fnSrc = extractFn(html, 'renderNewbookTopChart');
console.log('提取 renderNewbookTopChart：' + fnSrc.length + ' 字符');

// 回归断言：排序键不得被下拉框值无条件覆盖
// 注意：必须先剥离注释再检测，否则会匹配到说明文字里的同名字符串
const fnNoComment = fnSrc.split('\n').map(l => l.replace(/\/\/.*$/, '')).join('\n');
if (/newbookSortKey\s*=\s*metric\s*;/.test(fnNoComment)) {
  console.log('✗ 失败：仍存在 newbookSortKey = metric 无条件覆盖');
  process.exit(1);
}
console.log('✓ 无 newbookSortKey = metric 覆盖');

// ---- 表头点击处理器：从 HTML 中提取绑定逻辑 ----
const clickIdx = html.indexOf("document.querySelectorAll('#newbookTopTable thead th[data-nbtsort]')");
if (clickIdx < 0) throw new Error('未找到表头点击绑定');
// 必须用括号栈扫描：处理器内部含 addEventListener 的 `});`，用 indexOf('});') 会提前截断
let clickSrc;
{
  const open = html.indexOf('{', clickIdx);
  const stack = [];
  for (let p = open; p < html.length; p++) {
    const c = html[p];
    if (c === '{' || c === '(' || c === '[') stack.push(c);
    else if (c === '}' || c === ')' || c === ']') {
      const top = stack[stack.length - 1];
      const want = c === '}' ? '{' : c === ')' ? '(' : '[';
      if (top === want) stack.pop();
    }
    if (!stack.length) {
      // 栈空停在收尾的 '}'，后面还有 ');' 要带上，否则 eval 报 missing )
      let q = p + 1;
      while (q < html.length && html[q] !== ';') q++;
      clickSrc = html.slice(clickIdx, q + 1);
      break;
    }
  }
}
if (!clickSrc) throw new Error('表头点击处理器括号未闭合');
console.log('提取表头点击处理器：' + clickSrc.length + ' 字符');

// ---- mock 数据：5 本近 14 天新书，上架日期与天数各不同 ----
const BOOKS = [
  { book_id: 'A', title: '甲', author: 'x', category_l1: 'c', category_l2: 'd', days_online: 1,  launch_date: '2026-09-06', metrics: { effective_reading_uv: 10, reading_uv: 20, new_reading_uv: 1, avg_reading_duration: 3, next_day_retention: 10, day7_retention: 1, effective_reading_rate: 50, recommendation_rate: 80 } },
  { book_id: 'B', title: '乙', author: 'x', category_l1: 'c', category_l2: 'd', days_online: 13, launch_date: '2026-08-25', metrics: { effective_reading_uv: 900, reading_uv: 2000, new_reading_uv: 9, avg_reading_duration: 9, next_day_retention: 40, day7_retention: 8, effective_reading_rate: 45, recommendation_rate: 95 } },
  { book_id: 'C', title: '丙', author: 'x', category_l1: 'c', category_l2: 'd', days_online: 5,  launch_date: '2026-09-02', metrics: { effective_reading_uv: 300, reading_uv: 700, new_reading_uv: 5, avg_reading_duration: 6, next_day_retention: 25, day7_retention: 4, effective_reading_rate: 42, recommendation_rate: 88 } },
  { book_id: 'D', title: '丁', author: 'x', category_l1: 'c', category_l2: 'd', days_online: 9,  launch_date: '2026-08-29', metrics: { effective_reading_uv: 500, reading_uv: 1200, new_reading_uv: 7, avg_reading_duration: 7, next_day_retention: 30, day7_retention: 5, effective_reading_rate: 41, recommendation_rate: 90 } },
  { book_id: 'E', title: '戊', author: 'x', category_l1: 'c', category_l2: 'd', days_online: 3,  launch_date: '2026-09-04', metrics: { effective_reading_uv: 100, reading_uv: 300, new_reading_uv: 3, avg_reading_duration: 5, next_day_retention: 20, day7_retention: 3, effective_reading_rate: 33, recommendation_rate: 85 } },
];

// ---- DOM stub ----
let lastRows = '';
const mkEl = (id) => ({
  id,
  innerHTML: '',
  textContent: '',
  value: 'effective_reading_uv',
  dataset: {},
  classList: { add(){}, remove(){}, contains(){return false;} },
  querySelector(sel){ const m=/option\[value="(.+?)"\]/.exec(sel); return m ? {} : null; },
  addEventListener(){},
});
const els = {
  newbookTopBody: mkEl('newbookTopBody'),
  newbookMetric: mkEl('newbookMetric'),
  newbookTopFooter: mkEl('newbookTopFooter'),
};
const HEADERS = ['launch_date','title','author','category_l1','category_l2','days_online',
  'reading_uv','effective_reading_uv','effective_reading_rate','avg_reading_duration',
  'next_day_retention','day7_retention','new_reading_uv','recommendation_rate']
  .map(k => { const e = mkEl('th_' + k); e.dataset.nbtsort = k; return e; });

global.document = {
  getElementById: (id) => els[id] || mkEl(id),
  querySelectorAll: (sel) => (sel.indexOf('thead th') >= 0 ? HEADERS : []),
};
global.getScopedData = () => BOOKS;
global.fmt = (k, v) => (v == null ? '-' : String(v));
global.chg = () => '';
global.openBookDetail = () => {};
global.escapeHtml = (s) => String(s);

// 取每行 bid：行首 onclick="openBookDetail('X')"
function rowBids() {
  return [...lastRows.matchAll(/openBookDetail\('([A-E])'\)/g)].map(m => m[1]);
}

let newbookSortKey = 'effective_reading_uv';
let newbookSortDir = 'desc';
const newbookMetricEl = els.newbookMetric;

eval(fnSrc);
// 模拟表头点击：复用 HTML 中真实的绑定逻辑（含 addEventListener 包裹，直接整块 eval）
function clickHeader(k) {
  // 必须先清空所有表头的旧绑定：eval 会遍历全部 th，
  // 上一轮设置过的 handler 若残留，会在这次被连带触发并污染 newbookSortKey
  HEADERS.forEach(h => { h.addEventListener = () => {}; });
  const th = HEADERS.find(h => h.dataset.nbtsort === k);
  th.addEventListener = (ev, cb) => { if (ev === 'click') cb(); };
  eval(clickSrc);
}

let pass = 0, fail = 0;
function check(name, got, want) {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { console.log('  ✓ ' + name + '  ' + g); pass++; }
  else { console.log('  ✗ ' + name + '  得到 ' + g + ' 期望 ' + w); fail++; }
}

console.log('\n--- 点表头「上架日期」---');
clickHeader('launch_date');
renderNewbookTopChart(); lastRows = els.newbookTopBody.innerHTML;
console.log('  newbookSortKey =', newbookSortKey, ' dir =', newbookSortDir);
check('降序（最新在前）', rowBids(), ['A','E','C','D','B']);
clickHeader('launch_date');
renderNewbookTopChart(); lastRows = els.newbookTopBody.innerHTML;
check('再点切升序（最早在前）', rowBids(), ['B','D','C','E','A']);

console.log('\n--- 点表头「上架天数」---');
clickHeader('days_online');
renderNewbookTopChart(); lastRows = els.newbookTopBody.innerHTML;
console.log('  newbookSortKey =', newbookSortKey, ' dir =', newbookSortDir);
check('升序（最新上架在前）', rowBids(), ['A','E','C','D','B']);
clickHeader('days_online');
renderNewbookTopChart(); lastRows = els.newbookTopBody.innerHTML;
check('再点切降序（最早上架在前）', rowBids(), ['B','D','C','E','A']);

console.log('\n--- 回到指标排序仍正常 ---');
clickHeader('effective_reading_uv');
renderNewbookTopChart(); lastRows = els.newbookTopBody.innerHTML;
check('按有效在读UV 降序', rowBids(), ['B','D','C','E','A']);

console.log('\n--- 下拉框切换 ---');
newbookMetricEl.value = 'launch_date'; newbookSortKey = 'launch_date'; newbookSortDir = 'desc';
renderNewbookTopChart(); lastRows = els.newbookTopBody.innerHTML;
check('下拉框选上架日期', rowBids(), ['A','E','C','D','B']);

console.log('\n共 ' + (pass + fail) + ' 项，通过 ' + pass + '，失败 ' + fail);
process.exit(fail ? 1 : 0);
