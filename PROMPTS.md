# PROMPTS — 에이전트에게 보내는 메시지 모음

자산운용팀 실습에서 에이전트에게 보내는 자연어 메시지를 작업별로 모았습니다. 유닛별로 나눠 두었고, 각 항목에 누구에게 보내는지 적어 두었습니다.
코드 블록을 통째로 복사해 대화창에 붙여넣으세요. 괄호 자리만 본인 상황에 맞게 바꿉니다.

> 8.1은 키움 공식 `kwcli 1.0.0`·OS Keyring·새 Sam 세션 preflight 실측을 반영했습니다.

# 헤르메스에 증권 오픈API 연동하기 (8.1)

## 1. 자산운용팀 개소 — 원칙 세우기 (Sam)

```text
오늘부터 자산운용팀을 개소한다. 너는 개발 담당으로 파견이야.
이 팀의 원칙 세 가지를 먼저 기억해줘.
1) 모든 거래는 모의투자 연습 계좌에서만 한다
2) 주문은 어떤 경우에도 내 승인 없이 실행하지 않는다
3) 앱키와 계좌 정보는 화면에 출력하지 않는다
확인했으면 원칙 세 가지를 한 줄씩 요약해서 답해줘.
```

원칙을 먼저 문장으로 박아두는 것이 이 섹션의 안전장치입니다.
본인 업무에 쓸 때는 "돈·삭제·발송처럼 되돌리기 어려운 일"에 같은 패턴을 쓰세요.

## 2. 한도 템플릿을 수정하고 확정한다 (사람이 직접)

에이전트에게 보내는 메시지가 아닙니다. 스타터에 들어 있는 `guardrails/limits.md`를 열어 **여러분의 상황에 맞게 직접 수정하세요.**

```markdown
---
status: confirmed
updated_by: human
---

# 투자 한도

- 시드머니: 300만원 (모의)
- 1회 주문 한도: 최대 2주
- 1일 판단·주문 기안 횟수: 최대 5회
- 보유 수량 상한: 10주
- 손실 한도: -10% 도달 시 전체 중단
- 매수 금지: 장 미개장 · 예산 소진 · 보유 상한 도달
- 오류 시: 재시도하지 않는다. 보고하고 멈춘다
```

위 숫자는 모의투자용 초기값입니다. 가용 예산과 감당 가능한 손실 범위에 맞게 바꾸고, 모든 항목을 확인한 뒤에만 `status: unconfirmed`를 `status: confirmed`로 변경합니다.

자격 증명 등록보다 먼저 하는 이유가 있습니다. 외부 권한을 먼저 연결하고 안전장치를 나중에 붙이면 그건 옵션처럼 보입니다. **에이전트가 자기 한도를 정하거나 확정하게 하지 않습니다.**

## 3. 새 Sam 세션 preflight

```text
읽기 전용 환경 점검만 해줘.
1) command -v kiwoomcli
2) kiwoomcli auth status --profile 모의계좌
3) kiwoomcli doctor
자격 증명·토큰·계좌번호 원문은 출력하지 마. `command -v` 결과로 PATH 인식 여부를 적고, `auth status` 출력의 `계좌 별칭`, `모드`, `자격 증명 존재`, `자격 증명 출처`, `토큰 유효`, `지금 API 호출 가능` 값을 해석하거나 번역하지 말고 그대로 옮겨줘. 값이 모순되면 통과로 판정하지 마.
```

다섯 항목을 모두 통과한 뒤에만 조회합니다.

## 4. 연동과 첫 조회 (Sam)

```text
kiwoom-broker 스킬과 키움 공식 CLI의 `모의계좌` 프로필을 사용해서

1) KODEX 200(069500)의 종목 정보를 조회하고
2) 모의투자 계좌 잔고를 조회해서 보여줘.

접근토큰·앱키·시크릿·계좌번호 값은 출력하지 마. 주문은 오늘 하지 않는다.
```

마지막 두 문장이 핵심입니다. **비노출**과 **범위 제한**(오늘은 조회까지)을
요청 문장에 함께 넣는 패턴은 어떤 API 연동에든 그대로 옮겨 쓸 수 있습니다.

