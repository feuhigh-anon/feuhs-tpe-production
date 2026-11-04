-- Q2 subject catalog corrections and reference-aware cleanup of synthetic
-- ALPHA subject rows. Run in Supabase SQL Editor.
--
-- This updates only public.subjects. It does not import or activate the Q2
-- roster, create student accounts, or delete assignments/submissions.

begin;

insert into public.subjects (code, name, is_active)
values
  ('AE', 'Applied Economics', true),
  ('ARTS1', 'Arts 1 (Visual, Literary, Media, Applied, and Traditional Art)', true),
  ('BIO1', 'Biology 1', true),
  ('BM', 'Business Mathematics', true),
  ('BUS1', 'Business 1', true),
  ('CC1', 'Creative Composition 1', true),
  ('CHEM1', 'Chemistry 1', true),
  ('CL1', 'Contemporary Literature 1', true),
  ('CPAR', 'Contemporary Philippine Arts from the Regions', true),
  ('DIASS', 'Disciplines and Ideas in the Applied Social Sciences', true),
  ('EC', 'Effective Communication', true),
  ('ENT', 'Entrepreneurship', true),
  ('ET', 'Empowerment Technologies', true),
  ('FABM2', 'Fundamentals of Accountancy, Business, and Management 2', true),
  ('FITA', 'Filipino Identity Through the Arts', true),
  ('FPL', 'Filipino sa Piling Larang', true),
  ('GB1', 'General Biology 1', true),
  ('GC1', 'General Chemistry 1', true),
  ('GM', 'General Mathematics', true),
  ('GP1', 'General Physics 1', true),
  ('GS', 'General Science', true),
  ('G07AP', 'Grade 7 Araling Panlipunan', true),
  ('G07ENG', 'Grade 7 English', true),
  ('G07EP', 'Grade 7 Values Education', true),
  ('G07FIL', 'Grade 7 Filipino', true),
  ('G07MAPEH', 'Grade 7 Music, Arts, PE and Health', true),
  ('G07MATH', 'Grade 7 Mathematics', true),
  ('G07SCI', 'Grade 7 Science', true),
  ('G07TLE', 'Grade 7 Technology and Livelihood Education', true),
  ('G08AP', 'Grade 8 Araling Panlipunan', true),
  ('G08ENG', 'Grade 8 English', true),
  ('G08EP', 'Grade 8 Values Education', true),
  ('G08FIL', 'Grade 8 Filipino', true),
  ('G08MAPEH', 'Grade 8 Music, Arts, PE and Health', true),
  ('G08MATH', 'Grade 8 Mathematics', true),
  ('G08SCI', 'Grade 8 Science', true),
  ('G08TLE', 'Grade 8 Technology and Livelihood Education', true),
  ('G09AP', 'Grade 9 Araling Panlipunan', true),
  ('G09ENG', 'Grade 9 English', true),
  ('G09EP', 'Grade 9 Values Education', true),
  ('G09FIL', 'Grade 9 Filipino', true),
  ('G09MAPEH', 'Grade 9 Music, Arts, PE and Health', true),
  ('G09MATH', 'Grade 9 Mathematics', true),
  ('G09SCI', 'Grade 9 Science', true),
  ('G09TLE', 'Grade 9 Technology and Livelihood Education', true),
  ('G10AP', 'Grade 10 Araling Panlipunan', true),
  ('G10ENG', 'Grade 10 English', true),
  ('G10EP', 'Grade 10 Values Education', true),
  ('G10FIL', 'Grade 10 Filipino', true),
  ('G10MAPEH', 'Grade 10 Music, Arts, PE and Health', true),
  ('G10MATH', 'Grade 10 Mathematics', true),
  ('G10SCI', 'Grade 10 Science', true),
  ('G10TLE', 'Grade 10 Technology and Livelihood Education', true),
  ('HOPE4', 'Health Optimizing Physical Education 4', true),
  ('IOM', 'Introduction to Organization and Management', true),
  ('LCS', 'Life and Career Skills', true),
  ('MK', 'Mabisang Komunikasyon', true),
  ('PG', 'Philippine Governance', true),
  ('PHILO', 'Introduction to the Philosophy of the Human Person', true),
  ('PHYS1', 'Physics 1', true),
  ('PKLP', 'Pag-aaral ng Kasaysayan at Lipunang Pilipino', true),
  ('PPG', 'Philippine Politics and Governance', true),
  ('PR2A', 'Practical Research 2 (ABM)', true),
  ('PR2H', 'Practical Research 2 (HUMSS)', true),
  ('PR2S', 'Practical Research 2 (STEM)', true),
  ('TRIG1', 'Trigonometry 1', true),
  ('UCSP', 'Understanding Culture, Society, and Politics', true),
  ('WR', 'Introduction to World Religions and Belief Systems', true)
on conflict (code) do update
set name = excluded.name,
    is_active = excluded.is_active;

-- HOPE 3 is historical for this cycle; keep its row for old assignments but
-- prevent it from appearing as an active Q2 choice.
update public.subjects
set is_active = false
where code = 'HOPE3';

-- Preserve any synthetic subject still referenced by old assignments or
-- targets, but hide it from active selection. Delete only orphan catalog rows.
update public.subjects s
set is_active = false
where s.code like 'ALPHA-%'
  and (
    exists (select 1 from public.teaching_assignments ta where ta.subject_id = s.id)
    or exists (select 1 from public.evaluation_targets et where et.subject_id = s.id)
  );

delete from public.subjects s
where s.code like 'ALPHA-%'
  and not exists (select 1 from public.teaching_assignments ta where ta.subject_id = s.id)
  and not exists (select 1 from public.evaluation_targets et where et.subject_id = s.id);

commit;

-- Review rows that remain: these are referenced by historical records and were
-- deliberately deactivated rather than deleting their assignment history.
select code, name, is_active
from public.subjects
where code like 'ALPHA-%'
order by code;
