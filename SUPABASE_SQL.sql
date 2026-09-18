create table if not exists public.paper_state (
  id bigint primary key,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.paper_state enable row level security;
