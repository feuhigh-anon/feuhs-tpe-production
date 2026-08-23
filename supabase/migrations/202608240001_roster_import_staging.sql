-- Batch-based roster staging, validation, and activation.
-- Staging tables contain private roster data and are accessible only through
-- the elevated service role. Students never read or write these tables.

create table public.roster_import_batches (
    id bigint generated always as identity primary key,
    batch_code text not null unique,
    evaluation_period_id bigint not null references public.evaluation_periods (id) on delete restrict,
    source_filename text not null,
    source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
    source_date date,
    status text not null default 'draft'
        check (status in ('draft', 'validated', 'activated', 'superseded', 'rejected')),
    validation_summary jsonb not null default '{}'::jsonb,
    notes text,
    created_by uuid references auth.users (id) on delete set null,
    created_at timestamptz not null default now(),
    validated_at timestamptz,
    activated_at timestamptz,
    check (
        (status = 'draft' and validated_at is null and activated_at is null)
        or (status = 'validated' and validated_at is not null and activated_at is null)
        or (status in ('activated', 'superseded') and validated_at is not null and activated_at is not null)
        or status = 'rejected'
    )
);

create index roster_import_batches_period_status_idx
    on public.roster_import_batches (evaluation_period_id, status);

create table public.roster_stage_sections (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    section_code text not null,
    canvas_section_name text not null,
    school_level text not null,
    grade_level smallint not null,
    strand text,
    source_row integer check (source_row is null or source_row > 1)
);

create index roster_stage_sections_batch_code_idx
    on public.roster_stage_sections (batch_id, section_code);

create table public.roster_stage_teachers (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    employee_number text not null,
    display_name text not null,
    email text,
    source_row integer check (source_row is null or source_row > 1)
);

create index roster_stage_teachers_batch_employee_idx
    on public.roster_stage_teachers (batch_id, employee_number);

create table public.roster_stage_subjects (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    subject_code text not null,
    subject_name text not null,
    source_row integer check (source_row is null or source_row > 1)
);

create index roster_stage_subjects_batch_code_idx
    on public.roster_stage_subjects (batch_id, subject_code);

create table public.roster_stage_students (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    student_number text not null,
    display_name text not null,
    email text not null,
    section_code text not null,
    source_row integer check (source_row is null or source_row > 1)
);

create index roster_stage_students_batch_number_idx
    on public.roster_stage_students (batch_id, student_number);
create index roster_stage_students_batch_email_idx
    on public.roster_stage_students (batch_id, lower(email));

create table public.roster_stage_teaching_assignments (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    assignment_key text not null,
    section_code text not null,
    subject_code text not null,
    teacher_employee_number text not null,
    source_row integer check (source_row is null or source_row > 1)
);

create index roster_stage_teaching_batch_key_idx
    on public.roster_stage_teaching_assignments (batch_id, assignment_key);
create index roster_stage_teaching_refs_idx
    on public.roster_stage_teaching_assignments (
        batch_id, section_code, subject_code, teacher_employee_number
    );

create table public.roster_stage_student_assignments (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    student_number text not null,
    assignment_key text not null,
    source_row integer check (source_row is null or source_row > 1)
);

create index roster_stage_student_assignment_student_idx
    on public.roster_stage_student_assignments (batch_id, student_number);
create index roster_stage_student_assignment_key_idx
    on public.roster_stage_student_assignments (batch_id, assignment_key);

create table public.roster_import_issues (
    id bigint generated always as identity primary key,
    batch_id bigint not null references public.roster_import_batches (id) on delete cascade,
    severity text not null check (severity in ('error', 'warning', 'info')),
    entity_type text not null,
    entity_key text,
    issue_code text not null,
    message text not null,
    source_row integer,
    created_at timestamptz not null default now()
);

create index roster_import_issues_batch_severity_idx
    on public.roster_import_issues (batch_id, severity);

