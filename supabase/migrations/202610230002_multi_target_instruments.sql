-- Add target-specific assignment, submission, and response tables.
-- Apply only after the reviewed roster is approved and imported. Questionnaire catalog is seeded separately.

create table public.homeroom_programs (
  id bigint generated always as identity primary key,
  code text not null,
  display_name text not null,
  school_level text not null check (school_level in ('JHS','SHS')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (code,school_level)
);

insert into public.homeroom_programs (code,display_name,school_level)
values ('BE_BRAVE','Be Brave Homeroom Program','JHS'),
       ('BE_BRAVE','Be Brave Homeroom Program','SHS');

create table public.evaluation_targets (
  id bigint generated always as identity primary key,
  evaluation_period_id bigint not null references public.evaluation_periods(id) on delete restrict,
  section_id bigint not null references public.sections(id) on delete restrict,
  target_type text not null check (target_type in ('subject_teacher','homeroom_adviser','homeroom_program')),
  target_label text,
  teacher_id bigint references public.teachers(id) on delete restrict,
  subject_id bigint references public.subjects(id) on delete restrict,
  program_id bigint references public.homeroom_programs(id) on delete restrict,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  check (
    (target_type='subject_teacher' and teacher_id is not null and subject_id is not null and program_id is null)
    or (target_type='homeroom_adviser' and teacher_id is not null and subject_id is null and program_id is null)
    or (target_type='homeroom_program' and teacher_id is null and subject_id is null and program_id is not null)
  ),
  unique (id,evaluation_period_id)
);
create unique index evaluation_targets_subject_uq on public.evaluation_targets
  (evaluation_period_id,section_id,subject_id,teacher_id) where target_type='subject_teacher';
create unique index evaluation_targets_adviser_uq on public.evaluation_targets
  (evaluation_period_id,section_id) where target_type='homeroom_adviser';
create unique index evaluation_targets_program_uq on public.evaluation_targets
  (evaluation_period_id,section_id,program_id) where target_type='homeroom_program';
create index evaluation_targets_period_section_idx on public.evaluation_targets(evaluation_period_id,section_id);

create table public.student_evaluation_targets (
  student_id uuid not null references public.students(profile_id) on delete cascade,
  evaluation_target_id bigint not null references public.evaluation_targets(id) on delete cascade,
  is_active boolean not null default true,
  assigned_at timestamptz not null default now(),
  primary key (student_id,evaluation_target_id)
);
create index student_evaluation_targets_target_idx on public.student_evaluation_targets(evaluation_target_id);

create table public.evaluation_target_instruments (
  evaluation_period_id bigint not null references public.evaluation_periods(id) on delete restrict,
  school_level text not null check (school_level in ('JHS','SHS')),
  target_type text not null check (target_type in ('subject_teacher','homeroom_adviser','homeroom_program')),
  question_bank_id bigint not null references public.question_banks(id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (evaluation_period_id,school_level,target_type),
  unique (evaluation_period_id,question_bank_id)
);

create table public.evaluation_target_submissions (
  id bigint generated always as identity primary key,
  student_id uuid not null,
  evaluation_target_id bigint not null,
  evaluation_period_id bigint not null,
  question_bank_id bigint not null,
  submitted_at timestamptz not null default now(),
  client_version text,
  unique (student_id,evaluation_target_id,evaluation_period_id),
  unique (id,question_bank_id),
  foreign key (student_id,evaluation_target_id)
    references public.student_evaluation_targets(student_id,evaluation_target_id) on delete restrict,
  foreign key (evaluation_target_id,evaluation_period_id)
    references public.evaluation_targets(id,evaluation_period_id) on delete restrict,
  foreign key (evaluation_period_id,question_bank_id)
    references public.evaluation_target_instruments(evaluation_period_id,question_bank_id) on delete restrict
);

create table public.evaluation_target_responses (
  submission_id bigint not null,
  question_item_id bigint not null,
  question_bank_id bigint not null,
  rating_value smallint,
  text_value text,
  is_not_applicable boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (submission_id,question_item_id),
  foreign key (submission_id,question_bank_id)
    references public.evaluation_target_submissions(id,question_bank_id) on delete cascade,
  foreign key (question_item_id,question_bank_id)
    references public.question_items(id,question_bank_id) on delete restrict,
  check (rating_value is null or rating_value between 1 and 5),
  check (
    (rating_value is not null and text_value is null and is_not_applicable=false)
    or (rating_value is null and nullif(btrim(text_value),'') is not null)
  )
);
create index evaluation_target_responses_item_idx on public.evaluation_target_responses(question_item_id);
create index evaluation_target_submissions_period_idx on public.evaluation_target_submissions(evaluation_period_id);
create index evaluation_target_submissions_student_idx on public.evaluation_target_submissions(student_id);

alter table public.homeroom_programs enable row level security;
alter table public.evaluation_targets enable row level security;
alter table public.student_evaluation_targets enable row level security;
alter table public.evaluation_target_instruments enable row level security;
alter table public.evaluation_target_submissions enable row level security;
alter table public.evaluation_target_responses enable row level security;

create policy homeroom_programs_select_assigned on public.homeroom_programs for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_targets et join public.student_evaluation_targets setg
    on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active
    and et.program_id=homeroom_programs.id
));
create policy evaluation_targets_select_assigned on public.evaluation_targets for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.student_evaluation_targets setg
  where setg.evaluation_target_id=evaluation_targets.id
    and setg.student_id=(select auth.uid()) and setg.is_active
));
create policy student_evaluation_targets_select_own on public.student_evaluation_targets for select to authenticated
using (student_id=(select auth.uid()) or (select public.is_admin()));
create policy target_instruments_select_assigned on public.evaluation_target_instruments for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_targets et join public.student_evaluation_targets setg
    on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active
    and et.evaluation_period_id=evaluation_target_instruments.evaluation_period_id
    and et.target_type=evaluation_target_instruments.target_type
));
create policy target_submissions_select_own on public.evaluation_target_submissions for select to authenticated
using (student_id=(select auth.uid()) or (select public.is_admin()));
create policy target_responses_select_admin on public.evaluation_target_responses for select to authenticated
using ((select public.is_admin()));

