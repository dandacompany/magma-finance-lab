#!/usr/bin/env python3
"""오늘의 판단 — 조건표 판정 순서를 그대로 따른다.

주문을 내지 않는다. 판단만 하고 그 결과를 판단 파일로 남긴다.
집행은 사람 승인 후 별도 단계에서.

  0. 오늘 판단·주문 기안이 이미 있으면 아무것도 하지 않는다
  1. 장이 열리지 않았으면 아무것도 하지 않는다
  2. 보유 0주면 1주 매수
  3. 현재가 >= 평단 * 1.08 이면 전량 매도
  4. 보유 >= 10주면 매수하지 않는다
  5. 현재가 <= 평단 * 0.97 이면 2주, 아니면 1주 매수

판정 0번은 DB가 아니라 저장소 안의 판단 파일(state/decisions/<날짜>.json)로 막는다.
하루 한 번만 판정하므로, 같은 날 다시 실행하면 그 파일을 보고 아무것도 하지 않는다.
DB 기록은 이 판단 파일을 근거로 별도 단계에서 남긴다.
"""
import argparse, json, os, shutil, subprocess, sys
from datetime import date

P_TARGET, D_TRIGGER, Q_MAX = 8.0, 3.0, 10
DAILY_DRAFT_MAX = 1
SYMBOL = "069500"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(REPO, "state", "decisions")


def load_daily_decisions(state_path):
    """이전 단일 판단 파일과 새 누적 형식을 모두 읽는다."""
    if not os.path.exists(state_path):
        return []
    with open(state_path, encoding="utf-8") as f:
        saved = json.load(f)
    if isinstance(saved, dict) and isinstance(saved.get("decisions"), list):
        return saved["decisions"]
    return [saved] if isinstance(saved, dict) else []


def judge(qty, avg, price):
    """조건표 2~6번 — 위에서 아래로, 처음 걸리는 하나만. (매매방향, 수량, 근거)를 돌려준다."""
    if qty == 0:
        return "BUY", 1, "보유 0주 — 사이클 시작"
    if price >= avg * (1 + P_TARGET / 100):
        return "SELL", qty, "평단 {:,.0f} 의 +{:g}% 도달 — 전량 매도".format(avg, P_TARGET)
    if qty >= Q_MAX:
        return None, 0, "보유 %d주 — 상한 도달, 매수 중단" % qty
    floor = 100 - D_TRIGGER          # 추가매수 발동선 — 평단의 몇 %인가
    if price <= avg * (1 - D_TRIGGER / 100):
        return "BUY", 2, "평단의 %g%% 이하 — 최대 2주 매수" % floor
    return "BUY", 1, "평단의 %g%% 초과 — 기본 1주 매수" % floor


def kiwoomcli(args, profile):
    executable = shutil.which("kiwoomcli")
    if executable is None:
        fallback = os.path.expanduser("~/.local/bin/kiwoomcli")
        executable = fallback if os.access(fallback, os.X_OK) else None
    if executable is None:
        print("kiwoomcli를 찾지 못했습니다. uv tool install kwcli 후 새 세션에서 다시 실행하세요.", file=sys.stderr)
        sys.exit(1)

    cmd = [executable, *args, "--profile", profile, "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print("공식 CLI 오류: " + r.stderr.strip()[:200], file=sys.stderr)
        sys.exit(1)
    text = r.stdout.strip()
    brace = text.find("{")          # 앞에 HTTP 상태 줄이 붙어 나와도 JSON만 취한다
    if brace < 0:
        print("API 응답에 JSON이 없습니다: " + text[:200], file=sys.stderr)
        sys.exit(1)
    return json.loads(text[brace:])


def latest_bars(profile):
    d = kiwoomcli(
        ["domestic", "candles", "daily", "--code", SYMBOL, "--date", date.today().strftime("%Y%m%d")],
        profile,
    )
    return d.get("stk_dt_pole_chart_qry") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="판단 파일을 남기지 않고 판단만 출력")
    ap.add_argument("--state-dir", default=STATE_DIR, help="판단 파일을 둘 폴더")
    ap.add_argument("--profile", default="모의계좌", help="kiwoomcli 계좌 별칭")
    a = ap.parse_args()

    today = date.today().isoformat()
    state_path = os.path.join(a.state_dir, today + ".json")

    # 0) 하루 한 번만 판정한다. 오늘 판정 기록이 있으면 아무것도 하지 않는다
    daily_decisions = load_daily_decisions(state_path)
    if len(daily_decisions) >= DAILY_DRAFT_MAX:
        first = daily_decisions[0]
        print(json.dumps({"decision": "skip", "reason": "오늘 이미 판정함",
                          "already_decided_at": first.get("decided_at"),
                          "already_decision": first.get("decision"),
                          "already_quantity": first.get("quantity"),
                          "daily_count": len(daily_decisions),
                          "daily_limit": DAILY_DRAFT_MAX,
                          "state_file": state_path}, ensure_ascii=False))
        return 0

    # 1) 장 개장
    bars = latest_bars(a.profile)
    if not bars or bars[0]["dt"] != date.today().strftime("%Y%m%d"):
        print(json.dumps({"decision": "skip", "reason": "장 미개장 또는 아직 시세 없음"},
                         ensure_ascii=False))
        return 0

    acnt = kiwoomcli(
        ["domestic", "accounts", "holdings", "--basis", "total", "--exchange", "KRX"],
        a.profile,
    )
    held = [x for x in (acnt.get("acnt_evlt_remn_indv_tot") or [])
            if x.get("stk_cd", "").lstrip("A") == SYMBOL]
    qty = int(held[0]["rmnd_qty"]) if held else 0
    avg = float(held[0]["pur_pric"]) if held else 0.0
    price = int(bars[0]["cur_prc"])

    # 2~6) 판정 — 위에서 아래로, 처음 걸리는 하나만
    side, n_qty, why = judge(qty, avg, price)

    out = {"date": today, "symbol": SYMBOL, "price": price, "held_qty": qty,
           "avg_price": round(avg), "decision": side or "hold", "quantity": n_qty,
           "rationale": why}

    if not a.dry_run:
        from datetime import datetime
        out["decided_at"] = datetime.now().isoformat(timespec="seconds")
        daily_decisions.append(dict(out))
        out["daily_count"] = len(daily_decisions)
        out["daily_limit"] = DAILY_DRAFT_MAX
        os.makedirs(a.state_dir, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({**out, "decisions": daily_decisions}, f, ensure_ascii=False, indent=2)
        out["state_file"] = state_path
        if side:
            out["status"] = "drafted — 사람 승인 대기"

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
