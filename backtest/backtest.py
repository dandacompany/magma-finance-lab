#!/usr/bin/env python3
"""분할매수 규칙 백테스트 — 조건표(초안)의 판정 순서를 그대로 구현.

규칙 5줄
  1. 하루에 한 번만 판정한다 (같은 날 두 번 실행해도 두 번 사지 않는다)
  2. 보유가 0주면 1주 산다
  3. 현재가가 평단의 (100+P)% 이상이면 전량 판다
  4. 보유가 Q주 이상이면 사지 않는다
  5. 현재가가 평단의 (100-D)% 이하면 2주, 아니면 1주 산다

사용:  python3 backtest.py --start 2018-01-01 --end 2026-08-05 -P 8 -D 3 -Q 10
"""
import argparse, json, sys
from collections import namedtuple

Bar = namedtuple("Bar", "date close")


def load_bars(path, start, end):
    rows = json.load(open(path))
    out = []
    for r in rows:
        d = r["dt"]
        iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        if start <= iso <= end:
            out.append(Bar(iso, int(r["cur_prc"])))
    out.sort(key=lambda b: b.date)
    return out


def run(bars, P, D, Q, cap_mode):
    """cap_mode: 'A' = 상한에서 무조건 청산 · 'B' = 매수만 중단하고 목표 완화"""
    qty, cost = 0, 0            # 보유 수량, 매입 원가 합
    cycles, trades = [], 0
    cyc_start, cyc_buys = None, 0

    for b in bars:
        avg = cost / qty if qty else 0

        # 2) 보유 0 → 1주 매수 (사이클 시작)
        if qty == 0:
            qty, cost = 1, b.close
            trades += 1
            cyc_start, cyc_buys = b.date, 1
            continue

        # 3) 익절 — 평단 +P%
        target = P if not (cap_mode == "B" and qty >= Q) else min(P, 3)
        if b.close >= avg * (1 + target / 100):
            profit = b.close * qty - cost
            cycles.append({"start": cyc_start, "end": b.date, "buys": cyc_buys,
                           "qty": qty, "profit": profit, "ret": profit / cost * 100})
            qty, cost, trades = 0, 0, trades + 1
            continue

        # 4) 수량 상한
        if qty >= Q:
            if cap_mode == "A":                      # 무조건 청산
                profit = b.close * qty - cost
                cycles.append({"start": cyc_start, "end": b.date, "buys": cyc_buys,
                               "qty": qty, "profit": profit, "ret": profit / cost * 100,
                               "forced": True})
                qty, cost, trades = 0, 0, trades + 1
            continue                                  # B는 매수만 중단

        # 5) 하락이면 2주, 아니면 1주
        n = 2 if b.close <= avg * (1 - D / 100) else 1
        qty += n
        cost += b.close * n
        cyc_buys += n
        trades += 1

    open_pos = {"qty": qty, "avg": cost / qty if qty else 0,
                "last": bars[-1].close if bars else 0,
                "unreal": (bars[-1].close * qty - cost) if qty else 0}
    return cycles, trades, open_pos


def benchmark(bars):
    """일괄매수 — 첫날 사서 끝까지 보유"""
    if not bars: return 0.0
    return (bars[-1].close - bars[0].close) / bars[0].close * 100


def summarize(name, bars, P, D, Q, cap_mode):
    cycles, trades, op = run(bars, P, D, Q, cap_mode)
    closed = [c for c in cycles if not c.get("forced")]
    forced = [c for c in cycles if c.get("forced")]
    total = sum(c["profit"] for c in cycles) + op["unreal"]
    invested = max((c["qty"] * 1 for c in cycles), default=0)
    days = [(c["start"], c["end"]) for c in cycles]
    avg_hold = 0
    if cycles:
        from datetime import date
        def d(s): y, m, dd = map(int, s.split("-")); return date(y, m, dd)
        avg_hold = sum((d(c["end"]) - d(c["start"])).days for c in cycles) / len(cycles)
    return {
        "name": name, "P": P, "D": D, "Q": Q, "cap": cap_mode,
        "cycles": len(cycles), "forced": len(forced), "trades": trades,
        "avg_hold_days": round(avg_hold, 1),
        "realized": sum(c["profit"] for c in cycles),
        "open_qty": op["qty"], "unrealized": round(op["unreal"]),
        "total": round(total),
        "bench_pct": round(benchmark(bars), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/kw/candles.json")
    ap.add_argument("--start", default="2014-05-16")
    ap.add_argument("--end", default="2026-08-05")
    ap.add_argument("-P", type=float, default=8)
    ap.add_argument("-D", type=float, default=3)
    ap.add_argument("-Q", type=int, default=10)
    ap.add_argument("--cap", default="B", choices=["A", "B"])
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    bars = load_bars(a.data, a.start, a.end)
    if not bars:
        print("데이터 없음", file=sys.stderr); return 1
    r = summarize(a.label or f"{a.start}~{a.end}", bars, a.P, a.D, a.Q, a.cap)
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
