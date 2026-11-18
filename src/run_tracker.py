#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新书追踪批量驱动器（固化版）

背景：<新书追踪技能> 的 fetch.py 经 wink 网关拉数，偶发「静默挂起」
（单本卡 25-28 分钟无输出，与 504 / nginx 错误页同属网关瞬时抖动）。
特征：同一 bid 重跑即秒成功。因此本脚本对每本做「超时即重试」。

用法:
    python3 run_tracker.py <bid1> <bid2> ...
    python3 run_tracker.py --timeout 180 --retries 2 3300228157 ...

约定（用户 2026-08-31 明确）:
    - 只跑 Step1 check_coverage + Step2 fetch
    - 绝不跑 build.py，不生成任何 HTML
    - fetch.py 只传 bid 一个参数，不传输出目录（否则 raw.json 平铺互相覆盖）
    - 不要用 run.sh（会连带生成 HTML）
"""
import subprocess
import sys
import time
import os

PY = "<本机Python路径>/python3"
SKILL = "<技能目录>/<新书追踪技能>/scripts"
CWD = "<工作目录>/weread_dashboard"


def run_one(cmd, timeout):
    """跑一条命令，超时返回 TIMEOUT，否则返回 (rc, output)。"""
    try:
        p = subprocess.run(
            cmd,
            cwd=CWD,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""
    except Exception as e:
        return "ERR", str(e)


def main():
    args = sys.argv[1:]
    timeout = 180
    retries = 2
    bids = []
    i = 0
    while i < len(args):
        if args[i] == "--timeout":
            timeout = int(args[i + 1]); i += 2
        elif args[i] == "--retries":
            retries = int(args[i + 1]); i += 2
        else:
            bids.append(args[i]); i += 1

    print("[tracker] 待追踪 %d 本, timeout=%ss, retries=%d" % (len(bids), timeout, retries))
    ok, fail = [], []
    t0 = time.time()

    for n, bid in enumerate(bids, 1):
        print("\n===== [%d/%d] bid=%s =====" % (n, len(bids), bid), flush=True)

        # Step 1: check_coverage
        rc, out = run_one([PY, os.path.join(SKILL, "check_coverage.py"), bid], 120)
        cov_line = ""
        for line in out.splitlines():
            if line.strip():
                cov_line = line.strip()
        print("[coverage] %s | %s" % (rc, cov_line[:160]), flush=True)

        # Step 2: fetch（超时/失败重试）
        attempt = 0
        while attempt <= retries:
            attempt += 1
            rc, out = run_one([PY, os.path.join(SKILL, "fetch.py"), bid], timeout)
            tail = [l.strip() for l in out.splitlines() if l.strip()]
            tail = tail[-2:] if tail else []
            if rc == 0:
                print("[fetch] OK (attempt %d) | %s" % (attempt, " || ".join(tail)[:200]), flush=True)
                ok.append(bid)
                break
            else:
                print("[fetch] %s (attempt %d/%d) | %s"
                      % (rc, attempt, retries + 1, " || ".join(tail)[:200]), flush=True)
                if attempt > retries:
                    fail.append((bid, rc))
                else:
                    time.sleep(3)

    print("\n========== 汇总 ==========")
    print("成功 %d / %d: %s" % (len(ok), len(bids), " ".join(ok)))
    if fail:
        print("失败 %d: %s" % (len(fail), fail))
    print("总耗时 %.0f 秒" % (time.time() - t0))


if __name__ == "__main__":
    main()
