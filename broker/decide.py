#!/usr/bin/env python3
"""오늘의 판단 — 조건표 판정 순서를 그대로 따른다.

주문을 내지 않는다. 판단만 하고 그 결과를 판단 파일로 남긴다.
집행은 사람 승인 후 별도 단계에서.

  0. 오늘 이미 판정한 기록이 있으면 아무것도 하지 않는다   ← 중복 집행 방지
  1. 장이 열리지 않았으면 아무것도 하지 않는다
  2. 보유 0주면 1주 매수
  3. 현재가 >= 평단 * 1.08 이면 전량 매도
  4. 보유 >= 10주면 매수하지 않는다
  5. 현재가 <= 평단 * 0.97 이면 2주, 아니면 1주 매수

판정 0번은 DB가 아니라 저장소 안의 판단 파일(state/decisions/<날짜>.json)로 막는다.
안전장치를 코드 안에 두기 위해서다. DB 기록은 이 판단 파일을 근거로 별도 단계에서 남긴다.
"""
import argparse, json, os, subprocess, sys
from datetime import date

P_TARGET, D_TRIGGER, Q_MAX = 8.0, 3.0, 10
SYMBOL = "069500"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(REPO, "state", "decisions")


def kiwoom(api_id, path, body):
    here = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, os.path.join(here, "kiwoom.py"), "call", api_id, path, json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print("API 오류: " + r.stderr.strip()[:200], file=sys.stderr)
        sys.exit(1)
    text = r.stdout.strip()
    brace = text.find("{")          # 앞에 HTTP 상태 줄이 붙어 나와도 JSON만 취한다
    if brace < 0:
        print("API 응답에 JSON이 없습니다: " + text[:200], file=sys.stderr)
        sys.exit(1)
    return json.loads(text[brace:])


def latest_bars():
    d = kiwoom("ka10081", "/api/dostk/chart",
               {"stk_cd": SYMBOL, "base_dt": date.today().strftime("%Y%m%d"), "upd_stkpc_tp": "1"})
    return d.get("stk_dt_pole_chart_qry") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="판단 파일을 남기지 않고 판단만 출력")
    ap.add_argument("--state-dir", default=STATE_DIR, help="판단 파일을 둘 폴더")
    a = ap.parse_args()

    today = date.today().isoformat()
    state_path = os.path.join(a.state_dir, today + ".json")

    # 0) 중복 판정 방지 — 오늘 판단 파일이 있으면 아무것도 하지 않는다
    if os.path.exists(state_path):
        prev = json.load(open(state_path, encoding="utf-8"))
        print(json.dumps({"decision": "skip", "reason": "오늘 이미 판정함",
                          "recorded_at": prev.get("decided_at"),
                          "previous": prev.get("decision")}, ensure_ascii=False))
        return 0

    # 1) 장 개장
    bars = latest_bars()
    if not bars or bars[0]["dt"] != date.today().strftime("%Y%m%d"):
        print(json.dumps({"decision": "skip", "reason": "장 미개장 또는 아직 시세 없음"},
                         ensure_ascii=False))
        return 0

    acnt = kiwoom("kt00018", "/api/dostk/acnt", {"qry_tp": "1", "dmst_stex_tp": "KRX"})
    held = [x for x in (acnt.get("acnt_evlt_remn_indv_tot") or [])
            if x.get("stk_cd", "").lstrip("A") == SYMBOL]
    qty = int(held[0]["rmnd_qty"]) if held else 0
    avg = float(held[0]["pur_pric"]) if held else 0.0
    price = int(bars[0]["cur_prc"])

    # 2~5) 판정 — 위에서 아래로, 처음 걸리는 하나만
    if qty == 0:
        side, n_qty, why = "BUY", 1, "보유 0주 — 사이클 시작"
    elif price >= avg * (1 + P_TARGET / 100):
        side, n_qty, why = "SELL", qty, "평단 %(a),.0f 의 +%(p)s%% 도달 — 전량 매도" % {"a": avg, "p": P_TARGET}
    elif qty >= Q_MAX:
        side, n_qty, why = None, 0, "보유 %d주 — 상한 도달, 매수 중단" % qty
    elif price <= avg * (1 - D_TRIGGER / 100):
        side, n_qty, why = "BUY", 2, "평단 대비 -%s%% 이하 — 2주 매수" % D_TRIGGER
    else:
        side, n_qty, why = "BUY", 1, "평단 위 — 1주 매수"

    out = {"date": today, "symbol": SYMBOL, "price": price, "held_qty": qty,
           "avg_price": round(avg), "decision": side or "hold", "quantity": n_qty,
           "rationale": why}

    if not a.dry_run:
        from datetime import datetime
        out["decided_at"] = datetime.now().isoformat(timespec="seconds")
        os.makedirs(a.state_dir, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        out["state_file"] = state_path
        if side:
            out["status"] = "drafted — 사람 승인 대기"

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
