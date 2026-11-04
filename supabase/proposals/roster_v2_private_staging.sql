-- REVIEW PROPOSAL ONLY. Not a migration and not deployed automatically.
-- Compact transport staging; this does not activate targets or change the portal.
begin;

create table public.roster_v2_batches (
    id bigint generated always as identity primary key,
    batch_code text not null unique,
    evaluation_period_id bigint not null references public.evaluation_periods(id) on delete restrict,
    manifest_sha256 text not null check (manifest_sha256 ~ '^[a-f0-9]{64}$'),
    source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
    counts jsonb not null check (jsonb_typeof(counts)='object'),
    status text not null default 'draft' check (status in ('draft','reviewed','archived')),
    created_at timestamptz not null default now(),
    archived_at timestamptz
);
create index roster_v2_batches_period_idx on public.roster_v2_batches(evaluation_period_id);

-- JSONB/TOAST avoids a second six-table staging schema and thousands of
-- duplicate eligibility rows. Keep metadata after archived payload removal.
create table public.roster_v2_payloads (
    batch_id bigint primary key references public.roster_v2_batches(id) on delete restrict,
    payload jsonb not null check (jsonb_typeof(payload)='object'),
    uploaded_at timestamptz not null default now()
);

alter table public.roster_v2_batches enable row level security;
alter table public.roster_v2_payloads enable row level security;
revoke all on public.roster_v2_batches,public.roster_v2_payloads from public,anon,authenticated;
grant select,insert on public.roster_v2_batches,public.roster_v2_payloads to service_role;
grant usage,select on sequence public.roster_v2_batches_id_seq to service_role;
-- No student policies and no activation RPC are introduced here.
commit;
