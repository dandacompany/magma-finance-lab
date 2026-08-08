# Supabase 변경 계약

migrations/20260806090000_finance_contract.sql은 finance 스키마의 로컬 검토본입니다.
녹화 중 라이브 데이터베이스에 적용하지 않습니다.

검토 순서:

1. 대상 프로젝트와 스키마가 맞는지 확인합니다.
2. 기존 테이블 정의와 migration의 차이를 확인합니다.
3. Data API를 사용할지 결정합니다.
4. RLS 정책과 역할별 grant를 함께 설계한 뒤 별도 승인을 받아 적용합니다.

이 migration은 anon, authenticated, service_role에 권한을 부여하지 않습니다.
직접 Postgres 연결과 Data API 권한은 서로 다른 경계입니다.
