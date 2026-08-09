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
- Vibe Finance Kit — 공개 `main`을 설치하고 `doctor`와 고정 샘플로 정상 동작 확인

## 처음 5분 체크리스트

1. 공개 스타터 저장소를 정해진 위치로 clone 합니다.
   ```bash
   git clone https://github.com/dandacompany/magma-finance-lab.git ~/.hermes/workspace/magma-finance-lab
   cd ~/.hermes/workspace/magma-finance-lab && pwd
   git remote remove origin
   git remote -v
   ```
2. `git remote -v`가 아무것도 출력하지 않는지 확인합니다. 이 프로젝트는 GitHub에 push하지 않고 로컬에서만 버전을 관리합니다.
3. 같은 호스트·OS 사용자의 대화형 터미널에서 `kiwoomcli setup`을 실행합니다. 서버는 `demo`, 별칭은 `모의계좌`로 설정하고 OS Keyring에 저장합니다.
4. 새 Sam 세션에서 `command -v kiwoomcli`, `auth status --profile 모의계좌`, `doctor`를 다시 확인합니다.
5. Sam·Oliver·Ada 세션은 모두 `~/.hermes/workspace/magma-finance-lab`에서 시작합니다.
6. `scripts/backfill_prices.py`, `contracts/`, `supabase/migrations/`가 있는지 확인합니다.
7. 8.2에서는 이번 수집 결과로 `artifacts/analysis/etf-analysis-snapshot-069500.json`을
   만든 뒤 `python3 scripts/validate_artifact.py artifacts/analysis/etf-analysis-snapshot-069500.json`으로 검증합니다.

## Vibe Finance Kit 설치

macOS, Linux·WSL, Windows PowerShell에서 같은 명령을 사용합니다.

```text
cd "$HOME/.hermes/workspace"
git clone https://github.com/dandacompany/vibe-finance-kit.git
cd vibe-finance-kit
uv run python scripts/setup_hermes.py
```

마지막 명령이 프로젝트 환경, Ada Skill 3개, Oliver Skill 2개, Ada의 읽기 전용 MCP를
설정하고 연결까지 확인합니다. `Enable all 4 tools?`가 나오면 `Y`를 입력합니다.

## 장기 일봉 수집

먼저 `PROMPTS.md`의 **5. 실제 수집 카드 만들기**로 Sam·Oliver 카드를 구성하고,
Sam 카드에는 **3. Sam 수집 카드에 넣을 장기 일봉 요청**을 입력합니다.
Sam이 모의계좌 프로필, 종목코드, 수집 범위, 출력 경로, API 호출 간격을 먼저
보고하면 내용을 확인한 뒤 실행을 승인합니다.

수집 결과의 저장 위치는 다음과 같습니다.

```text
수정주가 확정 일봉  → Supabase finance.daily_prices
ETF 분석 근거       → JSON ETFAnalysisSnapshot
운영 4테이블 SQL    → 8.2에서 검토·승인 후 적용
분석 2테이블 SQL    → 이후 유닛을 위한 로컬 검토본
```

KODEX 200과 TIGER 200의 수정주가 확정 일봉을 수집하고, 두 종목의 공통 거래일이
2,500개 이상인지 검증합니다. 당일 미확정봉은 제외하며, 실행 결과와 Supabase
멱등 적재 SQL은 `artifacts/market/`에 생성됩니다.

이 범위는 일봉 분할매수 실습의 보정·평가 구간을 나누기 위한 것입니다. 현재의
ETF 가치지표 스냅샷을 과거 매매 신호처럼 소급 적용하지 않습니다.

8.2의 데이터 비교는 KODEX 200과 TIGER 200 두 종목으로 수행합니다. 8.3 백테스트의
실행 입력은 두 종목의 공통 장기 가격 이력이고, ETF 분석 JSON은 상품 구조와 결과의
한계를 설명하는 근거입니다. 후속 주문 시연 범위는 별도 유닛의 가드레일에서 정합니다.

## 주의

- **실전 계좌를 `kiwoomcli setup`에 등록하지 마세요.** 실습은 `demo` 모의계좌만 사용합니다.
- 접속 키·토큰·계좌번호는 커밋·채팅·로그에 남기지 않습니다. 키움 자격 증명을 저장소 `.env`에 넣지 않습니다.
- 이 저장소의 전략·코드·결과는 교육용입니다. 특정 상품의 매수 권유가 아니며, 과거 데이터의 결과가 미래를 보장하지 않습니다.
- `finance_core.sql`은 대상 프로젝트와 생성 객체를 확인한 뒤에만 적용합니다. `finance_analysis_contract.sql`은 8.2에서 라이브에 적용하지 않습니다.
