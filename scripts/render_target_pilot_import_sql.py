"""Render a guarded, transaction-based SQL import for the synthetic Q2 pilot."""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


PERIOD_CODE = "PILOT-SY2026-2027-Q2-FINALS-01"
OPEN_AT = "2026-11-03 00:00:00+08"
CLOSE_AT = "2026-12-31 23:59:59+08"
BANKS = {
    (level, target): (code, version)
    for level in ("JHS", "SHS")
    for target, code, version in (
        ("subject_teacher", f"faculty-evaluation-{level.lower()}", 2),
        ("homeroom_adviser", f"homeroom-adviser-evaluation-{level.lower()}", 1),
        ("homeroom_program", f"homeroom-program-evaluation-{level.lower()}", 1),
    )
}


def literal(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    accounts: dict[str, dict[str, str]] = {}
    targets: dict[tuple[str, str, str, str], dict[str, str]] = {}
    account_targets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        account_key = row["pilot_student_key"]
        account = {key: row[key] for key in (
            "pilot_student_key", "email", "cohort", "grade_level", "student_section_code", "teaching_section_code"
        )}
        if account_key in accounts and accounts[account_key] != account:
            raise SystemExit(f"Inconsistent account metadata for {account_key}")
        accounts[account_key] = account
        key = (row["target_type"], row["teaching_section_code"], row["teacher_employee_number"], row["subject_code"] or row["program_code"])
        targets[key] = row
        account_targets[account_key].append(row)

    if len(accounts) != 45 or len(rows) != 180:
        raise SystemExit(f"Expected 45 accounts and 180 target links; found {len(accounts)} and {len(rows)}")
    cohorts = Counter(account["cohort"] for account in accounts.values())
    if cohorts != Counter({"JHS": 15, "G11": 15, "G12": 15}):
        raise SystemExit(f"Unexpected cohort counts: {dict(cohorts)}")
    for key, account in accounts.items():
        items = account_targets[key]
        kinds = Counter(item["target_type"] for item in items)
        teachers = {item["teacher_employee_number"] for item in items if item["target_type"] == "subject_teacher"}
        if kinds != Counter({"subject_teacher": 2, "homeroom_adviser": 1, "homeroom_program": 1}) or len(teachers) != 2:
            raise SystemExit(f"Invalid four-target allocation for {key}: {dict(kinds)}")
        if account["cohort"] == "JHS" and not 7 <= int(account["grade_level"]) <= 10:
            raise SystemExit(f"Invalid JHS grade for {key}")
        if account["cohort"] == "G11" and int(account["grade_level"]) != 11:
            raise SystemExit(f"Invalid Grade 11 value for {key}")
        if account["cohort"] == "G12" and int(account["grade_level"]) != 12:
            raise SystemExit(f"Invalid Grade 12 value for {key}")
    return sorted(accounts.values(), key=lambda item: item["pilot_student_key"])


def render(rows: list[dict[str, str]], accounts: list[dict[str, str]]) -> str:
    values = ",\n".join(
        "  (" + ", ".join(literal(row[key]) for key in (
            "pilot_student_key", "email", "cohort", "grade_level", "student_section_code",
            "teaching_section_code", "target_type", "teacher_employee_number", "subject_code",
            "subject_name", "program_code"
        )) + ")"
        for row in rows
    )
    bank_values = ",\n".join(
        "  (" + ", ".join((literal(level), literal(target), literal(code), str(version))) + ")"
        for (level, target), (code, version) in sorted(BANKS.items())
    )
    return f'''-- Prepared Q2 synthetic pilot import. Do not run until the preflight checks pass.
-- This script does not create/reset Auth users and does not open the evaluation period.
-- All database changes below run in one transaction; any guard failure stops the import.

begin;

create temporary table pilot_target_stage (
  pilot_student_key text not null,
  email text not null,
  cohort text not null,
  grade_level smallint not null,
  student_section_code text not null,
  teaching_section_code text not null,
  target_type text not null,
  teacher_employee_number text,
  subject_code text,
  subject_name text,
  program_code text
) on commit drop;

insert into pilot_target_stage values
{values};

create temporary table pilot_bank_stage (
  school_level text not null,
  target_type text not null,
  bank_code text not null,
  bank_version integer not null
) on commit drop;

insert into pilot_bank_stage values
{bank_values};

-- The current teaching roster includes 11ME02. Add it only when absent;
-- preserve 11GS01 as the students' official section.
insert into public.sections(code,school_level,grade_level,strand,is_active)
values ('11ME02','SHS',11,null,true)
on conflict (code) do nothing;

do $$
declare
  n integer;
begin
  select count(*) into n from (select distinct pilot_student_key from pilot_target_stage) a;
  if n <> 45 then raise exception 'Expected 45 pilot accounts; found %', n; end if;
  select count(*) into n from pilot_target_stage;
  if n <> 180 then raise exception 'Expected 180 target links; found %', n; end if;
  select count(distinct email) into n from pilot_target_stage;
  if n <> 45 then raise exception 'Expected 45 distinct pilot emails; found %', n; end if;
  if exists (
    select 1 from pilot_target_stage group by pilot_student_key
    having count(*) <> 4
      or count(*) filter (where target_type='subject_teacher') <> 2
      or count(*) filter (where target_type='homeroom_adviser') <> 1
      or count(*) filter (where target_type='homeroom_program') <> 1
      or count(distinct teacher_employee_number) filter (where target_type='subject_teacher') <> 2
  ) then raise exception 'Pilot accounts must each have two distinct subject teachers, one adviser, and one program'; end if;

  select count(*) into n from (
    select distinct s.pilot_student_key
    from pilot_target_stage s
    join auth.users au on lower(au.email)=lower(s.email)
    join public.profiles p on p.id=au.id and p.role='student' and p.is_active
    join public.students st on st.profile_id=p.id
  ) matched;
  if n <> 45 then raise exception 'Expected all 45 existing Auth/profile/student records to match; found %', n; end if;

  if not exists (
    select 1 from public.sections
    where code='11ME02' and school_level='SHS' and grade_level=11 and is_active
  ) then raise exception 'Teaching section 11ME02 must be active SHS Grade 11'; end if;

  if exists (
    select 1 from (select distinct student_section_code,grade_level from pilot_target_stage) a
    left join public.sections sec on sec.code=a.student_section_code and sec.is_active
    where sec.id is null or sec.grade_level<>a.grade_level
  ) then raise exception 'An official pilot student section is missing, inactive, or has the wrong grade'; end if;
  if exists (
    select 1 from (select distinct teaching_section_code from pilot_target_stage) a
    left join public.sections sec on sec.code=a.teaching_section_code and sec.is_active
    where sec.id is null
  ) then raise exception 'A teaching section is missing or inactive'; end if;
  if exists (
    select 1 from (select distinct teacher_employee_number from pilot_target_stage where teacher_employee_number is not null) a
    left join public.teachers t on t.employee_number=a.teacher_employee_number and t.is_active
    where t.id is null
  ) then raise exception 'A pilot teacher is missing or inactive'; end if;
  if exists (
    select 1 from (select distinct subject_code from pilot_target_stage where subject_code is not null) a
    left join public.subjects s on s.code=a.subject_code and s.is_active
    where s.id is null
  ) then raise exception 'A pilot subject is missing or inactive'; end if;
  if exists (
    select 1 from (select distinct program_code from pilot_target_stage where program_code is not null) a
    left join public.homeroom_programs hp on hp.code=a.program_code and hp.is_active
    where hp.id is null
  ) then raise exception 'A homeroom program is missing or inactive'; end if;

  select count(*) into n
  from pilot_bank_stage b
  join public.question_banks qb on qb.code=b.bank_code and qb.version=b.bank_version
    and qb.school_level=b.school_level and qb.target_type=b.target_type and qb.status='published';
  if n <> 6 then raise exception 'Expected six matching published questionnaire banks; found %', n; end if;

  if exists (
    select 1 from public.evaluation_periods ep
    where ep.code={literal(PERIOD_CODE)} and ep.status <> 'draft'
  ) then raise exception 'The pilot period already exists and is not draft'; end if;
end;
$$;

insert into public.evaluation_periods(code,academic_year,term,opens_at,closes_at,status)
values ({literal(PERIOD_CODE)},'2026-2027','Q2','{OPEN_AT}'::timestamptz,'{CLOSE_AT}'::timestamptz,'draft')
on conflict (code) do nothing;

do $$
declare
  n integer;
begin
  select count(*) into n from public.evaluation_periods
  where code={literal(PERIOD_CODE)} and academic_year='2026-2027' and term='Q2'
    and opens_at='{OPEN_AT}'::timestamptz and closes_at='{CLOSE_AT}'::timestamptz and status='draft';
  if n <> 1 then raise exception 'Existing pilot period metadata differs from the prepared draft period'; end if;
  if exists (
    select 1 from public.evaluation_target_submissions sub
    join public.evaluation_periods ep on ep.id=sub.evaluation_period_id and ep.code={literal(PERIOD_CODE)}
    join auth.users au on au.id=sub.student_id
    join pilot_target_stage p on lower(p.email)=lower(au.email)
  ) then raise exception 'Pilot submissions already exist for this period; refusing to replace links'; end if;
end;
$$;

insert into public.evaluation_target_instruments(evaluation_period_id,school_level,target_type,question_bank_id)
select ep.id,b.school_level,b.target_type,qb.id
from public.evaluation_periods ep
cross join pilot_bank_stage b
join public.question_banks qb on qb.code=b.bank_code and qb.version=b.bank_version
  and qb.school_level=b.school_level and qb.target_type=b.target_type and qb.status='published'
where ep.code={literal(PERIOD_CODE)}
on conflict (evaluation_period_id,school_level,target_type) do nothing;

do $$
declare n integer;
begin
  select count(*) into n
  from public.evaluation_target_instruments eti
  join public.evaluation_periods ep on ep.id=eti.evaluation_period_id and ep.code={literal(PERIOD_CODE)}
  join pilot_bank_stage b on b.school_level=eti.school_level and b.target_type=eti.target_type
  join public.question_banks qb on qb.id=eti.question_bank_id and qb.code=b.bank_code and qb.version=b.bank_version;
  if n <> 6 then raise exception 'Pilot period must map exactly to the six prepared published banks'; end if;
end;
$$;

-- Move only these synthetic accounts to their approved current official sections.
update public.students st
set section_id=sec.id, updated_at=now()
from pilot_target_stage p
join auth.users au on lower(au.email)=lower(p.email)
join public.sections sec on sec.code=p.student_section_code and sec.is_active
where st.profile_id=au.id and st.section_id<>sec.id;

insert into public.evaluation_targets(evaluation_period_id,section_id,target_type,target_label,teacher_id,subject_id,program_id)
select distinct ep.id,sec.id,'subject_teacher',p.subject_name,t.id,s.id,null::bigint
from pilot_target_stage p
join public.evaluation_periods ep on ep.code={literal(PERIOD_CODE)}
join public.sections sec on sec.code=p.teaching_section_code and sec.is_active
join public.teachers t on t.employee_number=p.teacher_employee_number and t.is_active
join public.subjects s on s.code=p.subject_code and s.is_active
where p.target_type='subject_teacher'
on conflict do nothing;

insert into public.evaluation_targets(evaluation_period_id,section_id,target_type,target_label,teacher_id,subject_id,program_id)
select distinct ep.id,sec.id,'homeroom_adviser',t.display_name,t.id,null::bigint,null::bigint
from pilot_target_stage p
join public.evaluation_periods ep on ep.code={literal(PERIOD_CODE)}
join public.sections sec on sec.code=p.teaching_section_code and sec.is_active
join public.teachers t on t.employee_number=p.teacher_employee_number and t.is_active
where p.target_type='homeroom_adviser'
on conflict do nothing;

insert into public.evaluation_targets(evaluation_period_id,section_id,target_type,target_label,teacher_id,subject_id,program_id)
select distinct ep.id,sec.id,'homeroom_program',hp.display_name,null::bigint,null::bigint,hp.id
from pilot_target_stage p
join public.evaluation_periods ep on ep.code={literal(PERIOD_CODE)}
join public.sections sec on sec.code=p.teaching_section_code and sec.is_active
join public.homeroom_programs hp on hp.code=p.program_code and hp.school_level=sec.school_level and hp.is_active
where p.target_type='homeroom_program'
on conflict do nothing;

-- Replace only this pilot's not-yet-submitted links in this new Q2 period.
update public.student_evaluation_targets link
set is_active=false
from public.evaluation_targets et, public.evaluation_periods ep, public.students st
join auth.users au on au.id=st.profile_id
join pilot_target_stage p on lower(p.email)=lower(au.email)
where link.student_id=st.profile_id and et.id=link.evaluation_target_id
  and ep.id=et.evaluation_period_id and ep.code={literal(PERIOD_CODE)} and link.is_active;

insert into public.student_evaluation_targets(student_id,evaluation_target_id,is_active)
select distinct st.profile_id,et.id,true
from pilot_target_stage p
join auth.users au on lower(au.email)=lower(p.email)
join public.profiles pr on pr.id=au.id and pr.role='student' and pr.is_active
join public.students st on st.profile_id=pr.id
join public.evaluation_periods ep on ep.code={literal(PERIOD_CODE)}
join public.sections sec on sec.code=p.teaching_section_code and sec.is_active
join public.evaluation_targets et on et.evaluation_period_id=ep.id and et.section_id=sec.id and et.target_type=p.target_type
left join public.teachers t on t.employee_number=p.teacher_employee_number
left join public.subjects s on s.code=p.subject_code
left join public.homeroom_programs hp on hp.code=p.program_code and hp.school_level=sec.school_level
where (p.target_type='subject_teacher' and et.teacher_id=t.id and et.subject_id=s.id)
   or (p.target_type='homeroom_adviser' and et.teacher_id=t.id)
   or (p.target_type='homeroom_program' and et.program_id=hp.id)
on conflict (student_id,evaluation_target_id) do update set is_active=true;

do $$
declare n integer;
begin
  select count(*) into n from (
    select st.profile_id
    from public.students st
    join public.profiles p on p.id=st.profile_id and p.role='student' and p.is_active
    join auth.users au on au.id=st.profile_id
    join public.student_evaluation_targets link on link.student_id=st.profile_id and link.is_active
    join public.evaluation_targets et on et.id=link.evaluation_target_id and et.is_active
    join public.evaluation_periods ep on ep.id=et.evaluation_period_id and ep.code={literal(PERIOD_CODE)}
    join pilot_target_stage src on lower(src.email)=lower(au.email)
      and src.target_type=et.target_type
    join public.sections sec on sec.id=et.section_id and sec.code=src.teaching_section_code
    left join public.teachers expected_teacher on expected_teacher.employee_number=src.teacher_employee_number
    left join public.subjects expected_subject on expected_subject.code=src.subject_code
    left join public.homeroom_programs expected_program
      on expected_program.code=src.program_code and expected_program.school_level=sec.school_level
    where (et.target_type='subject_teacher'
           and et.teacher_id=expected_teacher.id and et.subject_id=expected_subject.id)
       or (et.target_type='homeroom_adviser' and et.teacher_id=expected_teacher.id)
       or (et.target_type='homeroom_program' and et.program_id=expected_program.id)
    group by st.profile_id
    having count(*)=4
      and count(*) filter (where et.target_type='subject_teacher')=2
      and count(*) filter (where et.target_type='homeroom_adviser')=1
      and count(*) filter (where et.target_type='homeroom_program')=1
      and count(distinct et.teacher_id) filter (where et.target_type='subject_teacher')=2
  ) valid;
  if n <> 45 then raise exception 'Final pilot allocation check failed: % of 45 accounts have exactly four correct active targets', n; end if;
end;
$$;

commit;

select ep.code,ep.status,
  count(distinct st.profile_id) as pilot_accounts,
  count(*) as active_student_target_links,
  count(*) filter (where et.target_type='subject_teacher') as subject_links,
  count(*) filter (where et.target_type='homeroom_adviser') as adviser_links,
  count(*) filter (where et.target_type='homeroom_program') as program_links
from public.evaluation_periods ep
join public.evaluation_targets et on et.evaluation_period_id=ep.id
join public.student_evaluation_targets link on link.evaluation_target_id=et.id and link.is_active
join public.students st on st.profile_id=link.student_id
where ep.code={literal(PERIOD_CODE)}
group by ep.code,ep.status;
'''


def render_preflight(rows: list[dict[str, str]]) -> str:
    stage_values = ",\n".join(
        "  (" + ", ".join(literal(row[key]) for key in (
            "pilot_student_key", "email", "cohort", "grade_level", "student_section_code",
            "teaching_section_code", "target_type", "teacher_employee_number", "subject_code", "program_code"
        )) + ")"
        for row in rows
    )
    bank_values = ",\n".join(
        "  (" + ", ".join((literal(level), literal(target), literal(code), str(version))) + ")"
        for (level, target), (code, version) in sorted(BANKS.items())
    )
    return f'''-- Read-only preflight for the Q2 synthetic pilot. This file performs SELECTs only.
with stage(pilot_student_key,email,cohort,grade_level,student_section_code,
           teaching_section_code,target_type,teacher_employee_number,subject_code,program_code) as (
  values
{stage_values}
),
accounts as (
  select distinct pilot_student_key,email,student_section_code,grade_level
  from stage
),
banks(school_level,target_type,bank_code,bank_version) as (
  values
{bank_values}
),
checks(check_name,expected,found) as (
  select 'Existing Auth/profile/student accounts',45,
    (select count(distinct a.email) from accounts a
     join auth.users au on lower(au.email)=lower(a.email)
     join public.profiles p on p.id=au.id and p.role='student' and p.is_active
     join public.students st on st.profile_id=p.id)
  union all
  select 'Active official sections with expected grade',
    (select count(*) from (select distinct student_section_code,grade_level from accounts) x),
    (select count(*) from (select distinct student_section_code,grade_level from accounts) x
     join public.sections sec on sec.code=x.student_section_code and sec.is_active and sec.grade_level=x.grade_level::smallint)
  union all
  select 'Teaching sections available or included in import',
    (select count(distinct teaching_section_code) from stage),
    (select count(*) from (select distinct teaching_section_code from stage) x
     where exists (select 1 from public.sections sec
                   where sec.code=x.teaching_section_code and sec.is_active)
        or (x.teaching_section_code='11ME02' and not exists (
              select 1 from public.sections sec where sec.code=x.teaching_section_code)))
  union all
  select 'Active teachers',
    (select count(distinct teacher_employee_number) from stage where teacher_employee_number is not null),
    (select count(*) from (select distinct teacher_employee_number from stage where teacher_employee_number is not null) x
     join public.teachers t on t.employee_number=x.teacher_employee_number and t.is_active)
  union all
  select 'Active subjects',
    (select count(distinct subject_code) from stage where subject_code is not null),
    (select count(*) from (select distinct subject_code from stage where subject_code is not null) x
     join public.subjects s on s.code=x.subject_code and s.is_active)
  union all
  select 'Active Be Brave programs by school level',
    (select count(*) from (select distinct program_code,case when cohort='JHS' then 'JHS' else 'SHS' end as school_level
                            from stage where program_code is not null) x),
    (select count(*) from (select distinct program_code,case when cohort='JHS' then 'JHS' else 'SHS' end as school_level
                            from stage where program_code is not null) x
     join public.homeroom_programs hp on hp.code=x.program_code and hp.school_level=x.school_level and hp.is_active)
  union all
  select 'Published target-specific questionnaire banks',6,
    (select count(*) from banks b join public.question_banks qb on qb.code=b.bank_code
      and qb.version=b.bank_version and qb.school_level=b.school_level
      and qb.target_type=b.target_type and qb.status='published')
  union all
  select 'Target-aware tables installed',6,
    (select count(*) from (values ('homeroom_programs'),('evaluation_targets'),
      ('student_evaluation_targets'),('evaluation_target_instruments'),
      ('evaluation_target_submissions'),('evaluation_target_responses')) t(table_name)
     where to_regclass('public.'||t.table_name) is not null)
  union all
  select 'Pilot period absent or matching draft',1,
    (select case when not exists(select 1 from public.evaluation_periods where code={literal(PERIOD_CODE)})
      or exists(select 1 from public.evaluation_periods where code={literal(PERIOD_CODE)}
        and academic_year='2026-2027' and term='Q2'
        and opens_at='{OPEN_AT}'::timestamptz and closes_at='{CLOSE_AT}'::timestamptz and status='draft')
      then 1 else 0 end)
  union all
  select 'Existing pilot submissions for this period',0,
    (select count(*) from public.evaluation_target_submissions sub
     join public.evaluation_periods ep on ep.id=sub.evaluation_period_id and ep.code={literal(PERIOD_CODE)}
     join auth.users au on au.id=sub.student_id
     join accounts a on lower(a.email)=lower(au.email))
)
select check_name,expected,found,
  case when expected=found then 'READY' else 'BLOCKED' end as result
from checks
order by check_name;
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path)
    args = parser.parse_args()
    rows = load(args.preview)
    accounts = validate(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.output.write_text(render(rows, accounts), encoding="utf-8")
    args.output.chmod(0o600)
    if args.preflight_output:
        args.preflight_output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args.preflight_output.write_text(render_preflight(rows), encoding="utf-8")
        args.preflight_output.chmod(0o600)
    print(f"Wrote guarded pilot import SQL for {len(accounts)} synthetic accounts and {len(rows)} target links")


if __name__ == "__main__":
    main()