> 💡 잔고에 "모의투자 해당조회내역이 없습니다"가 나오면 **정상**입니다.
> 오류가 아니라 아직 아무것도 사지 않았다는 뜻입니다.

## 5. 역할과 실행 경계 (개념 — 8.4에서 실제로 씀)

Keyring은 OS 사용자 단위라서 같은 사용자의 Ada와 Sam을 물리적으로 격리하는 보안 경계가 아닙니다. 이 프로젝트에서는 `kiwoom-broker` 스킬을 Sam에게 맡기고, Ada는 판단 파일만 작성하며, 주문은 `OrderIntent → ApprovalRecord → --confirm`을 통과하게 해 역할을 나눉니다. 실계좌라면 별도 OS 사용자·컨테이너·실행 정책이 필요합니다.

---

# 투자 DB 설계와 수집 (8.2)

실행 순서는 **0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8**입니다. 먼저 8.1의 주문
프로젝트가 현재 경로에 있는지 확인하고, 분석 도구 설치가 끝나면 같은 경로에서 세
프로필을 시작해 데이터베이스·카드를 차례로 구성합니다.
같은 Sam 카드에서 수집 범위를 확인·승인하고, 품질 검증이 끝난 뒤 Supabase 적재
범위를 승인합니다.

## 0. 주문 프로젝트 재료 점검 (Ada)

8.1에서 만든 주문 프로젝트 폴더에서 세션을 시작합니다.

```bash
cd "$HOME/.hermes/workspace/magma-finance-lab"
```

Sam·Oliver·Ada 세션은 모두 이 폴더에서 시작합니다. 오늘 쓸 재료가 제자리에
있는지는 터미널 대신 Ada에게 자연어로 확인을 맡깁니다.

```text
오늘 작업에 필요한 재료가 이 폴더에 있는지 확인해서 보고해줘.
장기 일봉을 수집할 스크립트, Supabase core 마이그레이션 SQL,
setup이 남긴 vibe-finance-kit 설치 증거 파일 세 가지야.
설치 증거에서는 doctor 결과와 고정 샘플 검증 결과만 요약해줘.
비밀값은 출력하지 마.
```

칸반을 실행하기 전에는 활성 보드, 잔존 카드, Sam Gateway heartbeat, 세 프로필
인증 상태도 확인합니다.

## 1. Skill과 MCP 경계 확인 (Ada·Oliver)

```text
vibe-finance-kit의 finance_kit_doctor를 실제로 호출해줘.
read_only, order_tools, broker_credentials_required만 보여줘.
```

Vibe Finance Kit을 처음 설치할 때는 macOS, Linux·WSL, Windows PowerShell에서 같은
명령을 사용합니다.

```text
cd "$HOME/.hermes/workspace"
git clone https://github.com/dandacompany/vibe-finance-kit.git
cd vibe-finance-kit
uv run python scripts/setup_hermes.py
```

마지막 명령이 프로젝트 환경, Ada Skill 3개, Oliver Skill 2개, Ada MCP를 한 번에
설정합니다. MCP 도구 4개 활성화 질문이 나오면 `Y`를 입력합니다.

Oliver의 새 세션에서는 공개자료 조사 Skill 두 개가 보이고 주문·브로커·계좌 도구가 없는지 확인합니다.

Ada 새 세션에서 고정 샘플을 먼저 검증합니다.

```text
$HOME/.hermes/workspace/vibe-finance-kit/examples/etf-analysis-snapshot.json을 읽고
Vibe Finance Kit의 읽기 전용 도구로 검증해줘.
valid, errors, warnings, order_eligible만 보고하고 파일은 수정하지 마.
```

설치 증거 파일 `artifacts/setup/setup-receipt-vibe-finance-kit.json`은 setup의
마지막 단계가 자동으로 작성합니다. 별도로 만들 필요 없이 0번 재료 점검에서 doctor
결과와 고정 샘플 검증 결과를 요약해 확인합니다. 키·토큰·계좌번호는 기록되지 않습니다.

## 2. 데이터 계약 검토 (Ada)

