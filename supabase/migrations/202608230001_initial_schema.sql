-- FEU High School faculty evaluation platform
-- Initial versioned schema, authorization model, RLS, and atomic submission RPC.

create table public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text not null,
    role text not null default 'student' check (role in ('student', 'admin')),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.sections (
    id bigint generated always as identity primary key,
    code text not null unique,
    school_level text not null check (school_level in ('JHS', 'SHS')),
    grade_level smallint not null check (grade_level between 7 and 12),
    strand text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    check (
        (school_level = 'JHS' and grade_level between 7 and 10)
        or (school_level = 'SHS' and grade_level between 11 and 12)
    )
);

create table public.students (
    profile_id uuid primary key references public.profiles (id) on delete cascade,
    student_number text not null unique,
    section_id bigint not null references public.sections (id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index students_section_id_idx on public.students (section_id);

create table public.teachers (
    id bigint generated always as identity primary key,
    employee_number text unique,
    display_name text not null,
    email text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create unique index teachers_email_lower_idx
    on public.teachers (lower(email))
    where email is not null;

create table public.subjects (
    id bigint generated always as identity primary key,
    code text not null unique,
    name text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table public.evaluation_periods (
    id bigint generated always as identity primary key,
    code text not null unique,
    academic_year text not null,
    term text not null,
    opens_at timestamptz not null,
    closes_at timestamptz not null,
    status text not null default 'draft' check (status in ('draft', 'open', 'closed')),
    created_at timestamptz not null default now(),
    check (closes_at > opens_at)
);

create index evaluation_periods_status_window_idx
    on public.evaluation_periods (status, opens_at, closes_at);

create table public.question_banks (
    id bigint generated always as identity primary key,
    code text not null,
    version integer not null check (version > 0),
    school_level text not null check (school_level in ('JHS', 'SHS')),
    title text not null,
    status text not null default 'draft' check (status in ('draft', 'published', 'retired')),
    published_at timestamptz,
    created_at timestamptz not null default now(),
    unique (code, version),
    check (
        (status = 'draft' and published_at is null)
        or (status in ('published', 'retired') and published_at is not null)
    )
);

create table public.question_items (
    id bigint generated always as identity primary key,
    question_bank_id bigint not null references public.question_banks (id) on delete restrict,
    stable_key text not null,
    section_key text not null check (
        section_key in ('teacher_performance', 'student_experience', 'student_self_evaluation', 'qualitative_feedback')
    ),
    prompt text not null,
    response_type text not null check (response_type in ('likert_5', 'text')),
    position smallint not null check (position > 0),
    is_required boolean not null default true,
    use_for_rci boolean not null default false,
    created_at timestamptz not null default now(),
    unique (question_bank_id, stable_key),
    unique (question_bank_id, section_key, position),
    unique (id, question_bank_id),
    check (
        (response_type = 'text' and section_key = 'qualitative_feedback' and use_for_rci = false)
        or (response_type = 'likert_5' and section_key <> 'qualitative_feedback')
    )
);

create index question_items_question_bank_id_idx
    on public.question_items (question_bank_id);

create table public.evaluation_period_instruments (
    evaluation_period_id bigint not null references public.evaluation_periods (id) on delete restrict,
    school_level text not null check (school_level in ('JHS', 'SHS')),
    question_bank_id bigint not null references public.question_banks (id) on delete restrict,
    created_at timestamptz not null default now(),
    primary key (evaluation_period_id, school_level),
    unique (evaluation_period_id, question_bank_id)
);

create index evaluation_period_instruments_question_bank_id_idx
    on public.evaluation_period_instruments (question_bank_id);

create table public.teaching_assignments (
    id bigint generated always as identity primary key,
    evaluation_period_id bigint not null references public.evaluation_periods (id) on delete restrict,
    section_id bigint not null references public.sections (id) on delete restrict,
    subject_id bigint not null references public.subjects (id) on delete restrict,
    teacher_id bigint not null references public.teachers (id) on delete restrict,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    unique (evaluation_period_id, section_id, subject_id, teacher_id),
    unique (id, evaluation_period_id)
);

create index teaching_assignments_evaluation_period_id_idx
    on public.teaching_assignments (evaluation_period_id);
create index teaching_assignments_section_id_idx
    on public.teaching_assignments (section_id);
create index teaching_assignments_subject_id_idx
    on public.teaching_assignments (subject_id);
create index teaching_assignments_teacher_id_idx
    on public.teaching_assignments (teacher_id);

create table public.student_assignments (
    student_id uuid not null references public.students (profile_id) on delete cascade,
    teaching_assignment_id bigint not null references public.teaching_assignments (id) on delete cascade,
    is_active boolean not null default true,
    assigned_at timestamptz not null default now(),
    primary key (student_id, teaching_assignment_id)
);

create index student_assignments_teaching_assignment_id_idx
    on public.student_assignments (teaching_assignment_id);

create table public.evaluation_submissions (
    id bigint generated always as identity primary key,
    student_id uuid not null,
    teaching_assignment_id bigint not null,
    evaluation_period_id bigint not null,
    question_bank_id bigint not null,
    submitted_at timestamptz not null default now(),
    client_version text,
    unique (student_id, teaching_assignment_id, evaluation_period_id),
    unique (id, question_bank_id),
    foreign key (student_id, teaching_assignment_id)
        references public.student_assignments (student_id, teaching_assignment_id) on delete restrict,
    foreign key (teaching_assignment_id, evaluation_period_id)
        references public.teaching_assignments (id, evaluation_period_id) on delete restrict,
    foreign key (evaluation_period_id, question_bank_id)
        references public.evaluation_period_instruments (evaluation_period_id, question_bank_id) on delete restrict
);

create index evaluation_submissions_student_id_idx
    on public.evaluation_submissions (student_id);
create index evaluation_submissions_teaching_assignment_id_idx
    on public.evaluation_submissions (teaching_assignment_id);
create index evaluation_submissions_evaluation_period_id_idx
    on public.evaluation_submissions (evaluation_period_id);
create index evaluation_submissions_question_bank_id_idx
    on public.evaluation_submissions (question_bank_id);

create table public.evaluation_responses (
    submission_id bigint not null,
    question_item_id bigint not null,
    question_bank_id bigint not null,
    rating_value smallint,
    text_value text,
    is_not_applicable boolean not null default false,
    created_at timestamptz not null default now(),
    primary key (submission_id, question_item_id),
    foreign key (submission_id, question_bank_id)
        references public.evaluation_submissions (id, question_bank_id) on delete cascade,
    foreign key (question_item_id, question_bank_id)
        references public.question_items (id, question_bank_id) on delete restrict,
    check (rating_value is null or rating_value between 1 and 5),
    check (
        (rating_value is not null and text_value is null and is_not_applicable = false)
        or (rating_value is null and nullif(btrim(text_value), '') is not null)
    )
);

create index evaluation_responses_question_item_id_idx
    on public.evaluation_responses (question_item_id);
create index evaluation_responses_question_bank_id_idx
    on public.evaluation_responses (question_bank_id);

create table public.submission_audit_events (
    id bigint generated always as identity primary key,
    submission_id bigint references public.evaluation_submissions (id) on delete set null,
    student_id uuid references public.students (profile_id) on delete set null,
    event_type text not null check (event_type in ('submitted', 'admin_voided')),
    event_at timestamptz not null default now(),
    details jsonb not null default '{}'::jsonb
);

create index submission_audit_events_submission_id_idx
    on public.submission_audit_events (submission_id);
create index submission_audit_events_student_id_idx
    on public.submission_audit_events (student_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger students_set_updated_at
before update on public.students
for each row execute function public.set_updated_at();

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (id, display_name)
    values (
        new.id,
        coalesce(
            nullif(btrim(new.raw_user_meta_data ->> 'display_name'), ''),
            split_part(coalesce(new.email, new.id::text), '@', 1)
        )
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

create or replace function public.guard_question_bank_changes()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if tg_op = 'DELETE' and old.status <> 'draft' then
        raise exception 'Published or retired question banks cannot be deleted';
    end if;

    if tg_op = 'UPDATE' then
        if old.status = 'published' and new.status not in ('published', 'retired') then
            raise exception 'A published question bank can only remain published or be retired';
        end if;

        if old.status = 'retired' and new.status <> 'retired' then
            raise exception 'A retired question bank cannot be reopened';
        end if;

        if old.status = 'draft' and new.status = 'retired' then
            raise exception 'A draft question bank must be published before it can be retired';
        end if;

        if old.status <> 'draft' and (
            new.code is distinct from old.code
            or new.version is distinct from old.version
            or new.school_level is distinct from old.school_level
            or new.title is distinct from old.title
            or new.published_at is distinct from old.published_at
        ) then
            raise exception 'Published question-bank identity and content metadata are immutable';
        end if;

        if old.status = 'draft' and new.status = 'published' and not exists (
            select 1 from public.question_items qi where qi.question_bank_id = old.id
        ) then
            raise exception 'A question bank must contain at least one item before publication';
        end if;
    end if;

    return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger question_banks_guard_changes
before update or delete on public.question_banks
for each row execute function public.guard_question_bank_changes();

create or replace function public.guard_question_item_changes()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    bank_status text;
    selected_bank_id bigint;
begin
    if tg_op = 'DELETE' then
        selected_bank_id := old.question_bank_id;
    else
        selected_bank_id := new.question_bank_id;
    end if;

    select qb.status
    into bank_status
    from public.question_banks qb
    where qb.id = selected_bank_id;

    if bank_status is distinct from 'draft' then
        raise exception 'Question items can be changed only while their question bank is in draft status';
    end if;

    return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger question_items_guard_changes
before insert or update or delete on public.question_items
for each row execute function public.guard_question_item_changes();

create or replace function public.validate_period_instrument_level()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    bank_level text;
begin
    select qb.school_level
    into bank_level
    from public.question_banks qb
    where qb.id = new.question_bank_id;

    if bank_level is distinct from new.school_level then
        raise exception 'The question bank and period instrument must use the same school level';
    end if;

    return new;
end;
$$;

create trigger period_instruments_validate_level
before insert or update on public.evaluation_period_instruments
for each row execute function public.validate_period_instrument_level();

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.profiles p
        where p.id = (select auth.uid())
          and p.role = 'admin'
          and p.is_active
    );
$$;

create or replace function public.submit_evaluation(
    p_teaching_assignment_id bigint,
    p_responses jsonb,
    p_client_version text default null
)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_student_id uuid := (select auth.uid());
    selected_period_id bigint;
    selected_question_bank_id bigint;
    expected_required_count integer;
    provided_required_count integer;
    new_submission_id bigint;
begin
    if current_student_id is null then
        raise exception 'Authentication is required';
    end if;

    if jsonb_typeof(p_responses) is distinct from 'array' then
        raise exception 'Responses must be supplied as a JSON array';
    end if;

    select ta.evaluation_period_id, epi.question_bank_id
    into selected_period_id, selected_question_bank_id
    from public.student_assignments sa
    join public.students s
      on s.profile_id = sa.student_id
    join public.profiles p
      on p.id = s.profile_id
    join public.teaching_assignments ta
      on ta.id = sa.teaching_assignment_id
    join public.sections sec
      on sec.id = ta.section_id
     and sec.id = s.section_id
    join public.evaluation_periods ep
      on ep.id = ta.evaluation_period_id
    join public.evaluation_period_instruments epi
      on epi.evaluation_period_id = ep.id
     and epi.school_level = sec.school_level
    join public.question_banks qb
      on qb.id = epi.question_bank_id
     and qb.school_level = sec.school_level
    where sa.student_id = current_student_id
      and sa.teaching_assignment_id = p_teaching_assignment_id
      and sa.is_active
      and p.is_active
      and ta.is_active
      and sec.is_active
      and ep.status = 'open'
      and now() >= ep.opens_at
      and now() < ep.closes_at
      and qb.status = 'published';

    if not found then
        raise exception 'No open authorized evaluation was found for this student and assignment';
    end if;

    if exists (
        select 1
        from jsonb_to_recordset(p_responses) as supplied(
            question_item_id bigint,
            rating_value smallint,
            text_value text
        )
        where supplied.question_item_id is null
    ) then
        raise exception 'Every response must include a question_item_id';
    end if;

    if (
        select count(*)
        from jsonb_to_recordset(p_responses) as supplied(
            question_item_id bigint,
            rating_value smallint,
            text_value text
        )
    ) <> (
        select count(distinct supplied.question_item_id)
        from jsonb_to_recordset(p_responses) as supplied(
            question_item_id bigint,
            rating_value smallint,
            text_value text
        )
    ) then
        raise exception 'A question can be answered only once per submission';
    end if;

    if exists (
        select 1
        from jsonb_to_recordset(p_responses) as supplied(
            question_item_id bigint,
            rating_value smallint,
            text_value text
        )
        left join public.question_items qi
          on qi.id = supplied.question_item_id
         and qi.question_bank_id = selected_question_bank_id
        where qi.id is null
           or (qi.response_type = 'likert_5' and (
                supplied.rating_value is null
                or supplied.rating_value not between 1 and 5
                or supplied.text_value is not null
           ))
           or (qi.response_type = 'text' and (
                supplied.rating_value is not null
                or nullif(btrim(supplied.text_value), '') is null
           ))
    ) then
        raise exception 'One or more responses do not match the active questionnaire';
    end if;

    select count(*)
    into expected_required_count
    from public.question_items qi
    where qi.question_bank_id = selected_question_bank_id
      and qi.is_required;

    select count(*)
    into provided_required_count
    from jsonb_to_recordset(p_responses) as supplied(
        question_item_id bigint,
        rating_value smallint,
        text_value text
    )
    join public.question_items qi
      on qi.id = supplied.question_item_id
     and qi.question_bank_id = selected_question_bank_id
    where qi.is_required;

    if provided_required_count <> expected_required_count then
        raise exception 'All required questions must be answered';
    end if;

    insert into public.evaluation_submissions (
        student_id,
        teaching_assignment_id,
        evaluation_period_id,
        question_bank_id,
        client_version
    )
    values (
        current_student_id,
        p_teaching_assignment_id,
        selected_period_id,
        selected_question_bank_id,
        nullif(btrim(p_client_version), '')
    )
    returning id into new_submission_id;

    insert into public.evaluation_responses (
        submission_id,
        question_item_id,
        question_bank_id,
        rating_value,
        text_value,
        is_not_applicable
    )
    select
        new_submission_id,
        supplied.question_item_id,
        selected_question_bank_id,
        supplied.rating_value,
        case when supplied.text_value is null then null else btrim(supplied.text_value) end,
        case
            when supplied.text_value is null then false
            else regexp_replace(lower(btrim(supplied.text_value)), '[^a-z0-9]+', '', 'g')
                 in ('na', 'notapplicable')
        end
    from jsonb_to_recordset(p_responses) as supplied(
        question_item_id bigint,
        rating_value smallint,
        text_value text
    );

    insert into public.submission_audit_events (
        submission_id,
        student_id,
        event_type,
        details
    )
    values (
        new_submission_id,
        current_student_id,
        'submitted',
        jsonb_build_object(
            'teaching_assignment_id', p_teaching_assignment_id,
            'evaluation_period_id', selected_period_id,
            'question_bank_id', selected_question_bank_id,
            'response_count', jsonb_array_length(p_responses)
        )
    );

    return new_submission_id;
exception
    when unique_violation then
        raise exception 'This evaluation has already been submitted';
end;
$$;

alter table public.profiles enable row level security;
alter table public.sections enable row level security;
alter table public.students enable row level security;
alter table public.teachers enable row level security;
alter table public.subjects enable row level security;
alter table public.evaluation_periods enable row level security;
alter table public.question_banks enable row level security;
alter table public.question_items enable row level security;
alter table public.evaluation_period_instruments enable row level security;
alter table public.teaching_assignments enable row level security;
alter table public.student_assignments enable row level security;
alter table public.evaluation_submissions enable row level security;
alter table public.evaluation_responses enable row level security;
alter table public.submission_audit_events enable row level security;

create policy profiles_select_own_or_admin on public.profiles
for select to authenticated
using (id = (select auth.uid()) or (select public.is_admin()));

create policy students_select_own_or_admin on public.students
for select to authenticated
using (profile_id = (select auth.uid()) or (select public.is_admin()));

create policy sections_select_assigned_or_admin on public.sections
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.students s
        where s.profile_id = (select auth.uid())
          and s.section_id = sections.id
    )
);

create policy teaching_assignments_select_assigned_or_admin on public.teaching_assignments
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.student_assignments sa
        where sa.student_id = (select auth.uid())
          and sa.teaching_assignment_id = teaching_assignments.id
          and sa.is_active
    )
);

create policy student_assignments_select_own_or_admin on public.student_assignments
for select to authenticated
using (student_id = (select auth.uid()) or (select public.is_admin()));

create policy teachers_select_assigned_or_admin on public.teachers
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.teaching_assignments ta
        join public.student_assignments sa
          on sa.teaching_assignment_id = ta.id
        where sa.student_id = (select auth.uid())
          and sa.is_active
          and ta.is_active
          and ta.teacher_id = teachers.id
    )
);