create policy target_question_banks_select on public.question_banks for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_target_instruments eti
  join public.evaluation_targets et on et.evaluation_period_id=eti.evaluation_period_id and et.target_type=eti.target_type
  join public.student_evaluation_targets setg on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active
    and eti.question_bank_id=question_banks.id
));
create policy target_question_items_select on public.question_items for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_target_instruments eti
  join public.evaluation_targets et on et.evaluation_period_id=eti.evaluation_period_id and et.target_type=eti.target_type
  join public.student_evaluation_targets setg on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active
    and eti.question_bank_id=question_items.question_bank_id
));
create policy target_periods_select_assigned on public.evaluation_periods for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_targets et join public.student_evaluation_targets setg
    on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active
    and et.evaluation_period_id=evaluation_periods.id
));
create policy target_teachers_select_assigned on public.teachers for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_targets et join public.student_evaluation_targets setg
    on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active and et.teacher_id=teachers.id
));
create policy target_subjects_select_assigned on public.subjects for select to authenticated
using ((select public.is_admin()) or exists (
  select 1 from public.evaluation_targets et join public.student_evaluation_targets setg
    on setg.evaluation_target_id=et.id
  where setg.student_id=(select auth.uid()) and setg.is_active and et.is_active and et.subject_id=subjects.id
));

revoke all on public.homeroom_programs,public.evaluation_targets,public.student_evaluation_targets,
  public.evaluation_target_instruments,public.evaluation_target_submissions,public.evaluation_target_responses
  from anon,authenticated;
grant select on public.homeroom_programs,public.evaluation_targets,public.student_evaluation_targets,
  public.evaluation_target_instruments,public.evaluation_target_submissions,public.evaluation_target_responses
  to authenticated;

create or replace function public.submit_target_evaluation(
  p_evaluation_target_id bigint,p_responses jsonb,p_client_version text default null
) returns bigint language plpgsql security definer set search_path='' as $$
declare
  current_student_id uuid := (select auth.uid());
  selected_period_id bigint;
  selected_bank_id bigint;
  selected_target_type text;
  selected_school_level text;
  expected_required_count integer;
  provided_required_count integer;
  new_submission_id bigint;