```text
이 저장소의 contracts/와 다음 두 파일을 읽어줘.
- supabase/migrations/20260806090000_finance_core.sql
- supabase/migrations/20260806091000_finance_analysis_contract.sql

라이브 데이터베이스에는 적용하지 말고 다음만 표로 검토해줘.
1) 종목코드가 A 접두 없는 6자리로 제한되는지
2) 일봉 중복을 어떤 키로 막는지
3) as_of와 available_at이 구분되는지
4) 결측을 null과 warnings로 보존하는지
5) Data API grant와 RLS가 각각 어떻게 제한되는지
```

Ada의 Supabase MCP로 현재 연결된 프로젝트 이름과 project ref, `finance` 스키마의
테이블 목록과 RLS 상태를 조회합니다. 비밀값은 출력하지 않습니다. 핵심 4개 테이블이
없으면 `finance_core.sql`의 생성 객체와 권한 변경만 먼저 보고하게 합니다.

```text
현재 연결된 Supabase 프로젝트의 이름과 project ref를 확인하고
finance 스키마에 symbols, daily_prices, positions, orders가 있는지 조회해줘.
각 테이블의 RLS 상태도 확인하되 아직 변경하지 마.

핵심 4개 테이블이 없으면 supabase 마이그레이션 폴더에서
finance core 마이그레이션 SQL을 찾아 읽고
생성할 스키마·테이블·인덱스와 권한 변경을 먼저 보고해줘.
분석 계약 파일은 이번 적용에서 제외해.
```

대상 project ref와 생성 객체를 확인한 뒤에만 다음 요청으로 core SQL 실행을 승인합니다.

```text
확인한 project ref에 finance core SQL만 실행해줘.
완료 후 핵심 4개 테이블과 RLS 활성 상태를 다시 조회해줘.
분석 계약 SQL과 Data API grant는 적용하지 마.
```

## 3. Sam 수집 카드에 넣을 장기 일봉 요청

아래 요청은 5절에서 만드는 Sam 수집 카드의 본문입니다. 같은 요청을 별도 세션과
칸반 카드에서 각각 실행하지 않습니다. 두 ETF의 수정주가 확정 일봉을 각각 최대
3,000개 수집하며, 당일 봉은 제외하고 공통 거래일이 2,500개 미만이면 성공 처리하지 않습니다.

```text
작업 폴더를 ~/.hermes/workspace/magma-finance-lab으로 고정하고
그 안의 scripts/backfill_prices.py를 사용해서
KODEX 200과 TIGER 200의 수정주가 확정 일봉을 수집할 준비를 해줘.

아직 실행하지 말고 사용할 모의계좌 프로필, 종목코드 두 개,
종목별 최대 페이지와 최대 일봉 수, 최소 공통 거래일 수,
생성될 파일과 저장 경로, 키움 API 호출 간격을 먼저 보고해줘.
주문 도구는 사용하지 말고 비밀값과 계좌번호는 출력하지 마.
```

5절에서 만든 카드가 이 범위를 보고하면, 같은 카드에서 다음처럼 승인합니다.

```text
보고한 범위로 수집을 진행해줘.
```

출력의 `gate_passed=true`, 두 종목의 `adjusted=true`, `common_bars`와
`common_start`·`common_end`를 확인합니다. 생성된 원천 스냅샷과 SQL은
`artifacts/market/`에만 남고 Git에는 포함되지 않습니다.

## 4. Supabase에 멱등 적재하고 검산하기 (Ada)

Sam 수집 카드와 Ada 품질 검증이 끝난 뒤 진행합니다.

```text
artifacts/market/price-history-coverage.json과 같은 폴더의
supabase-upsert-*.sql 파일을 검토해줘.

아직 실행하지 말고 파일 수, 대상 스키마와 테이블, 종목별 예상 행 수,
ON CONFLICT 키, 공통 거래일 수, 발견한 오류를 먼저 보고해줘.
finance 이외의 스키마는 검토 대상에서 제외하고 비밀값은 출력하지 마.
```

대상과 행 수를 확인한 뒤에만 다음 요청을 입력합니다.