create policy subjects_select_assigned_or_admin on public.subjects
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.teaching_assignments ta
        join public.student_assignments sa
          on sa.teaching_assignment_id = ta.id
        where sa.student_id = (select auth.uid())
          and sa.is_active
          and ta.is_active
          and ta.subject_id = subjects.id
    )
);

create policy evaluation_periods_select_assigned_or_admin on public.evaluation_periods
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.teaching_assignments ta
        join public.student_assignments sa
          on sa.teaching_assignment_id = ta.id
        where sa.student_id = (select auth.uid())
          and sa.is_active
          and ta.is_active
          and ta.evaluation_period_id = evaluation_periods.id
    )
);

create policy period_instruments_select_assigned_or_admin on public.evaluation_period_instruments
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.teaching_assignments ta
        join public.student_assignments sa
          on sa.teaching_assignment_id = ta.id
        where sa.student_id = (select auth.uid())
          and sa.is_active
          and ta.is_active
          and ta.evaluation_period_id = evaluation_period_instruments.evaluation_period_id
    )
);

create policy question_banks_select_assigned_or_admin on public.question_banks
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.evaluation_period_instruments epi
        join public.teaching_assignments ta
          on ta.evaluation_period_id = epi.evaluation_period_id
        join public.student_assignments sa
          on sa.teaching_assignment_id = ta.id
        where sa.student_id = (select auth.uid())
          and sa.is_active
          and ta.is_active
          and epi.question_bank_id = question_banks.id
    )
);

