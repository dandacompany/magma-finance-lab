# broker/ — 증권사 API 연동

키움증권 REST API를 부르는 도구가 들어 있습니다. **모의투자가 기본**이고 실전은 명시해야만 열립니다.

| 파일 | 무엇 |
| --- | --- |
| `kiwoom.py` | 호출 래퍼. 표준 라이브러리만 쓰므로 설치할 것이 없습니다 |
| `kiwoom-api-reference.md` | 직접 호출해 확인한 TR 목록과 함정 |

## 왜 스킬이 아니라 저장소에 있나

처음에는 이걸 Hermes 스킬로 만들어 `hermes skills install` 로 받게 하려 했습니다. **그런데 설치가 막혔습니다.**

```text
Verdict: DANGEROUS
  CRITICAL exfiltration   os.environ.get("KIWOOM_REST_API_KEY")
  CRITICAL exfiltration   os.environ.get("KIWOOM_REST_API_SECRET")
Decision: BLOCKED — --force does not override a dangerous verdict.
```

**스캐너가 맞습니다.** "환경변수에서 API 키를 읽어 네트워크로 보내는 코드"는 유출 패턴 그 자체입니다. 우리 의도가 정당해도 코드만 봐서는 구분할 방법이 없습니다.

우회하는 방법은 있지만 쓰지 않습니다. 대신 **코드를 눈으로 볼 수 있는 곳에 둡니다.** 여러분이 clone한 저장소 안에, 읽을 수 있는 파이썬 파일로요.

> 💡 여기서 하나 가져가실 것 — 남이 만든 도구에 키를 넘기기 전에 **그게 키로 무엇을 하는지 볼 수 있는가**를 확인하세요. 볼 수 없으면 넘기지 마세요.

## 자격증명 넣는 법

필요한 값은 셋입니다.

```text
KIWOOM_REST_API_KEY
KIWOOM_REST_API_SECRET
KIWOOM_API_BASE_URL     # 생략 가능 — 없으면 모의투자 주소
```

찾는 순서는 이렇습니다. **위에서 하나라도 잡히면 아래는 보지 않습니다.**

| 순위 | 어디 | 언제 |
| --- | --- | --- |
| 1 | 이미 환경에 있으면 그대로 | **Hermes 프로필 `.env`** 나 Bitwarden·1Password 같은 볼트가 넣어준 경우 — 권장 |
| 2 | `KIWOOM_AUTH_ENV=/경로/.env` | 파일 위치를 직접 지정할 때 |
| 3 | `$HERMES_HOME/.env` | Hermes 프로필 홈이 잡혀 있을 때 |
| 4 | `~/.claude/auth/kiwoom-mock.env` | 개발 편의용 폴백 |

### 권장 — Hermes 프로필 `.env`

```bash
# ~/.hermes/profiles/sam/.env
KIWOOM_REST_API_KEY=...
KIWOOM_REST_API_SECRET=...
KIWOOM_API_BASE_URL=https://mockapi.kiwoom.com
```

Hermes가 프로필의 `.env`를 읽어 세션 환경에 넣어주므로, 도구는 그 값을 그대로 씁니다. `chmod 600`으로 권한을 좁히세요.

### 키를 가진 프로필을 하나로 좁힌다

이 구조의 진짜 쓸모가 여기 있습니다. **집행 담당 프로필의 `.env`에만 키를 넣으세요.**

판단 담당 프로필에는 그 값이 없으므로, 그 세션에서 도구를 부르면 이렇게 멈춥니다.

```text
ERROR: 키움 자격증명을 찾지 못했습니다.
```

**호출 자체가 시작되지 않습니다.** 권한을 안 준 일은 실수로도 못 하게 됩니다.

## 사용법

