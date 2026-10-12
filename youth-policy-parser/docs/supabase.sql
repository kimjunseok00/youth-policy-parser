-- 익명 통계 저장 테이블 (Supabase SQL Editor에서 한 번 실행)
create table if not exists public.events (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  payload    jsonb not null,
  -- 익명 요약 한 건은 수 KB 이하. 비정상적으로 큰 요청은 거부
  constraint payload_size check (pg_column_size(payload) < 16000)
);

alter table public.events enable row level security;

-- 공개 키(publishable)로는 '쓰기'만 가능. 읽기 정책은 만들지 않는다 (= 공개 키로 읽기 불가)
create policy "anon insert only" on public.events
  for insert to anon with check (true);

-- 보유 기간 2년: 아래 쿼리를 주기적으로 실행하거나 pg_cron으로 예약
-- delete from public.events where created_at < now() - interval '2 years';