```text
검토한 범위로 Supabase 적재를 진행해줘.
적재 뒤 069500과 102110 각각의 행 수·최소일·최대일·adjusted 값과
두 종목의 공통 거래일 수·시작일·종료일을 확인해줘.
중복 키, 비정상적인 시가·고가·저가·종가, 오늘 이후 거래일이
하나라도 있으면 성공 처리하지 마. 비밀값과 접속 문자열은 출력하지 마.
```

2,500개는 모든 투자 연구에 통용되는 절대 기준이 아닙니다. 이 실습의 일봉
분할매수 전략에서 약 10년을 확보해 보정 구간과 평가 구간을 시간순으로 나누고,
서로 다른 시장 국면을 포함시키기 위한 최소 게이트입니다.

## 5. 실제 수집 카드 만들기 (Sam·Oliver)

```text
현재 활성 보드와 남아 있는 카드를 먼저 보여줘.
이번 8.2 실행에 사용할 새 보드를 만든 뒤 실제 수집 카드 두 장을 만들어줘.
아직 실행하지는 마.

- Sam: KODEX 200(069500)과 TIGER 200(102110)의 수정주가 확정 장기 일봉을 함께 수집하고 공통기간 계산
- Oliver: 두 ETF의 운용사·거래소 공개자료와 기준일 조사

Sam 카드에는 3절의 실행 전 보고 조건을 본문으로 넣는다. 키움 모의계좌의 공식 CLI를 사용하고 당일 미확정봉을 제외한다.
키움 API 호출은 순차 실행하고 초당 1건을 넘기지 않는다.
Oliver 카드는 공개자료의 URL과 기준일을 함께 남기고 결과를
artifacts/research/etf-product-sources.json에 저장한다.
두 카드의 작업 폴더는 ~/.hermes/workspace/magma-finance-lab으로 고정한다.
두 카드 모두 주문 도구를 호출하지 않고 비밀값과 계좌번호를 출력하지 않는다.
```

보드에 표시된 실제 카드 ID와 의존성을 확인합니다. 3절의 확인·승인 요청은 여기서 만든
Sam 카드에 이어서 입력하며, 같은 수집 카드를 다시 만들지 않습니다.

카드 실행 전 Sam Gateway heartbeat와 세 프로필 인증을 확인합니다. Sam·Oliver 카드를
`ready`로 전환하고 dispatch한 뒤 실제 상태가 `in_progress`로 바뀌는지 확인합니다.

### 5-1. 별도의 실패 격리 연습

```text
실제 수집 카드와 의존성을 공유하지 않는 연습용 카드를 하나 만들어줘.
잘못된 종목코드 000000을 키움 모의계좌에서 조회하고,
실패하면 원인과 필요한 다음 입력을 기록한 뒤 blocked로 남겨줘.
이 카드를 실제 ETF 수집이나 Ada 품질 카드의 선행 조건에 연결하지 마.
```

실패 연습 카드가 막혀도 실제 수집 카드와 품질 검증이 계속되는지 확인합니다.

선행 카드 완료만 기다리는 상황은 `dependency`입니다. 반면 미확정봉처럼
사람의 교정 입력이 필요한 실패는 `needs_input`, 필요한 조회 기능이나 자격 증명이
없는 실패는 `capability`로 분류해야 카드가 `blocked`에 남습니다.

## 6. 품질 게이트 연결 (Ada)

```text
앞의 실제 수집 카드 두 장이 모두 끝난 뒤에만 시작하는 품질 검증 카드를 만들어줘.
작업 폴더는 ~/.hermes/workspace/magma-finance-lab으로 고정하고,
Sam의 artifacts/market/ 결과와 Oliver의 artifacts/research/etf-product-sources.json을
입력 절대경로로 기록해.
별도의 000000 실패 연습 카드는 의존성에 포함하지 마.
검증 항목은 종목코드 정규화, 중복 거래일, 시가·고가·저가·종가 범위, 확정봉 여부,
as_of와 available_at, source와 warnings다.
선행 카드 중 하나가 완료되지 않으면 품질 검증을 성공 처리하지 마.
```

