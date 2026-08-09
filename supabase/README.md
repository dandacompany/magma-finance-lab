# Supabase 변경 계약

`migrations/20260806090000_finance_core.sql`은 8.2에서 만드는 라이브 운영 스키마입니다.
`migrations/20260806091000_finance_analysis_contract.sql`은 이후 유닛을 위한 로컬 검토본이며
8.2 녹화 중 라이브 데이터베이스에 적용하지 않습니다.

검토 순서:

1. 대상 프로젝트와 스키마가 맞는지 확인합니다.
2. 읽기 전용 조회로 `finance` 스키마와 핵심 4개 테이블의 존재 여부를 확인합니다.
3. 핵심 4개가 없을 때만 `finance_core.sql`의 대상·객체·권한을 검토합니다.
4. 사람이 승인한 뒤 쓰기 가능한 Supabase MCP로 core SQL을 실행합니다.
5. 재조회에서 핵심 4개 테이블과 RLS 활성화를 확인합니다.
6. Data API를 사용할지 결정한 뒤 필요한 정책과 grant를 별도로 설계합니다.

두 SQL 모두 `anon`, `authenticated`, `service_role`에 권한을 부여하지 않습니다.
이번 수업의 MCP 쓰기는 데이터베이스 소유자 권한에서 사람 승인 후 수행합니다.
Data API의 객체 접근 권한과 RLS의 행 접근 정책은 서로 다른 경계입니다.
