-- Initial SHS and JHS instruments. Never edit a published version in place.
-- Create a new question bank version and remap only a future evaluation period.

do $$
declare
    shs_bank_id bigint;
    jhs_bank_id bigint;
begin
    insert into public.question_banks (code, version, school_level, title)
    values ('faculty-evaluation-shs', 1, 'SHS', 'SHS Faculty Evaluation')
    returning id into shs_bank_id;

    insert into public.question_items (
        question_bank_id,
        stable_key,
        section_key,
        prompt,
        response_type,
        position,
        is_required,
        use_for_rci
    )
    select
        shs_bank_id,
        item.stable_key,
        item.section_key,
        item.prompt,
        item.response_type,
        item.position,
        true,
        item.use_for_rci
    from jsonb_to_recordset($items$
    [
      {"stable_key":"SHS_TP_01","section_key":"teacher_performance","prompt":"My teacher starts and ends the class on time.","response_type":"likert_5","position":1,"use_for_rci":false},
      {"stable_key":"SHS_TP_02","section_key":"teacher_performance","prompt":"My teacher explains the objectives and instructions of our lessons clearly.","response_type":"likert_5","position":2,"use_for_rci":false},
      {"stable_key":"SHS_TP_03","section_key":"teacher_performance","prompt":"My teacher is very good at handling the students and managing the class.","response_type":"likert_5","position":3,"use_for_rci":false},
      {"stable_key":"SHS_TP_04","section_key":"teacher_performance","prompt":"My teacher provides different strategies to help us learn the lesson.","response_type":"likert_5","position":4,"use_for_rci":false},
      {"stable_key":"SHS_TP_05","section_key":"teacher_performance","prompt":"My teacher assigns assessments in advance that can be accomplished within the allotted time.","response_type":"likert_5","position":5,"use_for_rci":false},
      {"stable_key":"SHS_TP_06","section_key":"teacher_performance","prompt":"My teacher returns graded assessments regularly.","response_type":"likert_5","position":6,"use_for_rci":false},
      {"stable_key":"SHS_TP_07","section_key":"teacher_performance","prompt":"My teacher provides learning materials that are readily available or easily accessible.","response_type":"likert_5","position":7,"use_for_rci":false},
      {"stable_key":"SHS_TP_08","section_key":"teacher_performance","prompt":"My teacher is available for consultations.","response_type":"likert_5","position":8,"use_for_rci":false},
      {"stable_key":"SHS_TP_09","section_key":"teacher_performance","prompt":"My teacher replies to posts and messages during asynchronous sessions.","response_type":"likert_5","position":9,"use_for_rci":false},
      {"stable_key":"SHS_TP_10","section_key":"teacher_performance","prompt":"My teacher provides help for students who are having difficulties or are advanced in the lesson or activity.","response_type":"likert_5","position":10,"use_for_rci":false},
      {"stable_key":"SHS_SELF_01","section_key":"student_experience","prompt":"I feel respected and appreciated as a student in class.","response_type":"likert_5","position":1,"use_for_rci":false},
      {"stable_key":"SHS_SELF_02","section_key":"student_experience","prompt":"I felt my teacher is genuinely interested in my academic growth and success.","response_type":"likert_5","position":2,"use_for_rci":false},
      {"stable_key":"SHS_SELF_03","section_key":"student_experience","prompt":"I find it easy and comfortable to ask questions and seek help when needed.","response_type":"likert_5","position":3,"use_for_rci":false},
      {"stable_key":"SHS_SELF_04","section_key":"student_experience","prompt":"I am challenged by the subject and teacher in a way that promotes my learning and growth.","response_type":"likert_5","position":4,"use_for_rci":false},
      {"stable_key":"SHS_SELF_05","section_key":"student_experience","prompt":"I feel that the teacher encourages active participation and class engagement.","response_type":"likert_5","position":5,"use_for_rci":false},
      {"stable_key":"SHS_SELF_06","section_key":"student_experience","prompt":"I improved my understanding and performance through my teacher's constructive feedback.","response_type":"likert_5","position":6,"use_for_rci":false},
      {"stable_key":"SHS_SELF_07","section_key":"student_experience","prompt":"I am motivated to learn and excel in this class because of the teacher's teaching style.","response_type":"likert_5","position":7,"use_for_rci":false},
      {"stable_key":"SHS_SELF_08","section_key":"student_experience","prompt":"I felt my sharing of ideas and perspectives were valued in class.","response_type":"likert_5","position":8,"use_for_rci":false},
      {"stable_key":"SHS_SELF_09","section_key":"student_experience","prompt":"I developed a deeper understanding and appreciation of the subject taught by my teacher.","response_type":"likert_5","position":9,"use_for_rci":false},
      {"stable_key":"SHS_SELF_10","section_key":"student_experience","prompt":"I feel that this class has positively contributed to my overall learning experience at FEU High School.","response_type":"likert_5","position":10,"use_for_rci":false},
      {"stable_key":"SHS_SELF_11","section_key":"student_self_evaluation","prompt":"I always arrive on time and regularly for class.","response_type":"likert_5","position":1,"use_for_rci":true},
      {"stable_key":"SHS_SELF_12","section_key":"student_self_evaluation","prompt":"I actively participate in class discussions, asking questions and engaging with the material.","response_type":"likert_5","position":2,"use_for_rci":true},
      {"stable_key":"SHS_SELF_13","section_key":"student_self_evaluation","prompt":"I collaborate with classmates when working on class activities or subject requirements.","response_type":"likert_5","position":3,"use_for_rci":true},
      {"stable_key":"SHS_SELF_14","section_key":"student_self_evaluation","prompt":"I turn in my homework and assignments on time and in good quality.","response_type":"likert_5","position":4,"use_for_rci":true},
      {"stable_key":"SHS_SELF_15","section_key":"student_self_evaluation","prompt":"I exerted a lot of effort and dedication in studying for this class.","response_type":"likert_5","position":5,"use_for_rci":true},
      {"stable_key":"SHS_OPEN_01","section_key":"qualitative_feedback","prompt":"What strategies and practices did you appreciate the most about your teacher?","response_type":"text","position":1,"use_for_rci":false},
      {"stable_key":"SHS_OPEN_02","section_key":"qualitative_feedback","prompt":"What are some constructive suggestions you can give to help them handle students or teach better?","response_type":"text","position":2,"use_for_rci":false},
      {"stable_key":"SHS_OPEN_03","section_key":"qualitative_feedback","prompt":"Overall how was your learning experience with your teacher?","response_type":"text","position":3,"use_for_rci":false}
    ]
    $items$::jsonb) as item(
        stable_key text,
        section_key text,
        prompt text,
        response_type text,
        position smallint,
        use_for_rci boolean
    );

    update public.question_banks
    set status = 'published', published_at = now()
    where id = shs_bank_id;

    insert into public.question_banks (code, version, school_level, title)
    values ('faculty-evaluation-jhs', 1, 'JHS', 'JHS Faculty Evaluation')
    returning id into jhs_bank_id;

    insert into public.question_items (
        question_bank_id,
        stable_key,
        section_key,
        prompt,
        response_type,
        position,
        is_required,
        use_for_rci
    )
    select
        jhs_bank_id,
        item.stable_key,
        item.section_key,
        item.prompt,
        item.response_type,
        item.position,
        true,
        item.use_for_rci
    from jsonb_to_recordset($items$
    [
      {"stable_key":"JHS_TP_01","section_key":"teacher_performance","prompt":"My teacher starts and ends the class on time.","response_type":"likert_5","position":1,"use_for_rci":false},
      {"stable_key":"JHS_TP_02","section_key":"teacher_performance","prompt":"My teacher tells us what we're going to do in class and explains it so we can understand.","response_type":"likert_5","position":2,"use_for_rci":false},
      {"stable_key":"JHS_TP_03","section_key":"teacher_performance","prompt":"My teacher is really good at making sure the class behaves well and listens.","response_type":"likert_5","position":3,"use_for_rci":false},
      {"stable_key":"JHS_TP_04","section_key":"teacher_performance","prompt":"My teacher teaches us different ways to learn new things.","response_type":"likert_5","position":4,"use_for_rci":false},
      {"stable_key":"JHS_TP_05","section_key":"teacher_performance","prompt":"My teacher gives us activities to do that we can finish during class.","response_type":"likert_5","position":5,"use_for_rci":false},
      {"stable_key":"JHS_TP_06","section_key":"teacher_performance","prompt":"My teacher regularly returns our graded tests and activities.","response_type":"likert_5","position":6,"use_for_rci":false},
      {"stable_key":"JHS_TP_07","section_key":"teacher_performance","prompt":"My teacher gives us things to use for learning that are easy to get or understand.","response_type":"likert_5","position":7,"use_for_rci":false},
      {"stable_key":"JHS_TP_08","section_key":"teacher_performance","prompt":"My teacher is there to talk to if we need help.","response_type":"likert_5","position":8,"use_for_rci":false},
      {"stable_key":"JHS_TP_09","section_key":"teacher_performance","prompt":"My teacher writes back to us when we write or message them during online lessons.","response_type":"likert_5","position":9,"use_for_rci":false},
      {"stable_key":"JHS_TP_10","section_key":"teacher_performance","prompt":"My teacher helps students who are having problems with the lesson or students who want to learn more.","response_type":"likert_5","position":10,"use_for_rci":false},
      {"stable_key":"JHS_SELF_01","section_key":"student_experience","prompt":"I feel happy and safe when I'm in my teacher's class.","response_type":"likert_5","position":1,"use_for_rci":false},
      {"stable_key":"JHS_SELF_02","section_key":"student_experience","prompt":"I think my teacher really cares about how I do in school and wants me to do well.","response_type":"likert_5","position":2,"use_for_rci":false},
      {"stable_key":"JHS_SELF_03","section_key":"student_experience","prompt":"I can ask questions and get help easily, and it's not scary.","response_type":"likert_5","position":3,"use_for_rci":false},
      {"stable_key":"JHS_SELF_04","section_key":"student_experience","prompt":"I have to work hard in this class, but it helps me get better at things.","response_type":"likert_5","position":4,"use_for_rci":false},
      {"stable_key":"JHS_SELF_05","section_key":"student_experience","prompt":"My teacher likes it when we talk and do things in class.","response_type":"likert_5","position":5,"use_for_rci":false},
      {"stable_key":"JHS_SELF_06","section_key":"student_experience","prompt":"I get better at my assignments and tests when my teacher tells me how to do better.","response_type":"likert_5","position":6,"use_for_rci":false},
      {"stable_key":"JHS_SELF_07","section_key":"student_experience","prompt":"I want to learn and do my best because of my teacher.","response_type":"likert_5","position":7,"use_for_rci":false},
      {"stable_key":"JHS_SELF_08","section_key":"student_experience","prompt":"My teacher is happy when I share my ideas in class.","response_type":"likert_5","position":8,"use_for_rci":false},
      {"stable_key":"JHS_SELF_09","section_key":"student_experience","prompt":"I know more about the subject because of what my teacher teaches us.","response_type":"likert_5","position":9,"use_for_rci":false},
      {"stable_key":"JHS_SELF_10","section_key":"student_experience","prompt":"My teacher's class is fun, and it helps me learn a lot at FEU High School.","response_type":"likert_5","position":10,"use_for_rci":false},
      {"stable_key":"JHS_SELF_11","section_key":"student_self_evaluation","prompt":"I arrive on time for class every day.","response_type":"likert_5","position":1,"use_for_rci":true},
      {"stable_key":"JHS_SELF_12","section_key":"student_self_evaluation","prompt":"I actively participate in discussions and ask questions in class to learn more.","response_type":"likert_5","position":2,"use_for_rci":true},
      {"stable_key":"JHS_SELF_13","section_key":"student_self_evaluation","prompt":"I work with my classmates in class when we do projects together.","response_type":"likert_5","position":3,"use_for_rci":true},
      {"stable_key":"JHS_SELF_14","section_key":"student_self_evaluation","prompt":"I finish all my homework and give it to the teacher on time.","response_type":"likert_5","position":4,"use_for_rci":true},
      {"stable_key":"JHS_SELF_15","section_key":"student_self_evaluation","prompt":"I worked really hard when I was studying for this class.","response_type":"likert_5","position":5,"use_for_rci":true},
      {"stable_key":"JHS_OPEN_01","section_key":"qualitative_feedback","prompt":"What did you like the most about your teacher's way of teaching?","response_type":"text","position":1,"use_for_rci":false},
      {"stable_key":"JHS_OPEN_02","section_key":"qualitative_feedback","prompt":"How do you think your teacher can be better at helping students like you?","response_type":"text","position":2,"use_for_rci":false},
      {"stable_key":"JHS_OPEN_03","section_key":"qualitative_feedback","prompt":"Overall, how was your learning experience with your teacher?","response_type":"text","position":3,"use_for_rci":false}
    ]
    $items$::jsonb) as item(
        stable_key text,
        section_key text,
        prompt text,
        response_type text,
        position smallint,
        use_for_rci boolean
    );

    update public.question_banks
    set status = 'published', published_at = now()
    where id = jhs_bank_id;
end;
$$;
