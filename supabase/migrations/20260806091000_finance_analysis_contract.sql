-- Local review contract for later units. Do not apply during the 8.2 recording.

create table if not exists finance.etf_analysis_snapshots (
  artifact_id text primary key,
  symbol text not null references finance.symbols(symbol),
  as_of timestamptz not null,
  available_at timestamptz not null,
  source text not null,
  schema_version text not null,
  content_hash text not null unique check (content_hash ~ '^sha256:[0-9a-f]{64}$'),
  warnings text[] not null default '{}',
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (available_at >= as_of),
  check (payload ->> 'artifact_type' = 'ETFAnalysisSnapshot')
);

create table if not exists finance.backtest_reports (
  artifact_id text primary key,
  data_snapshot_id text not null,
  strategy_spec_id text not null,
  test_period daterange not null,
  signal_at text not null,
  execution_at text not null,
  transaction_cost_bps numeric not null check (transaction_cost_bps >= 0),
  benchmark text not null,
  code_version text not null,
  warnings text[] not null default '{}',
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (payload ->> 'artifact_type' = 'BacktestReport')
);

create index if not exists etf_analysis_snapshots_symbol_as_of_idx
  on finance.etf_analysis_snapshots (symbol, as_of desc);

alter table finance.etf_analysis_snapshots enable row level security;
alter table finance.backtest_reports enable row level security;

revoke all privileges on finance.etf_analysis_snapshots, finance.backtest_reports
  from public, anon, authenticated, service_role;
