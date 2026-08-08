# magma-finance-lab

MAGMA(3040 남성 패션 브랜드)의 자산운용팀 작업 저장소입니다.
인프런 「Hermes × Codex 가상 오피스」 섹션 8(자산운용팀)이 이 저장소 위에서 진행됩니다.

데이터 분석 사업부(magma-data-lab)가 시장을 읽는 곳이라면,
이 저장소는 회사의 여유 자금이 규칙대로 굴러가는 일터입니다.

먼저 알아두실 것 두 가지.

- 이 저장소의 모든 거래 실습은 **모의투자(연습 계좌)** 에서만 진행합니다. 실제 돈이 나가는 경로가 없습니다.
- 이 저장소는 수익 내는 법이 아니라 **자동화 메커니즘을 만드는 법**을 연습하는 곳입니다.

## 구조 한눈에

```
PROMPTS.md       실습에서 에이전트에게 보내는 메시지 모음 (복사해서 사용)
broker/          공식 CLI와 하네스의 경계·주문 의도 생성기
contracts/       에이전트 사이에서 주고받는 시세·분석 JSON 계약
supabase/        검토와 승인 뒤 적용하는 데이터베이스 migration
scripts/         계약·해시·확정봉 검증 도구
examples/        검증된 입력 예시
backtest/        전략 규칙과 백테스트 스크립트·결과
guardrails/      투자 가드레일 문서 (제공된 템플릿을 사람이 수정·확정)
```

## 유닛별로 채워지는 자리

| 유닛 | 실습 | 채울 자리 | 만들어지는 것 |
| --- | --- | --- | --- |
| 8.1 | 헤르메스에 증권 오픈API 연동하기 | 공식 `kiwoomcli` + `broker/` | setup·Keyring·Sam preflight·첫 시세·잔고 조회 |
| 8.2 | Supabase에 시세 데이터베이스 만들기 | `contracts/` + `supabase/` | 시세·분석 계약·과거 시세 적재·매일 수집 예약 |
| 8.3 | 분할매수 규칙 백테스트하기 | `backtest/` | 전략 규칙과 백테스트 결과 |
| 8.4 | 크론으로 매일 자동 주문 돌리기 | `guardrails/` + `broker/` | 주문 의도·사람 승인·모의 집행·대사 기록 |
| 8.5 | 멀티에이전트 투자위원회 구성하기 | Council 산출물 | 위험 검토·투자 결정·회의 기록 |

## 준비물

- 키움증권 계좌(비대면 개설 가능) + **상시모의투자 참가신청** + **모의투자용** 앱키
- `uv` + 키움 공식 CLI: `uv tool install kwcli`
- Hermes 에이전트 (Sam·Ada·Oliver·Noah·Sophie 프로필)
- `kiwoom-broker` 스킬 — `hermes skills install dandacompany/dante-skills/kiwoom-broker`
- Vibe Finance Kit 고정 버전 `e542710` — 분석 근거 계약과 읽기 전용 검증 도구

## 처음 5분 체크리스트

1. GitHub에서 이 저장소를 Fork 하거나 Use this template으로 내 저장소를 만듭니다.
2. 내 컴퓨터의 정해진 위치로 clone 합니다.
   ```bash
   git clone (내 저장소 주소) ~/.hermes/workspace/magma-finance-lab
   cd ~/.hermes/workspace/magma-finance-lab && pwd
   ```
3. 같은 호스트·OS 사용자의 대화형 터미널에서 `kiwoomcli setup`을 실행합니다. 서버는 `demo`, 별칭은 `모의계좌`로 설정하고 OS Keyring에 저장합니다.
4. 새 Sam 세션에서 `command -v kiwoomcli`, `auth status --profile 모의계좌`, `doctor`를 다시 확인합니다.
5. 8.2에서는 `python3 scripts/validate_artifact.py examples/etf-analysis-snapshot.json`으로
   제공된 분석 계약과 content hash를 검증합니다.

## 장기 일봉 수집

```bash
python3 scripts/backfill_prices.py --profile 모의계좌 --pages 5 --minimum-common-bars 2500
```

KODEX 200과 TIGER 200의 수정주가 확정 일봉을 수집하고, 두 종목의 공통 거래일이
2,500개 이상인지 검증합니다. 당일 미확정봉은 제외하며, 실행 결과와 Supabase
멱등 적재 SQL은 `artifacts/market/`에 생성됩니다.

이 범위는 일봉 분할매수 실습의 보정·평가 구간을 나누기 위한 것입니다. 현재의
ETF 가치지표 스냅샷을 과거 매매 신호처럼 소급 적용하지 않습니다.

## 주의

- **실전 계좌를 `kiwoomcli setup`에 등록하지 마세요.** 실습은 `demo` 모의계좌만 사용합니다.
- 접속 키·토큰·계좌번호는 커밋·채팅·로그에 남기지 않습니다. 키움 자격 증명을 저장소 `.env`에 넣지 않습니다.
- 이 저장소의 전략·코드·결과는 교육용입니다. 특정 상품의 매수 권유가 아니며, 과거 데이터의 결과가 미래를 보장하지 않습니다.
- `supabase/migrations/`의 SQL은 로컬 검토본입니다. 녹화 중 라이브 데이터베이스에 적용하지 않습니다.