create policy question_items_select_assigned_or_admin on public.question_items
for select to authenticated
using (
    (select public.is_admin())
    or exists (
        select 1
        from public.evaluation_period_instruments epi
        join public.teaching_assignments ta
          on ta.evaluation_period_id = epi.evaluation_period_id
        join public.student_assignments sa
          on sa.teaching_assignment_id = ta.id
        where sa.student_id = (select auth.uid())
          and sa.is_active
          and ta.is_active
          and epi.question_bank_id = question_items.question_bank_id
    )
);

create policy evaluation_submissions_select_own_or_admin on public.evaluation_submissions
for select to authenticated
using (student_id = (select auth.uid()) or (select public.is_admin()));

create policy evaluation_responses_select_admin on public.evaluation_responses
for select to authenticated
using ((select public.is_admin()));

create policy submission_audit_events_select_admin on public.submission_audit_events
for select to authenticated
using ((select public.is_admin()));

revoke all on public.profiles from anon, authenticated;
revoke all on public.sections from anon, authenticated;
revoke all on public.students from anon, authenticated;
revoke all on public.teachers from anon, authenticated;
revoke all on public.subjects from anon, authenticated;
revoke all on public.evaluation_periods from anon, authenticated;
revoke all on public.question_banks from anon, authenticated;
revoke all on public.question_items from anon, authenticated;
revoke all on public.evaluation_period_instruments from anon, authenticated;
revoke all on public.teaching_assignments from anon, authenticated;
revoke all on public.student_assignments from anon, authenticated;
revoke all on public.evaluation_submissions from anon, authenticated;
revoke all on public.evaluation_responses from anon, authenticated;
revoke all on public.submission_audit_events from anon, authenticated;

grant select on public.profiles to authenticated;
grant select on public.sections to authenticated;
grant select on public.students to authenticated;
grant select on public.teachers to authenticated;
grant select on public.subjects to authenticated;
grant select on public.evaluation_periods to authenticated;
grant select on public.question_banks to authenticated;
grant select on public.question_items to authenticated;
grant select on public.evaluation_period_instruments to authenticated;
grant select on public.teaching_assignments to authenticated;
grant select on public.student_assignments to authenticated;
grant select on public.evaluation_submissions to authenticated;
grant select on public.evaluation_responses to authenticated;
grant select on public.submission_audit_events to authenticated;

revoke execute on function public.set_updated_at() from public;
revoke execute on function public.handle_new_auth_user() from public;
revoke execute on function public.guard_question_bank_changes() from public;
revoke execute on function public.guard_question_item_changes() from public;
revoke execute on function public.validate_period_instrument_level() from public;
revoke execute on function public.is_admin() from public;
revoke execute on function public.submit_evaluation(bigint, jsonb, text) from public;

grant execute on function public.is_admin() to authenticated;
grant execute on function public.submit_evaluation(bigint, jsonb, text) to authenticated;
