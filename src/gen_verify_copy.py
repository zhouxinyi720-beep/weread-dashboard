#!/usr/bin/env python3
"""从生成好的看板 HTML 中抽取弹窗加推文案所依赖的全局与函数，拼成可在 node 里真跑的校验脚本。

用法:
    python3 gen_verify_copy.py <html路径> <输出js路径>
"""
import re
import sys

GLOBALS = ['DATES', 'ALL_DATA', 'CHANGES', 'BENCHMARKS', 'LEADERBOARD_HITS',
           'HOTSPOTS_RAW', 'HAS_PREV', 'TIMELINE']
FUNCTIONS = ['getBenchmark', 'getStreak', 'risingTier', 'buildCopywriterPayload']


def extract_declaration(src, name, kind='const'):
    """抽取 const NAME = ...; 的完整声明（括号/引号感知，简单处理）。"""
    pat = re.compile(r'(?m)^[ \t]*' + kind + r'\s+' + re.escape(name) + r'\b')
    m = pat.search(src)
    if not m:
        pat = re.compile(kind + r'\s+' + re.escape(name) + r'\b')
        m = pat.search(src)
    if not m:
        return None
    start = m.start()
    i = src.index('=', m.end() - len(name) - 1)
    i += 1
    depth = 0
    j = i
    n = len(src)
    instr = None
    while j < n:
        c = src[j]
        if instr:
            if c == '\\':
                j += 2
                continue
            if c == instr:
                instr = None
        elif c in ('"', "'", '`'):
            instr = c
        elif c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ';' and depth == 0:
            return src[start:j + 1]
        elif c == '\n' and depth == 0:
            # 顶层换行且深度为 0，说明语句已结束
            seg = src[i:j].rstrip()
            if seg.endswith((';',)) is False and depth == 0:
                # 可能是多行数组，继续看下一行是否还是同一语句；简单起见以分号为准
                pass
        j += 1
    return src[start:n][:0] or None


def extract_function(src, name):
    """抽取 function NAME(...) {...} 的完整定义，括号扫描严格匹配栈顶。"""
    pat = re.compile(r'(?m)^[ \t]*function\s+' + re.escape(name) + r'\s*\(')
    m = pat.search(src)
    if not m:
        pat = re.compile(r'function\s+' + re.escape(name) + r'\s*\(')
        m = pat.search(src)
    if not m:
        return None
    start = m.start()
    i = src.index('{', m.end() - 1)
    stack = ['{']
    j = i + 1
    n = len(src)
    instr = None
    while j < n and stack:
        c = src[j]
        if instr:
            if c == '\\':
                j += 2
                continue
            if c == instr:
                instr = None
        elif c in ('"', "'", '`'):
            instr = c
        elif c in '([{':
            stack.append(c)
        elif c in ')]}':
            if stack and stack[-1] == mapping.get(c):
                stack.pop()
            elif c == '}':
                stack.pop()
        j += 1
    return src[start:j]


mapping = {')': '(', ']': '[', '}': '{'}


HARNESS = r"""
// ===== 运行期依赖补齐 =====
const HOTSPOTS = [];
function isHotspotFresh(){ return false; }

// ===== 校验主体 =====
const hits = LEADERBOARD_HITS || [];
const targets = hits.map(h => String(h.book_id));
const others = ALL_DATA.filter(b => b.metrics)
  .sort((a, b) => (b.metrics.effective_reading_uv || 0) - (a.metrics.effective_reading_uv || 0))
  .slice(0, 12)
  .map(b => String(b.book_id));
const ids = Array.from(new Set(targets.concat(others)));
let fail = 0, checked = 0;
for (const id of ids) {
  const b = ALL_DATA.find(x => String(x.book_id) === String(id));
  if (!b || !b.metrics) { console.log('  [SKIP]', id, 'no metrics'); continue; }
  for (let v = 0; v < 3; v++) {
    checked++;
    try {
      const r = buildCopywriterPayload(b, v);
      const risingIt = (hits.find(h => String(h.book_id) === String(id)) || {items: []})
        .items.find(it => it.section_key === '飙升榜');
      const must = risingIt ? ('飙升榜' + risingTier(risingIt.rank)) : null;
      const ok = !must || r.text.includes(must);
      if (!ok) { fail++; console.log('  [FAIL]', id, '缺少', must, '->', r.text); }
      if (v === 0) {
        console.log('---', b.title, '| 榜单:', risingIt ? ('飙升榜 rank ' + risingIt.rank + ' -> ' + risingTier(risingIt.rank)) : '无');
        console.log('    文案:', r.text);
        console.log('    登榜必注:', must ? (ok ? 'PASS' : 'FAIL') : 'N/A');
      }
    } catch (e) { fail++; console.log('  [ERROR]', id, 'v' + v, e.message); }
  }
}
console.log('\n共校验 ' + checked + ' 次调用，失败 ' + fail + ' 次');
console.log(fail === 0 ? 'OK 弹窗文案实跑校验全部通过' : 'NG 弹窗文案实跑校验存在失败');
"""


def main():
    html_path = sys.argv[1]
    out_path = sys.argv[2]
    src = open(html_path, encoding='utf-8').read()
    parts = []
    for name in GLOBALS:
        decl = extract_declaration(src, name, 'const') or extract_declaration(src, name, 'let') \
            or extract_declaration(src, name, 'var')
        if not decl:
            raise SystemExit('未找到全局声明: ' + name)
        parts.append('// ---- %s ---- (%d chars)' % (name, len(decl)))
        parts.append(decl[:20000000])
    for name in FUNCTIONS:
        fn = extract_function(src, name)
        if not fn:
            raise SystemExit('未找到函数: ' + name)
        parts.append('// ---- function %s ---- (%d chars)' % (name, len(fn)))
        parts.append(fn)
    parts.append(HARNESS)
    open(out_path, 'w', encoding='utf-8').write('\n'.join(parts))
    print('已生成', out_path)
    for name in FUNCTIONS:
        fn = extract_function(src, name)
        print('  function %s: %d chars' % (name, len(fn)))


if __name__ == '__main__':
    main()
