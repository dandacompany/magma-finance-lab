# broker 경계

이 폴더는 증권사 API를 다시 구현하는 곳이 아닙니다.

- 인증·토큰·종목·잔고·주문 호출: 키움 공식 `kwcli` / `kiwoomcli`
- 자연어를 공식 CLI 명령으로 바꾸는 운영 설명서: `kiwoom-broker` Hermes 스킬
- 전략 결과를 주문 의도로 바꾸는 결정론적 하네스: `decide.py`

## 1. 설치와 setup

```bash
uv tool install kwcli
uv tool update-shell
kiwoomcli setup
```

강의 실습은 서버 `demo`, 계좌 별칭 `모의계좌`를 사용합니다. App Key·Secret은 OS Keyring에 저장하고 저장소에 `.env`로 남기지 않습니다.

setup은 Hermes가 실행될 **같은 호스트·같은 OS 사용자**에서 실행해야 합니다. `자격 증명 저장소 사용 불가`가 나오면 `.env`로 우회하지 말고 중단합니다.

## 2. 새 Sam 세션 preflight

```text
읽기 전용 환경 점검만 해줘.
1) command -v kiwoomcli
2) kiwoomcli auth status --profile 모의계좌
3) kiwoomcli doctor
자격 증명·토큰·계좌번호 값은 출력하지 말고, PATH 인식·profile·mode·자격 증명 존재·토큰 유효 여부만 보고해줘.
```

PATH, `모의계좌`, `demo`, 자격 증명, 토큰을 모두 인식한 뒤에만 조회합니다.

## 3. 공식 CLI 조회

```bash
kiwoomcli domestic etfs info --code 069500 --profile 모의계좌 --format json
kiwoomcli domestic candles daily --code 069500 --date YYYYMMDD --profile 모의계좌 --format json
kiwoomcli domestic accounts holdings --basis total --exchange KRX --profile 모의계좌 --format json
```

명령을 추정하지 말고 `kiwoomcli spec search "검색어"`와 해당 명령의 `-h`를 먼저 사용합니다.

## 4. 주문 경계

1. 처음에는 `--confirm`을 붙이지 않아 미전송 미리보기를 만듭니다.
2. `OrderIntent`와 유효한 `ApprovalRecord`를 확인합니다.
3. 종목·수량·가격·주문 유형·demo 프로필이 미리보기와 같을 때만 `--confirm`을 붙입니다.
4. 실패한 주문을 자동으로 재시도하지 않습니다.

Keyring은 같은 OS 사용자 안의 에이전트를 물리적으로 격리하지 않습니다. 강의의 Sam·Ada 분리는 스킬·파일 계약·승인 기록을 이용한 역할 분리입니다. 실계좌의 강한 격리는 별도 OS 사용자·컨테이너·실행 정책이 필요합니다.