```bash
# 토큰 상태 (토큰 값은 안 보입니다)
python3 broker/kiwoom.py token --status

# ETF 종목 정보
python3 broker/kiwoom.py call ka40002 /api/dostk/etf '{"stk_cd":"069500"}'

# 일봉 차트 — 1회에 600봉까지 옵니다
python3 broker/kiwoom.py call ka10081 /api/dostk/chart \
  '{"stk_cd":"069500","base_dt":"20260806","upd_stkpc_tp":"1"}'

# 계좌 평가잔고
python3 broker/kiwoom.py call kt00018 /api/dostk/acnt '{"qry_tp":"1","dmst_stex_tp":"KRX"}'
```

`upd_stkpc_tp`는 수정주가 구분입니다(`1` = 적용). **한 프로젝트 안에서 이 값을 섞으면 평단 계산이 어긋납니다.**

## 주문 (실행 전에 반드시 읽으세요)

```bash
# 이렇게 하면 거부됩니다 — 무엇을 주문하려는지 보여주고 멈춥니다
python3 broker/kiwoom.py call kt10000 /api/dostk/ordr \
  '{"dmst_stex_tp":"KRX","stk_cd":"069500","ord_qty":"1","ord_uv":"","trde_tp":"3"}'

# 확인한 뒤에만
python3 broker/kiwoom.py call kt10000 /api/dostk/ordr '{...}' --confirm-order
```

- 수량·단가는 **문자열**로 보냅니다 (`"1"`, 숫자 1 아님)
- **주문 응답을 못 받았다고 재주문하지 마세요.** 주문 조회로 이미 나갔는지부터 확인합니다

주문 안전 설계는 `guardrails/order-safety.md`에 정리해 뒀습니다.

## 도구가 대신 해주는 것

| | 손으로 하면 | 이 도구가 하면 |
| --- | --- | --- |
| 토큰 만료 | 401 보고 당황 | 감지해서 1회 재발급 후 재시도 |
| 429 | 그냥 실패 | 1초 → 2초 → 4초 대기 후 재시도 |
| HTTP 200인데 실패 | 성공으로 착각 | `return_code`까지 검사 |
| 모의/실전 혼동 | 사고 | 프로필과 서버가 어긋나면 중단 |
| 주문 실수 | 되돌릴 수 없음 | `--confirm-order` 없이는 거부 |

접근토큰은 파일로 저장·재사용합니다(요청마다 재발급하면 발급 제한에 걸립니다). 토큰 파일은 임시 폴더에 `600` 권한으로 저장되고 저장소에는 들어가지 않습니다.

## 자주 만나는 문제

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| `8001 App Key와 Secret Key 검증에 실패` | 키 만료·해지 | 포털에서 재발급. 상시모의투자 신청 상태도 확인 |
| `프로필과 서버가 어긋납니다` | 주소가 프로필과 안 맞음 | 모의는 `mockapi.kiwoom.com` |
| `키움 자격증명을 찾지 못했습니다` | 위 네 곳 어디에도 키가 없음 | 프로필 `.env`에 넣으세요. **다른 프로필에서는 일부러 안 보이게 한 것일 수도 있습니다** |
| `모의투자 해당조회내역이 없습니다` | **정상.** 보유 0건 | 그대로 진행 |
| 조회는 되는데 필드가 전부 빈 문자열 | 종목코드 오타 | **없는 종목도 정상 응답으로 옵니다.** 코드를 확인하세요 |
| 429 반복 | 호출이 잦음 | 조회는 TR당 초당 1건이 안전합니다 |

## 공식 저장소와의 관계

키움 공식 저장소(`Kiwoom-Securities/Kiwoom-REST-API`)는 Python 런타임과 예제 362개를 제공하지만 **라이선스가 `All rights reserved`** 라 복제·재배포에 제약이 있습니다.

`kiwoom.py`는 공식 코드를 포함하지 않습니다. 공개된 API 사양(엔드포인트·TR 식별자·파라미터명)만 참조해 직접 만든 것입니다. 공식 런타임이나 CLI가 필요하면 키움 배포처에서 별도로 받으세요.
