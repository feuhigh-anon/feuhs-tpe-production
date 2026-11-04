-- Read-only aggregate diagnostics. Run in the Supabase SQL Editor as operator.
-- No identities, student numbers, emails, passwords or response text returned.
select current_timestamp as checked_at,
       pg_database_size(current_database()) as database_bytes,
       pg_size_pretty(pg_database_size(current_database())) as database_size,
       (select count(*) from auth.users) as auth_users,
       (select count(*) from public.students) as students,
       (select count(*) from public.evaluation_submissions) as submissions,
       (select count(*) from public.evaluation_responses) as responses,
       (select count(*) from public.roster_stage_students) as staged_students,
       (select count(*) from public.roster_stage_student_assignments) as staged_links,
       (select count(*) from public.roster_import_issues) as import_issues,
       (select count(*) from storage.objects) as storage_objects;

select c.relname as table_name,
       pg_total_relation_size(c.oid) as total_bytes,
       c.reltuples::bigint as estimated_rows,
       c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relkind='r'
order by pg_total_relation_size(c.oid) desc;

select batch_id,severity,issue_code,count(*) as findings
from public.roster_import_issues
group by batch_id,severity,issue_code order by batch_id,severity,issue_code;

select id,batch_code,evaluation_period_id,status,validated_at,activated_at
from public.roster_import_batches order by id;

select code,status,opens_at,closes_at from public.evaluation_periods order by id;

select version from supabase_migrations.schema_migrations order by version;