검증 fixture는 계약 형식과 실패 분류를 연습하기 위한 자료입니다.
장기 백테스트에는 이 fixture가 아니라 앞에서 수집한 공통 장기 일봉을 사용합니다.

## 7. 이번 실행의 분석 스냅샷 생성·검증 (Ada)

먼저 이번에 수집한 가격과 Oliver의 조사 결과로 새 분석 JSON을 만듭니다.

```text
이번에 수집한 KODEX 200 MarketSnapshot과
artifacts/research/etf-product-sources.json을 사용해서
ETFAnalysisSnapshot 계약에 맞는 JSON을 만들어줘.

가격 신호는 이번 확정 일봉에서 계산하고, 상품 품질과 기초지수 가치지표는
Oliver가 확인한 출처와 기준일만 사용해. 같은 기준일에 확보하지 못한 값은 null로 두고
missing_fields와 warnings에 사유를 남겨줘. 주문 가능 여부는 false로 유지하고
상위 폴더가 없으면 만든 뒤
artifacts/analysis/etf-analysis-snapshot-069500.json에 저장해줘.
비밀값과 계좌번호는 출력하지 마.
```

새 파일의 입력 출처와 기준 시각을 확인한 뒤 읽기 전용 도구로 검증합니다.

```text
artifacts/analysis/etf-analysis-snapshot-069500.json이 ETFAnalysisSnapshot 계약을 통과하는지
읽기 전용 도구로 검증해줘.
valid, errors, warnings, order_eligible을 그대로 보고하고,
null인 가치지표를 추정해서 채우지 마.
```

로컬에서도 같은 content hash를 확인할 수 있습니다.

```bash
python3 scripts/validate_artifact.py artifacts/analysis/etf-analysis-snapshot-069500.json
```

`examples/etf-analysis-snapshot.json`은 계약 확인용 예시입니다. 이번 실행 파일을 만들지
못했을 때 예시를 새 산출물처럼 말하지 않습니다.

현재 가치지표 스냅샷을 과거 시점의 매매 신호로 사용하지 않습니다. 과거 발표
시점이 확인된 가치지표 시계열이 없기 때문입니다. 8.3에서는 장기 가격 이력으로
규칙을 검증하고, 이 스냅샷은 상품 구조와 결과의 한계를 설명하는 근거로 사용합니다.

## 8. 매일 확정봉 수집 예약 (Sam)

먼저 Sam Gateway heartbeat가 정상인지 확인합니다. stale이면 cron을 만들지 않고
Gateway를 복구한 뒤 다시 확인합니다.

```text
평일 한국시간 18시 30분에 069500과 102110의 직전 확정 일봉을 수집하는
Hermes cron을 만들어줘. Sam의 종목별 확정봉 수집이 끝나면 Ada의 가격 품질 검증
카드를 실행하도록 해. Oliver의 ETF 상품 구조와 가치지표 조사는 매일 반복하지 않고
공식 자료 변경 확인 또는 별도 주기로 운영한다. 주문은 만들거나 실행하지 않는다.
작업 폴더는 ~/.hermes/workspace/magma-finance-lab으로 고정해.
등록 뒤 cron ID, 일정, 다음 실행 시각, profile, workdir만 보여주고 비밀값은 출력하지 마.
```

지속 운영하지 않을 경우에는 생성된 cron ID와 종목코드를 확인한 뒤 작업을 제거하고,
목록에서 사라졌는지 확인합니다.

# 분할매수 규칙 백테스트하기 (8.3)

```bash
python3 backtest/backtest.py \
  --data artifacts/market/market-snapshot-069500.json \
  --start 2014-05-19 \
  --end 2020-12-30 \
  -P 8 -D 3 -Q 10 --cap B
```

백테스트는 `t`일 확정 종가로 판단하고 `t+1`일 시가에 체결합니다. 전략과
일괄매수는 같은 초기자금·기간·비용 모형을 사용합니다. 뒤의 평가 구간 결과를
본 뒤 보정 구간의 파라미터를 다시 고르지 않습니다.

# 결정론적 자동 집행 (8.4)

> 실습 확정 후 추가됩니다.

# 투자위원회 (8.5)

> 실습 확정 후 추가됩니다.