begin
  if current_student_id is null then raise exception 'Authentication is required'; end if;
  if jsonb_typeof(p_responses) is distinct from 'array' then raise exception 'Responses must be a JSON array'; end if;

  select et.evaluation_period_id,eti.question_bank_id,et.target_type,sec.school_level
    into selected_period_id,selected_bank_id,selected_target_type,selected_school_level
  from public.student_evaluation_targets setg
  join public.students s on s.profile_id=setg.student_id
  join public.profiles p on p.id=s.profile_id
  join public.evaluation_targets et on et.id=setg.evaluation_target_id
  join public.sections sec on sec.id=s.section_id
  join public.evaluation_periods ep on ep.id=et.evaluation_period_id
  join public.evaluation_target_instruments eti
    on eti.evaluation_period_id=et.evaluation_period_id
   and eti.school_level=sec.school_level and eti.target_type=et.target_type
  join public.question_banks qb on qb.id=eti.question_bank_id
   and qb.school_level=sec.school_level and qb.target_type=et.target_type
  where setg.student_id=current_student_id and setg.evaluation_target_id=p_evaluation_target_id
    and setg.is_active and et.is_active and sec.is_active and p.is_active
    and ep.status='open' and now()>=ep.opens_at and now()<ep.closes_at and qb.status='published';
  if not found then raise exception 'No open authorized evaluation target was found'; end if;

  if (select count(*) from jsonb_to_recordset(p_responses) as x(question_item_id bigint,rating_value smallint,text_value text))
     <> (select count(distinct x.question_item_id) from jsonb_to_recordset(p_responses) as x(question_item_id bigint,rating_value smallint,text_value text))
     then raise exception 'A question can be answered only once'; end if;

  if exists (
    select 1 from jsonb_to_recordset(p_responses) as x(question_item_id bigint,rating_value smallint,text_value text)
    left join public.question_items qi on qi.id=x.question_item_id and qi.question_bank_id=selected_bank_id
    where qi.id is null
      or (qi.response_type='likert_5' and (x.rating_value is null or x.rating_value not between 1 and 5 or x.text_value is not null))
      or (qi.response_type='likert_4' and (x.rating_value is null or x.rating_value not between 1 and 4 or x.text_value is not null))
      or (qi.response_type='text' and (x.rating_value is not null or nullif(btrim(x.text_value),'') is null))
  ) then raise exception 'One or more responses do not match the active questionnaire'; end if;

  select count(*) into expected_required_count from public.question_items qi
    where qi.question_bank_id=selected_bank_id and qi.is_required;
  select count(*) into provided_required_count
  from jsonb_to_recordset(p_responses) as x(question_item_id bigint,rating_value smallint,text_value text)
  join public.question_items qi on qi.id=x.question_item_id and qi.question_bank_id=selected_bank_id
  where qi.is_required;
  if provided_required_count<>expected_required_count then raise exception 'All required responses must be answered'; end if;

  insert into public.evaluation_target_submissions(student_id,evaluation_target_id,evaluation_period_id,question_bank_id,client_version)
  values(current_student_id,p_evaluation_target_id,selected_period_id,selected_bank_id,nullif(btrim(p_client_version),''))
  returning id into new_submission_id;
  insert into public.evaluation_target_responses(submission_id,question_item_id,question_bank_id,rating_value,text_value,is_not_applicable)
  select new_submission_id,x.question_item_id,selected_bank_id,x.rating_value,nullif(btrim(x.text_value),''),false
  from jsonb_to_recordset(p_responses) as x(question_item_id bigint,rating_value smallint,text_value text);
  insert into public.submission_audit_events(student_id,event_type,details)
  values(current_student_id,'submitted',jsonb_build_object('evaluation_target_id',p_evaluation_target_id,
    'evaluation_period_id',selected_period_id,'question_bank_id',selected_bank_id,
    'target_type',selected_target_type,'response_count',jsonb_array_length(p_responses)));
  return new_submission_id;
exception when unique_violation then raise exception 'This evaluation has already been submitted';
end;
$$;

revoke execute on function public.submit_target_evaluation(bigint,jsonb,text) from public;
grant execute on function public.submit_target_evaluation(bigint,jsonb,text) to authenticated;