alter table public.teaching_assignments
    add column roster_import_batch_id bigint
    references public.roster_import_batches (id) on delete set null;

alter table public.student_assignments
    add column roster_import_batch_id bigint
    references public.roster_import_batches (id) on delete set null;

create index teaching_assignments_roster_import_batch_idx
    on public.teaching_assignments (roster_import_batch_id);
create index student_assignments_roster_import_batch_idx
    on public.student_assignments (roster_import_batch_id);

create or replace function public.validate_roster_import_batch(p_batch_id bigint)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    selected_status text;
    error_count integer;
    warning_count integer;
    info_count integer;
    result jsonb;
begin
    select b.status
    into selected_status
    from public.roster_import_batches b
    where b.id = p_batch_id
    for update;

    if not found then
        raise exception 'Roster import batch % was not found', p_batch_id;
    end if;
    if selected_status in ('activated', 'superseded', 'rejected') then
        raise exception 'Roster import batch % cannot be validated from status %', p_batch_id, selected_status;
    end if;

    delete from public.roster_import_issues where batch_id = p_batch_id;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', entity_type, null, 'EMPTY_STAGE_TABLE',
           entity_type || ' staging table contains no rows'
    from (values
        ('section', (select count(*) from public.roster_stage_sections where batch_id = p_batch_id)),
        ('teacher', (select count(*) from public.roster_stage_teachers where batch_id = p_batch_id)),
        ('subject', (select count(*) from public.roster_stage_subjects where batch_id = p_batch_id)),
        ('student', (select count(*) from public.roster_stage_students where batch_id = p_batch_id)),
        ('teaching_assignment', (select count(*) from public.roster_stage_teaching_assignments where batch_id = p_batch_id)),
        ('student_assignment', (select count(*) from public.roster_stage_student_assignments where batch_id = p_batch_id))
    ) as staged(entity_type, row_count)
    where row_count = 0;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'section', s.section_code, 'INVALID_SECTION_LEVEL',
           'School level and grade level must form a valid JHS or SHS section', s.source_row
    from public.roster_stage_sections s
    where s.batch_id = p_batch_id
      and not (
          (s.school_level = 'JHS' and s.grade_level between 7 and 10)
          or (s.school_level = 'SHS' and s.grade_level between 11 and 12)
      );

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'section', s.section_code, 'BLANK_REQUIRED_FIELD',
           'Section code and Canvas section name must not be blank', s.source_row
    from public.roster_stage_sections s
    where s.batch_id = p_batch_id
      and (nullif(btrim(s.section_code), '') is null
           or nullif(btrim(s.canvas_section_name), '') is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'section', section_code, 'DUPLICATE_SECTION',
           'Section code occurs more than once in the staged batch'
    from public.roster_stage_sections
    where batch_id = p_batch_id
    group by section_code having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'teacher', employee_number, 'DUPLICATE_TEACHER',
           'Teacher employee number occurs more than once in the staged batch'
    from public.roster_stage_teachers
    where batch_id = p_batch_id
    group by employee_number having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'teacher', t.employee_number, 'BLANK_REQUIRED_FIELD',
           'Teacher employee number and display name must not be blank', t.source_row
    from public.roster_stage_teachers t
    where t.batch_id = p_batch_id
      and (nullif(btrim(t.employee_number), '') is null
           or nullif(btrim(t.display_name), '') is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'teacher', lower(email), 'DUPLICATE_TEACHER_EMAIL',
           'Teacher email occurs more than once in the staged batch'
    from public.roster_stage_teachers
    where batch_id = p_batch_id and nullif(btrim(email), '') is not null
    group by lower(email) having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'teacher', staged.employee_number,
           'TEACHER_EMAIL_CONFLICT',
           'Teacher email already belongs to a different employee number', staged.source_row
    from public.roster_stage_teachers staged
    join public.teachers existing on lower(existing.email) = lower(staged.email)
    where staged.batch_id = p_batch_id
      and nullif(btrim(staged.email), '') is not null
      and existing.employee_number is distinct from staged.employee_number;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'subject', subject_code, 'DUPLICATE_SUBJECT',
           'Subject code occurs more than once in the staged batch'
    from public.roster_stage_subjects
    where batch_id = p_batch_id
    group by subject_code having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'subject', s.subject_code, 'BLANK_REQUIRED_FIELD',
           'Subject code and name must not be blank', s.source_row
    from public.roster_stage_subjects s
    where s.batch_id = p_batch_id
      and (nullif(btrim(s.subject_code), '') is null
           or nullif(btrim(s.subject_name), '') is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'student', student_number, 'DUPLICATE_STUDENT',
           'Student number occurs more than once in the staged batch'
    from public.roster_stage_students
    where batch_id = p_batch_id
    group by student_number having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student', s.student_number, 'BLANK_REQUIRED_FIELD',
           'Student number, display name, and section code must not be blank', s.source_row
    from public.roster_stage_students s
    where s.batch_id = p_batch_id
      and (nullif(btrim(s.student_number), '') is null
           or nullif(btrim(s.display_name), '') is null
           or nullif(btrim(s.section_code), '') is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'student', lower(email), 'DUPLICATE_STUDENT_EMAIL',
           'Student email occurs more than once in the staged batch'
    from public.roster_stage_students
    where batch_id = p_batch_id
    group by lower(email) having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student', s.student_number, 'INVALID_STUDENT_EMAIL',
           'Student email is blank or does not resemble an email address', s.source_row
    from public.roster_stage_students s
    where s.batch_id = p_batch_id
      and (nullif(btrim(s.email), '') is null or position('@' in s.email) <= 1);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student', s.student_number, 'UNKNOWN_SECTION',
           'Student references a section absent from this staged batch', s.source_row
    from public.roster_stage_students s
    left join public.roster_stage_sections sec
      on sec.batch_id = s.batch_id and sec.section_code = s.section_code
    where s.batch_id = p_batch_id and sec.id is null;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'teaching_assignment', a.assignment_key,
           'UNKNOWN_ASSIGNMENT_REFERENCE',
           'Teaching assignment references an unknown section, subject, or teacher', a.source_row
    from public.roster_stage_teaching_assignments a
    left join public.roster_stage_sections sec
      on sec.batch_id = a.batch_id and sec.section_code = a.section_code
    left join public.roster_stage_subjects sub
      on sub.batch_id = a.batch_id and sub.subject_code = a.subject_code
    left join public.roster_stage_teachers t
      on t.batch_id = a.batch_id and t.employee_number = a.teacher_employee_number
    where a.batch_id = p_batch_id
      and (sec.id is null or sub.id is null or t.id is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'teaching_assignment', assignment_key,
           'DUPLICATE_ASSIGNMENT_KEY', 'Assignment key occurs more than once in the staged batch'
    from public.roster_stage_teaching_assignments
    where batch_id = p_batch_id
    group by assignment_key having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'teaching_assignment', a.assignment_key,
           'BLANK_REQUIRED_FIELD',
           'Assignment key, section, subject, and teacher must not be blank', a.source_row
    from public.roster_stage_teaching_assignments a
    where a.batch_id = p_batch_id
      and (nullif(btrim(a.assignment_key), '') is null
           or nullif(btrim(a.section_code), '') is null
           or nullif(btrim(a.subject_code), '') is null
           or nullif(btrim(a.teacher_employee_number), '') is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'teaching_assignment',
           section_code || '|' || subject_code || '|' || teacher_employee_number,
           'DUPLICATE_TEACHING_ASSIGNMENT',
           'The same section, subject, and teacher combination occurs more than once'
    from public.roster_stage_teaching_assignments
    where batch_id = p_batch_id
    group by section_code, subject_code, teacher_employee_number having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'info', 'teaching_assignment', section_code || '|' || subject_code,
           'SHARED_CLASS',
           'This section-subject has ' || count(distinct teacher_employee_number) ||
           ' staged teachers; student assignments remain teacher-specific'
    from public.roster_stage_teaching_assignments
    where batch_id = p_batch_id
    group by section_code, subject_code
    having count(distinct teacher_employee_number) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message)
    select p_batch_id, 'error', 'student_assignment',
           student_number || '|' || assignment_key, 'DUPLICATE_STUDENT_ASSIGNMENT',
           'Student-assignment pair occurs more than once in the staged batch'
    from public.roster_stage_student_assignments
    where batch_id = p_batch_id
    group by student_number, assignment_key having count(*) > 1;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student_assignment',
           sa.student_number || '|' || sa.assignment_key, 'BLANK_REQUIRED_FIELD',
           'Student number and assignment key must not be blank', sa.source_row
    from public.roster_stage_student_assignments sa
    where sa.batch_id = p_batch_id
      and (nullif(btrim(sa.student_number), '') is null
           or nullif(btrim(sa.assignment_key), '') is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student_assignment',
           sa.student_number || '|' || sa.assignment_key, 'UNKNOWN_STUDENT_ASSIGNMENT_REFERENCE',
           'Student assignment references an unknown student or teaching assignment', sa.source_row
    from public.roster_stage_student_assignments sa
    left join public.roster_stage_students s
      on s.batch_id = sa.batch_id and s.student_number = sa.student_number
    left join public.roster_stage_teaching_assignments a
      on a.batch_id = sa.batch_id and a.assignment_key = sa.assignment_key
    where sa.batch_id = p_batch_id and (s.id is null or a.id is null);

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student_assignment',
           sa.student_number || '|' || sa.assignment_key, 'CROSS_SECTION_ASSIGNMENT',
           'Student and teaching assignment belong to different sections', sa.source_row
    from public.roster_stage_student_assignments sa
    join public.roster_stage_students s
      on s.batch_id = sa.batch_id and s.student_number = sa.student_number
    join public.roster_stage_teaching_assignments a
      on a.batch_id = sa.batch_id and a.assignment_key = sa.assignment_key
    where sa.batch_id = p_batch_id and s.section_code <> a.section_code;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student', s.student_number, 'AUTH_USER_NOT_FOUND',
           'No Supabase Auth user matches the staged student email', s.source_row
    from public.roster_stage_students s
    left join auth.users u on lower(u.email) = lower(s.email)
    where s.batch_id = p_batch_id and u.id is null;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student', s.student_number, 'STUDENT_IDENTITY_CONFLICT',
           'Existing student number belongs to a different Auth user', s.source_row
    from public.roster_stage_students s
    join auth.users u on lower(u.email) = lower(s.email)
    join public.students existing on existing.student_number = s.student_number
    where s.batch_id = p_batch_id and existing.profile_id <> u.id;

    insert into public.roster_import_issues
        (batch_id, severity, entity_type, entity_key, issue_code, message, source_row)
    select p_batch_id, 'error', 'student', s.student_number, 'AUTH_IDENTITY_CONFLICT',
           'Auth user is already linked to a different student number', s.source_row
    from public.roster_stage_students s
    join auth.users u on lower(u.email) = lower(s.email)
    join public.students existing on existing.profile_id = u.id
    where s.batch_id = p_batch_id and existing.student_number <> s.student_number;

    select count(*) filter (where severity = 'error'),
           count(*) filter (where severity = 'warning'),
           count(*) filter (where severity = 'info')
    into error_count, warning_count, info_count
    from public.roster_import_issues
    where batch_id = p_batch_id;

    result := jsonb_build_object(
        'errors', error_count,
        'warnings', warning_count,
        'info', info_count,
        'sections', (select count(*) from public.roster_stage_sections where batch_id = p_batch_id),
        'teachers', (select count(*) from public.roster_stage_teachers where batch_id = p_batch_id),
        'subjects', (select count(*) from public.roster_stage_subjects where batch_id = p_batch_id),
        'students', (select count(*) from public.roster_stage_students where batch_id = p_batch_id),
        'teaching_assignments', (select count(*) from public.roster_stage_teaching_assignments where batch_id = p_batch_id),
        'student_assignments', (select count(*) from public.roster_stage_student_assignments where batch_id = p_batch_id)
    );

    update public.roster_import_batches
    set status = case when error_count = 0 then 'validated' else 'draft' end,
        validation_summary = result,
        validated_at = case when error_count = 0 then now() else null end
    where id = p_batch_id;

    return result;
end;
$$;

create or replace function public.activate_roster_import_batch(p_batch_id bigint)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    selected_period_id bigint;
    selected_period_status text;
    selected_status text;
    validation_result jsonb;
begin
    validation_result := public.validate_roster_import_batch(p_batch_id);
    if (validation_result ->> 'errors')::integer <> 0 then
        raise exception 'Roster import batch % has validation errors', p_batch_id;
    end if;

    select b.evaluation_period_id, b.status, ep.status
    into selected_period_id, selected_status, selected_period_status
    from public.roster_import_batches b
    join public.evaluation_periods ep on ep.id = b.evaluation_period_id
    where b.id = p_batch_id
    for update of b, ep;

    if selected_status <> 'validated' then
        raise exception 'Roster import batch % is not validated', p_batch_id;
    end if;
    if selected_period_status <> 'draft' then
        raise exception 'Roster batches can be activated only for draft evaluation periods';
    end if;
    if exists (
        select 1 from public.evaluation_submissions
        where evaluation_period_id = selected_period_id
    ) then
        raise exception 'A roster batch cannot be activated after submissions exist for the period';
    end if;

    insert into public.sections (code, school_level, grade_level, strand, is_active)
    select section_code, school_level, grade_level, nullif(btrim(strand), ''), true
    from public.roster_stage_sections where batch_id = p_batch_id
    on conflict (code) do update set
        school_level = excluded.school_level,
        grade_level = excluded.grade_level,
        strand = excluded.strand,
        is_active = true;

    insert into public.teachers (employee_number, display_name, email, is_active)
    select employee_number, display_name, nullif(btrim(email), ''), true
    from public.roster_stage_teachers where batch_id = p_batch_id
    on conflict (employee_number) do update set
        display_name = excluded.display_name,
        email = excluded.email,
        is_active = true;

    insert into public.subjects (code, name, is_active)
    select subject_code, subject_name, true
    from public.roster_stage_subjects where batch_id = p_batch_id
    on conflict (code) do update set name = excluded.name, is_active = true;

    insert into public.profiles (id, display_name, role, is_active)
    select u.id, s.display_name, 'student', true
    from public.roster_stage_students s
    join auth.users u on lower(u.email) = lower(s.email)
    where s.batch_id = p_batch_id
    on conflict (id) do update set
        display_name = excluded.display_name,
        is_active = true;

    insert into public.students (profile_id, student_number, section_id)
    select u.id, s.student_number, sec.id
    from public.roster_stage_students s
    join auth.users u on lower(u.email) = lower(s.email)
    join public.sections sec on sec.code = s.section_code
    where s.batch_id = p_batch_id
    on conflict (student_number) do update set
        section_id = excluded.section_id,
        updated_at = now();

    update public.teaching_assignments
    set is_active = false
    where evaluation_period_id = selected_period_id;

    insert into public.teaching_assignments (
        evaluation_period_id, section_id, subject_id, teacher_id,
        is_active, roster_import_batch_id
    )
    select selected_period_id, sec.id, sub.id, t.id, true, p_batch_id
    from public.roster_stage_teaching_assignments a
    join public.sections sec on sec.code = a.section_code
    join public.subjects sub on sub.code = a.subject_code
    join public.teachers t on t.employee_number = a.teacher_employee_number
    where a.batch_id = p_batch_id
    on conflict (evaluation_period_id, section_id, subject_id, teacher_id)
    do update set is_active = true, roster_import_batch_id = excluded.roster_import_batch_id;

    update public.student_assignments sa
    set is_active = false
    from public.teaching_assignments ta
    where ta.id = sa.teaching_assignment_id
      and ta.evaluation_period_id = selected_period_id;

    insert into public.student_assignments (
        student_id, teaching_assignment_id, is_active, roster_import_batch_id
    )
    select st.profile_id, ta.id, true, p_batch_id
    from public.roster_stage_student_assignments sa
    join public.roster_stage_students staged_student
      on staged_student.batch_id = sa.batch_id
     and staged_student.student_number = sa.student_number
    join public.students st on st.student_number = staged_student.student_number
    join public.roster_stage_teaching_assignments staged_assignment
      on staged_assignment.batch_id = sa.batch_id
     and staged_assignment.assignment_key = sa.assignment_key
    join public.sections sec on sec.code = staged_assignment.section_code
    join public.subjects sub on sub.code = staged_assignment.subject_code
    join public.teachers t
      on t.employee_number = staged_assignment.teacher_employee_number
    join public.teaching_assignments ta
      on ta.evaluation_period_id = selected_period_id
     and ta.section_id = sec.id
     and ta.subject_id = sub.id
     and ta.teacher_id = t.id
    where sa.batch_id = p_batch_id
    on conflict (student_id, teaching_assignment_id)
    do update set is_active = true, assigned_at = now(),
                  roster_import_batch_id = excluded.roster_import_batch_id;

    update public.roster_import_batches
    set status = 'superseded'
    where evaluation_period_id = selected_period_id
      and status = 'activated'
      and id <> p_batch_id;

    update public.roster_import_batches
    set status = 'activated', activated_at = now()
    where id = p_batch_id;

    return validation_result || jsonb_build_object(
        'batch_id', p_batch_id,
        'evaluation_period_id', selected_period_id,
        'status', 'activated'
    );
end;
$$;

alter table public.roster_import_batches enable row level security;
alter table public.roster_stage_sections enable row level security;
alter table public.roster_stage_teachers enable row level security;
alter table public.roster_stage_subjects enable row level security;
alter table public.roster_stage_students enable row level security;
alter table public.roster_stage_teaching_assignments enable row level security;
alter table public.roster_stage_student_assignments enable row level security;
alter table public.roster_import_issues enable row level security;

revoke all on public.roster_import_batches from anon, authenticated;
revoke all on public.roster_stage_sections from anon, authenticated;
revoke all on public.roster_stage_teachers from anon, authenticated;
revoke all on public.roster_stage_subjects from anon, authenticated;
revoke all on public.roster_stage_students from anon, authenticated;
revoke all on public.roster_stage_teaching_assignments from anon, authenticated;
revoke all on public.roster_stage_student_assignments from anon, authenticated;
revoke all on public.roster_import_issues from anon, authenticated;

grant all on public.roster_import_batches to service_role;
grant all on public.roster_stage_sections to service_role;
grant all on public.roster_stage_teachers to service_role;
grant all on public.roster_stage_subjects to service_role;
grant all on public.roster_stage_students to service_role;
grant all on public.roster_stage_teaching_assignments to service_role;
grant all on public.roster_stage_student_assignments to service_role;
grant all on public.roster_import_issues to service_role;
grant usage, select on all sequences in schema public to service_role;

revoke execute on function public.validate_roster_import_batch(bigint) from public, anon, authenticated;
revoke execute on function public.activate_roster_import_batch(bigint) from public, anon, authenticated;
grant execute on function public.validate_roster_import_batch(bigint) to service_role;
grant execute on function public.activate_roster_import_batch(bigint) to service_role;
