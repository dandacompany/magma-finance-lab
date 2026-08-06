#!/usr/bin/env python3
"""오늘의 판단 — 조건표 판정 순서를 그대로 따른다.

주문을 내지 않는다. 판단만 하고 orders 테이블에 status='drafted' 로 기안한다.
집행은 사람 승인 후 별도 단계에서.

  0. 오늘 이미 판정한 기록이 있으면 아무것도 하지 않는다   ← 중복 집행 방지
  1. 장이 열리지 않았으면 아무것도 하지 않는다
  2. 보유 0주면 1주 매수
  3. 현재가 >= 평단 * 1.08 이면 전량 매도
  4. 보유 >= 10주면 매수하지 않는다
  5. 현재가 <= 평단 * 0.97 이면 2주, 아니면 1주 매수
"""
import argparse, json, os, subprocess, sys, urllib.request
from datetime import date

P_TARGET, D_TRIGGER, Q_MAX = 8.0, 3.0, 10
SYMBOL = "069500"


def psql(url, sql, tuples_only=True):
    cmd = ["psql", url, "-tAc" if tuples_only else "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"DB 오류: {r.stderr.strip()[:200]}", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def kiwoom(api_id, path, body):
    cmd = ["env", "-i", f"HOME={os.environ['HOME']}", "PATH=/usr/bin:/bin", "TMPDIR=/tmp",
           "python3", "/tmp/kw/kiwoom.py", "call", api_id, path, json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"API 오류: {r.stderr.strip()[:200]}", file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)


def market_open_today():
    """장 운영 캘린더로 오늘이 영업일인지 확인 (주문 전에 거른다)"""
    try:
        with urllib.request.urlopen(
            "https://openapi.tossinvest.com/api/v1/market-calendar/KR", timeout=10
        ) as _:
            pass
    except Exception:
        pass
    # 토스는 토큰이 필요하므로 여기서는 키움 일봉의 최신 일자로 갈음한다.
    d = kiwoom("ka10081", "/api/dostk/chart",
               {"stk_cd": SYMBOL, "base_dt": date.today().strftime("%Y%m%d"), "upd_stkpc_tp": "1"})
    bars = d.get("stk_dt_pole_chart_qry") or []
    return bool(bars) and bars[0]["dt"] == date.today().strftime("%Y%m%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true", help="DB 기록 없이 판단만 출력")
    a = ap.parse_args()

    today = date.today().isoformat()

    # 0) 중복 판정 방지
    n = psql(a.db, f"select count(*) from finance.orders where drafted_at::date = '{today}';")
    if int(n) > 0:
        print(json.dumps({"decision": "skip", "reason": "오늘 이미 판정함", "existing": int(n)},
                         ensure_ascii=False))
        return 0

    # 1) 장 개장
    if not market_open_today():
        print(json.dumps({"decision": "skip", "reason": "장 미개장 또는 아직 시세 없음"},
                         ensure_ascii=False))
        return 0

    # 현재 보유 (모의 계좌 실시간)
    acnt = kiwoom("kt00018", "/api/dostk/acnt", {"qry_tp": "1", "dmst_stex_tp": "KRX"})
    held = [x for x in (acnt.get("acnt_evlt_remn_indv_tot") or [])
            if x.get("stk_cd", "").lstrip("A") == SYMBOL]      # A 접두 정규화
    qty = int(held[0]["rmnd_qty"]) if held else 0
    avg = float(held[0]["pur_pric"]) if held else 0.0

    price = int(kiwoom("ka10081", "/api/dostk/chart",
                       {"stk_cd": SYMBOL, "base_dt": date.today().strftime("%Y%m%d"),
                        "upd_stkpc_tp": "1"})["stk_dt_pole_chart_qry"][0]["cur_prc"])

    # 2~5) 판정
    if qty == 0:
        side, n_qty, why = "BUY", 1, "보유 0주 — 사이클 시작"
    elif price >= avg * (1 + P_TARGET / 100):
        side, n_qty, why = "SELL", qty, f"평단 {avg:,.0f} 의 +{P_TARGET}% 도달 — 전량 매도"
    elif qty >= Q_MAX:
        side, n_qty, why = None, 0, f"보유 {qty}주 — 상한 도달, 매수 중단"
    elif price <= avg * (1 - D_TRIGGER / 100):
        side, n_qty, why = "BUY", 2, f"평단 대비 -{D_TRIGGER}% 이하 — 2주 매수"
    else:
        side, n_qty, why = "BUY", 1, "평단 위 — 1주 매수"

    out = {"date": today, "symbol": SYMBOL, "price": price, "held_qty": qty,
           "avg_price": round(avg), "decision": side or "hold", "quantity": n_qty,
           "rationale": why}

    if side and not a.dry_run:
        psql(a.db, f"""insert into finance.orders
            (symbol, side, quantity, order_type, status, rationale)
            values ('{SYMBOL}','{side}',{n_qty},'MARKET','drafted',
                    '{why.replace("'", "''")}');""")
        oid = psql(a.db, "select max(id) from finance.orders;")
        out["order_id"] = int(oid)
        out["status"] = "drafted — 사람 승인 대기"

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
