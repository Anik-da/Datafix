-- Run in the Supabase SQL editor before setting DATAFIX_STORAGE_BACKEND=supabase.
-- Create a private Storage bucket named `datafix` in the Storage dashboard.
-- Backend requests authenticate with SUPABASE_SECRET_KEY (preferred) or the
-- legacy SUPABASE_SERVICE_ROLE_KEY. Both remain server-only credentials.

create table if not exists public.datafix_runs (
  id uuid primary key,
  filename text not null,
  sha256 text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  row_count integer not null check (row_count >= 0),
  column_count integer not null check (column_count >= 0),
  status text not null check (status in ('uploaded', 'analyzed', 'applied')),
  created_at timestamptz not null,
  original_path text not null unique,
  working_json text not null,
  analysis jsonb,
  format_metadata jsonb not null default '{"format":"csv"}'::jsonb
);

alter table public.datafix_runs add column if not exists format_metadata jsonb not null default '{"format":"csv"}'::jsonb;

-- Content-addressed export records. Objects are private in the `datafix` bucket
-- and keyed by run/name/SHA-256 so repeated exports cannot silently overwrite.
create table if not exists public.datafix_artifacts (
  run_id uuid not null references public.datafix_runs(id) on delete cascade,
  name text not null check (name in ('cleaned','report','log','recipe','passport')),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  content_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  object_path text not null unique,
  created_at timestamptz not null,
  primary key (run_id,name,sha256)
);

create table if not exists public.datafix_verifications (
  run_id uuid not null references public.datafix_runs(id) on delete cascade,
  verification_id text primary key,
  verified_at timestamptz not null,
  result jsonb not null
);

create table if not exists public.datafix_decisions (
  run_id uuid not null references public.datafix_runs(id) on delete cascade,
  proposal_id text not null,
  action text not null check (action in ('approve', 'reject')),
  decided_at timestamptz not null,
  primary key (run_id, proposal_id)
);

-- Save explicit review decisions and the audited proposal state in one database transaction.
create or replace function public.datafix_save_review(p_run_id uuid, p_decisions jsonb, p_analysis jsonb)
returns void language plpgsql security invoker set search_path = '' as $$
declare item jsonb; old_action text;
begin
  perform 1 from public.datafix_runs where id=p_run_id for update;
  if not found then raise exception 'unknown run'; end if;
  for item in select value from pg_catalog.jsonb_array_elements(p_decisions)
  loop
    select action into old_action from public.datafix_decisions where run_id=p_run_id and proposal_id=item->>'proposal_id';
    if old_action is not null and old_action <> item->>'action' then
      raise exception 'proposal decision conflict' using errcode='23505';
    end if;
  end loop;
  for item in select value from pg_catalog.jsonb_array_elements(p_decisions)
  loop
    insert into public.datafix_decisions(run_id,proposal_id,action,decided_at)
    values(p_run_id,item->>'proposal_id',item->>'action',(item->>'decided_at')::timestamptz)
    on conflict(run_id,proposal_id) do nothing;
  end loop;
  update public.datafix_runs set analysis=p_analysis where id=p_run_id;
end; $$;

create or replace function public.datafix_save_analysis_and_clear_decision(p_run_id uuid, p_proposal_id text, p_analysis jsonb)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  perform 1 from public.datafix_runs where id=p_run_id for update;
  if not found then raise exception 'unknown run'; end if;
  delete from public.datafix_decisions where run_id=p_run_id and proposal_id=p_proposal_id;
  update public.datafix_runs set analysis=p_analysis where id=p_run_id;
end; $$;

create table if not exists public.datafix_operations (
  run_id uuid not null references public.datafix_runs(id) on delete cascade,
  seq integer not null,
  op_id text primary key,
  proposal_id text not null,
  op text not null,
  column_name text,
  cells_changed integer not null,
  rows_removed integer not null,
  decided_by text not null check (decided_by in ('auto', 'user')),
  applied_at timestamptz not null,
  confidence double precision,
  active boolean not null default true,
  before_data text not null,
  after_data text not null,
  params jsonb not null,
  cell_log jsonb not null,
  unique (run_id, seq)
);

alter table public.datafix_runs enable row level security;
alter table public.datafix_decisions enable row level security;
alter table public.datafix_operations enable row level security;
alter table public.datafix_artifacts enable row level security;
alter table public.datafix_verifications enable row level security;
-- No anon/authenticated policies are created. Service-role backend requests bypass RLS.
-- Explicit privileges are needed for PostgREST access on projects with restricted
-- Data API exposure defaults. No client role receives access to these tables.
grant usage on schema public to service_role;
grant select, insert, update on public.datafix_runs to service_role;
grant select, insert on public.datafix_decisions to service_role;
grant select, insert, update on public.datafix_operations to service_role;
grant select, insert on public.datafix_artifacts to service_role;
grant select, insert on public.datafix_verifications to service_role;

-- Preserve applied status while atomically recording a newer analysis document.
create or replace function public.datafix_mark_analyzed(p_run_id uuid, p_analysis jsonb)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  update public.datafix_runs
     set status=case when status='applied' then 'applied' else 'analyzed' end,
         analysis=p_analysis
   where id=p_run_id;
  if not found then raise exception 'unknown run'; end if;
end; $$;

drop function if exists public.datafix_apply_batch(uuid,jsonb,text);
create or replace function public.datafix_apply_batch(p_run_id uuid, p_operations jsonb, p_working_json text, p_expected_working_json text)
returns void language plpgsql security invoker set search_path = '' as $$
declare item jsonb; next_seq integer; current_working text;
begin
  select working_json into current_working from public.datafix_runs where id = p_run_id for update;
  if not found then raise exception 'unknown run'; end if;
  if current_working <> p_expected_working_json then raise exception 'concurrent update' using errcode='40001'; end if;
  select coalesce(max(seq),0) into next_seq from public.datafix_operations where run_id=p_run_id;
  for item in select value from pg_catalog.jsonb_array_elements(p_operations)
  loop
    next_seq := next_seq + 1;
    insert into public.datafix_operations(run_id,seq,op_id,proposal_id,op,column_name,cells_changed,rows_removed,decided_by,applied_at,confidence,active,before_data,after_data,params,cell_log)
    values(p_run_id,next_seq,item->>'op_id',item->>'proposal_id',item->>'op',item->>'column',(item->>'cells_changed')::integer,(item->>'rows_removed')::integer,item->>'decided_by',(item->>'applied_at')::timestamptz,(item->>'confidence')::double precision,true,item->>'before_data',item->>'after_data',item->'params',item->'cell_log');
  end loop;
  update public.datafix_runs set working_json=p_working_json,status='applied' where id=p_run_id;
end; $$;

create or replace function public.datafix_undo_latest(p_run_id uuid, p_op_id text)
returns boolean language plpgsql security invoker set search_path = '' as $$
declare latest public.datafix_operations%rowtype; has_active boolean;
begin
  select * into latest from public.datafix_operations where run_id=p_run_id and active=true order by seq desc limit 1 for update;
  if not found or latest.op_id <> p_op_id then return false; end if;
  update public.datafix_runs set working_json=latest.before_data where id=p_run_id;
  update public.datafix_operations set active=false where op_id=p_op_id;
  select exists(select 1 from public.datafix_operations where run_id=p_run_id and active=true) into has_active;
  update public.datafix_runs set status=case when has_active then 'applied' else 'analyzed' end where id=p_run_id;
  return true;
end; $$;

revoke all on function public.datafix_apply_batch(uuid,jsonb,text,text) from public, anon, authenticated;
revoke all on function public.datafix_mark_analyzed(uuid,jsonb) from public, anon, authenticated;
revoke all on function public.datafix_undo_latest(uuid,text) from public, anon, authenticated;
revoke all on function public.datafix_save_review(uuid,jsonb,jsonb) from public, anon, authenticated;
revoke all on function public.datafix_save_analysis_and_clear_decision(uuid,text,jsonb) from public, anon, authenticated;
grant execute on function public.datafix_apply_batch(uuid,jsonb,text,text) to service_role;
grant execute on function public.datafix_mark_analyzed(uuid,jsonb) to service_role;
grant execute on function public.datafix_undo_latest(uuid,text) to service_role;
grant execute on function public.datafix_save_review(uuid,jsonb,jsonb) to service_role;
grant execute on function public.datafix_save_analysis_and_clear_decision(uuid,text,jsonb) to service_role;
