"""Build a compact, private Q2 roster bundle from reviewed assignments and students.

The reviewed SubjectLoads sheet is authoritative. Canvas is used only for the
explicit Collado/Galang additions and the remaining missing JHS teacher IDs.
An optional student roster workbook supplies student numbers and official
sections. This script never edits its source workbooks or contacts Supabase.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook


COLLADO_ID = "202290226"
GALANG_ID = "202290227"
MAYORGA_ID = "202290188"
SACDAL_ID = "202290176"
SANTIAGO_ID = "202290192"
COLLADO_SECTIONS = ("12S03a", "12S04b", "12S05b", "12S06b", "12S07b", "12S08b", "12S09b")
GALANG_SECTIONS = {"G07-1": "G07SCI", "G08-1": "G08SCI", "G10-1": "G10SCI"}
OMIT_SCIENCE_SECTIONS = {"G07-2", "G08-2", "G10-2"}
PERIOD_CODE = "SY2026-2027-Q2"
SEED = 20261023

# Canonical names are kept in sync with the Supabase subject catalog and the
# current Canvas course titles. SubjectLoads remains authoritative for which
# teacher is assigned to each section; these rules normalize only course
# identity and display text for the upload payload.
SUBJECT_NAMES = {
    "AE": "Applied Economics",
    "ARTS1": "Arts 1 (Visual, Literary, Media, Applied, and Traditional Art)",
    "BIO1": "Biology 1",
    "BM": "Business Mathematics",
    "BUS1": "Business 1",
    "CC1": "Creative Composition 1",
    "CHEM1": "Chemistry 1",
    "CL1": "Contemporary Literature 1",
    "CPAR": "Contemporary Philippine Arts from the Regions",
    "DIASS": "Disciplines and Ideas in the Applied Social Sciences",
    "EC": "Effective Communication",
    "ENT": "Entrepreneurship",
    "ET": "Empowerment Technologies",
    "FABM2": "Fundamentals of Accountancy, Business, and Management 2",
    "FITA": "Filipino Identity Through the Arts",
    "FPL": "Filipino sa Piling Larang",
    "GB1": "General Biology 1",
    "GC1": "General Chemistry 1",
    "GM": "General Mathematics",
    "GP1": "General Physics 1",
    "GS": "General Science",
    "HOPE4": "Health Optimizing Physical Education 4",
    "IOM": "Introduction to Organization and Management",
    "LCS": "Life and Career Skills",
    "MK": "Mabisang Komunikasyon",
    "PG": "Philippine Governance",
    "PHILO": "Introduction to the Philosophy of the Human Person",
    "PHYS1": "Physics 1",
    "PKLP": "Pag-aaral ng Kasaysayan at Lipunang Pilipino",
    "PPG": "Philippine Politics and Governance",
    "PR2A": "Practical Research 2 (ABM)",
    "PR2H": "Practical Research 2 (HUMSS)",
    "PR2S": "Practical Research 2 (STEM)",
    "TRIG1": "Trigonometry 1",
    "UCSP": "Understanding Culture, Society, and Politics",
    "WR": "Introduction to World Religions and Belief Systems",
}

for _grade in range(7, 11):
    _prefix = f"G{_grade:02d}"
    for _suffix, _name in {
        "AP": "Araling Panlipunan",
        "ENG": "English",
        "EP": "Values Education",
        "FIL": "Filipino",
        "MAPEH": "Music, Arts, PE and Health",
        "MATH": "Mathematics",
        "SCI": "Science",
        "TLE": "Technology and Livelihood Education",
    }.items():
        SUBJECT_NAMES[_prefix + _suffix] = f"Grade {_grade} {_name}"


def normalize_subject(section_code, subject_code, subject_name):
    """Return the canonical Q2 code and display name for a reviewed load."""
    code = subject_code
    if code == "BASACC":
        # The user confirmed Business 1 and Basic Accounting are the same.
        code = "BUS1"
    elif code == "HOPE3":
        # HOPE 3 remains historical in the catalog; Q2 uses a distinct code.
        code = "HOPE4"
    elif code == "PR2":
        # Strand/department variant. User confirmed GAS PR teachers are the
        # ABM teachers; SubjectLoads retains each teacher-section assignment.
        if section_code.startswith(("12A", "12G")):
            code = "PR2A"
        elif section_code.startswith("12H"):
            code = "PR2H"
        elif section_code.startswith("12S"):
            code = "PR2S"
        else:
            raise ValueError(f"Cannot resolve Practical Research 2 variant for {section_code}")
    return code, SUBJECT_NAMES.get(code, subject_name)


def clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def private_csv(path: Path, rows, columns):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    path.chmod(0o600)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sheets(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    data = {}
    try:
        for sheet_name in ("Students", "Teachers", "SubjectLoads", "Homeroom", "Programs", "SectionGroups", "Settings"):
            it = wb[sheet_name].iter_rows(values_only=True)
            headers = [clean(x) for x in next(it)]
            data[sheet_name] = [
                {k: clean(v) for k, v in zip(headers, row) if k}
                for row in it if any(v is not None for v in row)
            ]
    finally:
        wb.close()
    return data


def load_external_students(path: Path, reviewed_students):
    """Read a separate authoritative student/section export without editing it.

    Section codes come from the reviewed roster's source-section crosswalk.
    Political Science is an updated label for the existing Political Studies
    section names; the official section codes remain 11PS01 and 11PS02.
    """
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        headers = [clean(x) for x in next(it)]
        column = {header: i for i, header in enumerate(headers) if header}
        required = {"Student Number", "Year Level", "K12 - Section"}
        if not required <= set(column):
            raise ValueError("External student roster is missing required columns: " + ", ".join(sorted(required-set(column))))

        section_to_code = {}
        for row in reviewed_students:
            label = clean(row.get("source_section"))
            code = clean(row.get("section_code"))
            if not label or not code:
                continue
            if label in section_to_code and section_to_code[label] != code:
                raise ValueError(f"Reviewed roster has conflicting codes for source section {label}")
            section_to_code[label] = code

        aliases = {
            "11ASSH-Political Science Sec. 1 (S.Y.26-27)": "11ASSH-Political Studies Sec. 1 (S.Y.26-27)",
            "11ASSH-Political Science Sec. 2 (S.Y.26-27)": "11ASSH-Political Studies Sec. 2 (S.Y.26-27)",
        }
        students = []
        seen = set()
        for row in it:
            if not any(value is not None for value in row):
                continue
            sid = clean(row[column["Student Number"]])
            level = clean(row[column["Year Level"]])
            label = clean(row[column["K12 - Section"]])
            if not sid:
                raise ValueError("External student roster contains a blank student number")
            if sid in seen:
                raise ValueError(f"External student roster contains duplicate student number {sid}")
            seen.add(sid)
            code = section_to_code.get(aliases.get(label, label))
            if not code:
                raise ValueError(f"External student roster section is not mapped in the reviewed roster: {label}")
            expected_level = "Grade " + str(int(code[1:3])) if re.fullmatch(r"G\d{2}-\d", code) else f"Grade {code[:2]}" if code[:2].isdigit() else ""
            if expected_level and level != expected_level:
                raise ValueError(f"Student {sid} year level {level} conflicts with section {code}")
            students.append({"student_number": sid, "section_code": code})
        if not students:
            raise ValueError("External student roster contains no student rows")
        return students
    finally:
        wb.close()


def load_canvas(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        def read_csv(name):
            with zf.open(name) as raw:
                return list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")))
        users = read_csv("users.csv")
        courses = read_csv("courses.csv")
        sections = read_csv("sections.csv")
        enrollments = read_csv("enrollments.csv")
    user_by_canvas_id = {r["canvas_user_id"]: r for r in users}
    expected = {
        COLLADO_ID: "Mark Arthur Collado",
        GALANG_ID: "John Paul Galang",
        MAYORGA_ID: "Francesca Venisse Mayorga",
        SACDAL_ID: "Genrie Edward Sacdal",
        SANTIAGO_ID: "Shantal Santiago",
    }
    identities = {}
    for emp_id, full_name in expected.items():
        matches = [u for u in users if re.sub(r"^H", "", clean(u.get("user_id"))) == emp_id]
        if len(matches) != 1 or clean(matches[0].get("full_name")) != full_name:
            raise ValueError(f"Canvas identity check failed for employee {emp_id}")
        u = matches[0]
        identities[emp_id] = {"employee_number": emp_id, "display_name": full_name,
                              "email": clean(u.get("email"))}
    target_terms = {"SY_2026_S1_SHS_OFFICIAL", "SY_2026_JHS_OFFICIAL"}
    term_courses = {c["canvas_course_id"]: c for c in courses if c.get("term_id") in target_terms}
    section_rows = [s for s in sections if s.get("canvas_course_id") in term_courses]
    section_names = defaultdict(list)
    for row in section_rows:
        section_names[row["canvas_course_id"]].append(row["name"])
    # Confirm the user-specified course and all seven Canvas section labels.
    cc = [c for c in term_courses.values() if "UCSP_NEWSOCSCIT3" in (c.get("course_id", "") + c.get("short_name", ""))]
    if len(cc) != 1:
        raise ValueError("Expected exactly one in-term UCSP_NEWSOCSCIT3 course")
    c = cc[0]
    collado_enrollments = [e for e in enrollments if e.get("canvas_course_id") == c["canvas_course_id"]
                           and e.get("status") == "active" and e.get("role", "").lower() == "teacher"
                           and re.sub(r"^H", "", clean(user_by_canvas_id.get(e.get("canvas_user_id"), {}).get("user_id"))) == COLLADO_ID]
    expected_labels = {"12STEM-3A", "12STEM-4B", "12STEM-5B", "12STEM-6B", "12STEM-7B", "12STEM-8B", "12STEM-9B"}
    if not collado_enrollments or set(section_names[c["canvas_course_id"]]) != expected_labels:
        raise ValueError("Collado course enrollment or section list differs from the confirmed roster map")
    # Confirm the remaining JHS teacher-handle resolutions and Galang's
    # section-linked science enrollments within the requested active term.
    section_name_by_id = {s["canvas_section_id"]: s["name"] for s in section_rows}
    def require_course_handle(fragment, employee_id, expected_sections):
        found = [course for course in term_courses.values()
                 if course.get("term_id") == "SY_2026_JHS_OFFICIAL"
                 and fragment in course.get("course_id", "")]
        if len(found) != 1:
            raise ValueError(f"Canvas course handle check failed: {fragment}")
        course = found[0]
        course_teachers = [e for e in enrollments if e.get("canvas_course_id") == course["canvas_course_id"]
                           and e.get("status") == "active" and e.get("role", "").lower() == "teacher"
                           and re.sub(r"^H", "", clean(user_by_canvas_id.get(e.get("canvas_user_id"), {}).get("user_id"))) == employee_id]
        course_labels = set(section_names[course["canvas_course_id"]])
        if not course_teachers or not set(expected_sections) <= course_labels:
            raise ValueError(f"Canvas teacher/section evidence failed: {fragment}")
    require_course_handle("G08EP_FVMAYORGA", MAYORGA_ID, {"Grade 8-1", "Grade 8-2"})
    require_course_handle("G09TLE_GESACDAL", SACDAL_ID, {"Grade 9-1", "Grade 9-2"})
    require_course_handle("G10TLE_SMSANTIAGO", SANTIAGO_ID, {"Grade 10-1", "Grade 10-2"})
    for grade, sec_label in (("G07SCI", "Grade 7-1"), ("G08SCI", "Grade 8-1"), ("G10SCI", "Grade 10-1")):
        matching = [e for e in enrollments if e.get("status") == "active" and e.get("role", "").lower() == "teacher"
                    and e.get("canvas_course_id") in term_courses
                    and grade in term_courses[e["canvas_course_id"]].get("course_id", "")
                    and re.sub(r"^H", "", clean(user_by_canvas_id.get(e.get("canvas_user_id"), {}).get("user_id"))) == GALANG_ID
                    and section_name_by_id.get(e.get("canvas_section_id")) == sec_label]
        if not matching:
            raise ValueError(f"Canvas section-linked Galang enrollment missing: {grade} {sec_label}")
    # Exclude Canvas small-class/tutorial courses by their exact `_SM` suffix.
    # This token check deliberately does not match faculty handles like SMSANTIAGO.
    sm_courses = []
    for course in courses:
        if course.get("term_id") not in target_terms:
            continue
        identifiers = (clean(course.get("course_id")), clean(course.get("short_name")))
        if not any(re.search(r"(?:^|_)SM$", value, flags=re.I) for value in identifiers):
            continue
        cid = course["canvas_course_id"]
        course_sections = [s for s in sections if s.get("canvas_course_id") == cid]
        course_section_names = sorted(clean(s.get("name")) for s in course_sections)
        active_students = sum(1 for e in enrollments if e.get("canvas_course_id") == cid
                              and e.get("status") == "active" and e.get("role", "").lower() == "student")
        sm_courses.append({"canvas_course_id": cid, "course_id": course.get("course_id", ""),
                           "short_name": course.get("short_name", ""), "subject_name": course.get("long_name", ""),
                           "term_id": course.get("term_id", ""), "course_status": course.get("status", ""),
                           "section_count": len(course_sections), "canvas_section_names": " | ".join(course_section_names),
                           "active_student_enrollments": active_students,
                           "evaluation_status": "excluded: Canvas _SM course"})
    return identities, sha(zip_path), sm_courses


def build_loads(data, identities):
    teachers = {r["employee_number"]: r for r in data["Teachers"] if r.get("employee_number")}
    for emp_id, row in identities.items():
        teachers[emp_id] = row
    raw = data["SubjectLoads"]
    excluded = []
    active = []
    # Workbook decisions and priority/mode tags take precedence over Canvas.
    for r in raw:
        reason = ""
        if r.get("decision") in {"remove", "not include", "exclude"}:
            reason = "subjectLoads decision: " + r["decision"]
        elif r.get("assignment_mode") not in {"regular", "overload"}:
            reason = "non-primary assignment mode: " + r.get("assignment_mode", "")
        elif r.get("allocation_priority") not in {"", "primary"}:
            reason = "secondary allocation priority"
        if reason:
            excluded.append({"section_code": r.get("section_code", ""), "subject_code": r.get("subject_code", ""),
                             "teacher_employee_number": r.get("teacher_employee_number", ""), "teacher_alias": r.get("teacher_alias", ""),
                             "reason": reason, "review_notes": r.get("review_notes", "")})
            continue
        active.append({**r})

    resolved = []
    for r in active:
        sec, code = r.get("section_code", ""), r.get("subject_code", "")
        tid = r.get("teacher_employee_number", "")
        resolution_note = "SubjectLoads employee number"
        if sec in OMIT_SCIENCE_SECTIONS and code in {"G07SCI", "G08SCI", "G10SCI"}:
            excluded.append({"section_code": sec, "subject_code": code, "teacher_employee_number": tid,
                             "teacher_alias": r.get("teacher_alias", ""), "reason": "user-directed omit of Science section 2 load"})
            continue
        if sec in COLLADO_SECTIONS and code == "UCSP":
            excluded.append({"section_code": sec, "subject_code": code, "teacher_employee_number": tid,
                             "teacher_alias": r.get("teacher_alias", ""), "reason": "replaced by Collado per user direction"})
            continue
        if not tid:
            if (sec, code) in {(s, c) for s, c in GALANG_SECTIONS.items()}:
                tid = GALANG_ID
                resolution_note = "Canvas section-linked enrollment; user confirmed Galang"
            elif sec == "G08-2" and (code == "" or r.get("subject_name") == "Mayorga"):
                tid, code = MAYORGA_ID, "G08EP"
                r["subject_name"] = "Values Education"
                resolution_note = "Canvas course handle FVMAYORGA; Grade 8-2 section"
            elif sec in {"G09-1", "G09-2"} and code == "G09TLE":
                # Canvas course_id uses the faculty handle GESACDAL for Grade 9 TLE.
                tid = SACDAL_ID
                resolution_note = "Canvas course handle GESACDAL; Grade 9 TLE"
            elif sec in {"G10-1", "G10-2"} and code == "G10TLE":
                # Canvas course_id uses the faculty handle SMSANTIAGO for Grade 10 TLE.
                tid = SANTIAGO_ID
                resolution_note = "Canvas course handle SMSANTIAGO; Grade 10 TLE"
            else:
                raise ValueError(f"Unresolved active teacher identity: {sec} / {code} / {r.get('teacher_alias')}")
        if tid not in teachers:
            raise ValueError(f"Active load references unknown employee number {tid}")
        source_code = code
        code, subject_name = normalize_subject(sec, code, r.get("subject_name", ""))
        if code != source_code:
            resolution_note += f"; normalized Q2 subject code {source_code} to {code}"
        resolved.append({"assignment_key": f"{sec}|{code}|{tid}", "section_code": sec, "subject_code": code,
                         "subject_name": subject_name, "teacher_employee_number": tid,
                         "assignment_mode": r.get("assignment_mode", "regular"),
                         "allocation_priority": "primary", "source_note": resolution_note})

    # Collado is the sole UCSP evaluation teacher on all seven linked sections.
    for sec in COLLADO_SECTIONS:
        resolved.append({"assignment_key": f"{sec}|UCSP|{COLLADO_ID}", "section_code": sec, "subject_code": "UCSP",
                         "subject_name": "Understanding Culture, Society, and Politics", "teacher_employee_number": COLLADO_ID,
                         "assignment_mode": "regular", "allocation_priority": "primary",
                         "source_note": "Canvas course UCSP_NEWSOCSCIT3; user-confirmed teacher"})
    for sec, code in GALANG_SECTIONS.items():
        resolved.append({"assignment_key": f"{sec}|{code}|{GALANG_ID}", "section_code": sec, "subject_code": code,
                         "subject_name": SUBJECT_NAMES[code], "teacher_employee_number": GALANG_ID,
                         "assignment_mode": "regular", "allocation_priority": "primary",
                         "source_note": "Canvas section-linked enrollment; user-confirmed teacher"})

    # Exact duplicate rows tagged "maintain one" collapse to one assignment.
    unique = {}
    for r in resolved:
        unique[(r["section_code"], r["subject_code"], r["teacher_employee_number"])] = r
    loads = list(unique.values())
    by_pair = defaultdict(list)
    for r in loads:
        by_pair[(r["section_code"], r["subject_code"])].append(r)
    collisions = {key: rows for key, rows in by_pair.items() if len(rows) > 1}
    if collisions:
        detail = "; ".join(f"{sec}/{sub}: {[r['teacher_employee_number'] for r in rows]}" for (sec, sub), rows in collisions.items())
        raise ValueError("More than one active teacher remains for a section/subject: " + detail)
    return loads, teachers, excluded


def allocation(students, loads, homes, seed=SEED, minimum=20, maximum=96):
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix, csr_matrix, hstack, vstack

    students = sorted(students, key=lambda r: r["student_number"])
    by_sec = defaultdict(list)
    for load in loads:
        by_sec[load["section_code"]].append(load)
    candidates, context = {}, {}
    student_by_id = {s["student_number"]: s for s in students}
    for student in students:
        sid, sec = student["student_number"], student["teaching_section_code"]
        by_teacher = defaultdict(list)
        for load in by_sec[sec]:
            by_teacher[load["teacher_employee_number"]].append(load)
        if len(by_teacher) < 2:
            raise ValueError(f"Section {sec} has fewer than two distinct eligible subject teachers")
        candidates[sid] = set(by_teacher)
        for tid, options in by_teacher.items():
            context[(sid, tid)] = min(options, key=lambda row: hashlib.sha256(
                f"{seed}|{sid}|{row['assignment_key']}".encode()).digest())

    regular_students, advisory_students = defaultdict(set), defaultdict(set)
    for student in students:
        sid, sec = student["student_number"], student["teaching_section_code"]
        adviser = homes[sec]["adviser_employee_number"]
        for tid in candidates[sid]:
            if tid == adviser:
                advisory_students[tid].add(sid)
            else:
                regular_students[tid].add(sid)

    pairs = [(sid, tid) for sid in sorted(candidates) for tid in sorted(candidates[sid])]
    teacher_ids = sorted({tid for _, tid in pairs})
    student_ids = [s["student_number"] for s in students]
    si, ti = {s:i for i,s in enumerate(student_ids)}, {t:i for i,t in enumerate(teacher_ids)}
    ns, nt, n = len(student_ids), len(teacher_ids), len(pairs)
    pools = Counter(t for cs in candidates.values() for t in cs)
    lower, upper = {}, {}
    for t in teacher_ids:
        lower[t] = min(minimum, pools[t]) if regular_students[t] else 0
        upper[t] = min(maximum, pools[t])

    total = 2 * ns
    target = {t:float(lower[t]) for t in teacher_ids}
    remaining = total - sum(target.values())
    if remaining < 0:
        raise ValueError("Teacher invitation minimums exceed the available subject targets")
    active = {t for t in teacher_ids if target[t] < upper[t]}
    while active and remaining > 1e-8:
        layer = remaining / len(active)
        saturated = {t for t in active if target[t] + layer >= upper[t]}
        if not saturated:
            for t in active:
                target[t] += layer
            remaining = 0
            break
        for t in saturated:
            delta = upper[t] - target[t]
            target[t] += delta
            remaining -= delta
        active -= saturated
    if remaining > 1e-6:
        raise ValueError("Teacher maximums cannot cover all two-subject targets")

    rounded = {t:int(math.floor(target[t])) for t in teacher_ids}
    remainder = total - sum(rounded.values())
    for t in sorted(teacher_ids, key=lambda t: (-(target[t]-rounded[t]),t))[:remainder]:
        rounded[t] += 1

    # Student assignment constraints plus soft balancing around the declared
    # invitation targets. There is no forced assignment based on teacher load
    # size; Canvas _SM courses are outside the eligible SubjectLoads set.
    eq = lil_matrix((ns+nt,n+2*nt))
    for j,(sid,tid) in enumerate(pairs):
        eq[si[sid],j]=1
        eq[ns+ti[tid],j]=1
    for tid,idx in ti.items():
        eq[ns+idx,n+2*idx]=-1
        eq[ns+idx,n+2*idx+1]=1
    rhs=[2]*ns+[rounded[t] for t in teacher_ids]
    incidence=eq[ns:,:n].tocsr()
    zero=csr_matrix((nt,2*nt))
    aub=vstack([hstack([incidence,zero]),hstack([-incidence,zero])]).tocsr()
    bub=[upper[t] for t in teacher_ids]+[-lower[t] for t in teacher_ids]
    costs=[]
    for sid,tid in pairs:
        sec=student_by_id[sid]["teaching_section_code"]
        is_adviser=homes[sec]["adviser_employee_number"]==tid
        tie=int.from_bytes(hashlib.sha256(f"{seed}|{sid}|{tid}".encode()).digest()[:8],"big")/2**64*.001
        costs.append((10.0 if is_adviser else 0.0)+tie)
    costs += [100.0]*(2*nt)
    solved=linprog(costs,A_eq=eq.tocsr(),b_eq=rhs,A_ub=aub,b_ub=bub,
                   bounds=[(0,1)]*n+[(0,None)]*(2*nt),method="highs")
    if not solved.success:
        raise ValueError("No feasible two-subject allocation: "+solved.message)
    if any(abs(v-round(v))>1e-6 for v in solved.x[:n]):
        raise ValueError("Allocation is fractional under current constraints")
    selected=defaultdict(list)
    for (sid,tid),value in zip(pairs,solved.x[:n]):
        if value>.5:
            selected[sid].append(tid)
    if any(len(selected[sid])!=2 or len(set(selected[sid]))!=2 for sid in student_ids):
        raise ValueError("Final allocation does not have exactly two distinct subject teachers per student")
    rows=[]
    for sid in student_ids:
        student=student_by_id[sid]
        sec=student["teaching_section_code"]
        for tid in sorted(selected[sid]):
            load=context[(sid,tid)]
            basis="advisory_secondary" if homes[sec]["adviser_employee_number"]==tid else "regular_load"
            rows.append({"student_number":sid,"section_code":student["section_code"],
                         "teaching_section_code":sec,"target_type":"subject_teacher",
                         "target_key":"SUBJECT|"+load["assignment_key"],
                         "teacher_employee_number":tid,"subject_code":load["subject_code"],
                         "subject_name":load.get("subject_name",""),"program_code":"",
                         "allocation_basis":basis})
    subject_counts=Counter(r["teacher_employee_number"] for r in rows)
    basis_counts=Counter((r["teacher_employee_number"],r["allocation_basis"]) for r in rows)
    coverage={t:{"eligible_students":pools[t],"regular_pool_students":len(regular_students[t]),
                 "advisory_pool_students":len(advisory_students[t]),
                 "subject_regular_invitations":basis_counts[(t,"regular_load")],
                 "subject_advisory_invitations":basis_counts[(t,"advisory_secondary")],
                 "subject_invitations":subject_counts[t],"minimum":lower[t],"maximum":upper[t]}
              for t in teacher_ids}
    return rows,coverage


def finalize(workbook: Path, canvas_zip: Path, output: Path, student_roster: Path | None = None):
    if output.exists():
        raise ValueError("Choose a new output folder; existing outputs are preserved")
    data = load_sheets(workbook)
    roster_students = load_external_students(student_roster, data["Students"]) if student_roster else data["Students"]
    # The user confirmed that official section 11GS01 is mixed with the
    # mother teaching/advisory section 11ME02. Record that confirmation in the
    # generated payload without editing their reviewed workbook.
    gs_group = [r for r in data["SectionGroups"] if r["section_code"] == "11GS01"]
    if len(gs_group) != 1 or gs_group[0]["teaching_section_code"] != "11ME02":
        raise ValueError("Expected the user-confirmed 11GS01 -> 11ME02 teaching-group mapping")
    gs_group[0]["review_status"] = "approved"
    gs_group[0]["review_notes"] = (
        "User-confirmed: 11GS01 students are mixed with 11ME02; use the mother section's "
        "subject teachers, homeroom adviser and program while retaining official section 11GS01."
    )
    identities, canvas_hash, sm_courses = load_canvas(canvas_zip)
    loads, teachers, exclusions = build_loads(data, identities)
    groups = {r["section_code"]: r["teaching_section_code"] for r in data["SectionGroups"]}
    students = []
    for r in roster_students:
        students.append({"student_number": r["student_number"], "section_code": r["section_code"],
                         "teaching_section_code": groups.get(r["section_code"], r["section_code"])})
    if len({s["student_number"] for s in students}) != len(students):
        raise ValueError("Duplicate student numbers")
    homes = {r["section_code"]: {"section_code": r["section_code"],
                                 "adviser_employee_number": r["adviser_employee_number"],
                                 "program_code": "BE_BRAVE"} for r in data["Homeroom"]}
    occupied = {s["teaching_section_code"] for s in students}
    if occupied - set(homes):
        raise ValueError("No adviser/program mapping for: " + ", ".join(sorted(occupied-set(homes))))
    if any(homes[s]["adviser_employee_number"] not in teachers for s in occupied):
        raise ValueError("Homeroom references an unknown teacher")
    programs = [
        {"program_code":"BE_BRAVE", "program_name":"Be Brave Homeroom Program", "school_level":lvl}
        for lvl in ("JHS","SHS")
    ]
    subject_targets, coverage = allocation(students, loads, homes, minimum=0, maximum=96)
    targets = list(subject_targets)
    for student in students:
        sec = student["teaching_section_code"]
        home = homes[sec]
        for kind in ("homeroom_adviser", "homeroom_program"):
            targets.append({"student_number": student["student_number"], "section_code": student["section_code"],
                            "teaching_section_code": sec, "target_type": kind,
                            "target_key": kind.upper()+"|"+sec,
                            "teacher_employee_number": home["adviser_employee_number"] if kind == "homeroom_adviser" else "",
                            "subject_code":"", "program_code":"BE_BRAVE" if kind == "homeroom_program" else "",
                            "allocation_basis":"advisory" if kind == "homeroom_adviser" else "program"})
    if len(targets) != 4*len(students):
        raise ValueError("Expected exactly four evaluation targets per student")
    basis_counts = Counter(r["allocation_basis"] for r in subject_targets)
    # Expand teacher coverage to all rostered faculty, including zero invitations.
    full_coverage = []
    name_coverage = []
    adviser_counts = Counter(homes[s["teaching_section_code"]]["adviser_employee_number"] for s in students)
    for tid, teacher in sorted(teachers.items()):
        c = coverage.get(tid, {"eligible_students":0,"regular_pool_students":0,"advisory_pool_students":0,
                               "subject_regular_invitations":0,
                               "subject_advisory_invitations":0,"subject_invitations":0,"minimum":0,"maximum":0})
        row = {"employee_number": tid, **c, "homeroom_adviser_invitations":adviser_counts[tid],
               "total_teacher_invitations":c["subject_invitations"]+adviser_counts[tid]}
        full_coverage.append(row)
        name_coverage.append({"employee_number":tid,"display_name":teacher.get("display_name", ""),
                              "subject_invitations":c["subject_invitations"],
                              "regular_load_invitations":c["subject_regular_invitations"],
                              "advisory_secondary_invitations":c["subject_advisory_invitations"],
                              "homeroom_adviser_invitations":adviser_counts[tid],
                              "total_teacher_invitations":row["total_teacher_invitations"]})
    allocation_by_student = defaultdict(Counter)
    for row in targets:
        allocation_by_student[row["student_number"]][row["target_type"]] += 1
    if any(counts != Counter({"subject_teacher":2,"homeroom_adviser":1,"homeroom_program":1})
           for counts in allocation_by_student.values()):
        raise ValueError("Target count validation failed")
    advisories = []
    student_counts = Counter(s["teaching_section_code"] for s in students)
    for sec in sorted(occupied):
        h=homes[sec]
        advisories.append({"section_code":sec,"adviser_employee_number":h["adviser_employee_number"],
                           "adviser_name":teachers[h["adviser_employee_number"]]["display_name"],
                           "program_code":"BE_BRAVE","program_name":"Be Brave Homeroom Program",
                           "student_count":student_counts[sec]})
    output.mkdir(parents=True, mode=0o700)
    payload=output/"supabase_payload"; payload.mkdir(mode=0o700)
    # Operational payload omits student names/emails and avoids repeating teacher
    # names in student assignments. IDs and normalized target keys are sufficient.
    file_rows={
        "students.csv":(students,["student_number","section_code","teaching_section_code"]),
        "teachers.csv":(list(teachers.values()),["employee_number","display_name","email"]),
        "subject_loads.csv":(loads,["assignment_key","section_code","subject_code","subject_name","teacher_employee_number","assignment_mode","allocation_priority","source_note"]),
        "homeroom.csv":([homes[s] for s in sorted(occupied)],["section_code","adviser_employee_number","program_code"]),
        "programs.csv":(programs,["program_code","program_name","school_level"]),
        "evaluation_allocations.csv":(targets,["student_number","section_code","teaching_section_code","target_type","target_key","teacher_employee_number","subject_code","subject_name","program_code","allocation_basis"]),
        "teacher_coverage.csv":(full_coverage,["employee_number","eligible_students","regular_pool_students","advisory_pool_students","subject_regular_invitations","subject_advisory_invitations","subject_invitations","minimum","maximum","homeroom_adviser_invitations","total_teacher_invitations"]),
        "section_groups.csv":(data["SectionGroups"],["section_code","teaching_section_code","review_status","review_notes"]),
    }
    file_meta={}
    for name,(rows,cols) in file_rows.items():
        path=payload/name; private_csv(path,rows,cols)
        file_meta[name]={"rows":len(rows),"sha256":sha(path),"bytes":path.stat().st_size}
    manifest={"contract":"roster-v2-validated","period_code":PERIOD_CODE,
              "schedule_version":"Finals","same_school_year_cycle_as_q2":True,
              "allocation_policy":{"subject_targets_per_student":2,"adviser_subject_load":"secondary; regular-load edges preferred",
                                  "canvas_sm_courses":"excluded from evaluation; no full-class forcing based on teacher section or student count",
                                  "omitted_science_sections":sorted(OMIT_SCIENCE_SECTIONS),
                                  "seed":SEED,"minimum_teacher_count":0,"maximum_teacher_count":96,
                                  "quota_note":"No minimum invitation floor; eligible subject invitations are balanced subject to exactly two distinct subject teachers per student and the 96 maximum."},
              "sources":{"review_workbook_sha256":sha(workbook),
                         "student_roster_sha256":sha(student_roster) if student_roster else sha(workbook),
                         "canvas_export_sha256":canvas_hash},
              "source_sha256":sha(workbook),
              "counts":{"students":len(students),"teachers":len(teachers),"subject_loads":len(loads),
                        "subject_allocations":len(subject_targets),"adviser_allocations":len(students),
                        "program_allocations":len(students),"evaluation_allocations":len(targets),
                        "advisory_sections":len(advisories),"zero_subject_invitation_teachers":sum(c["subject_invitations"]==0 for c in full_coverage),
                        "subject_allocation_basis":dict(basis_counts)},
              "canvas_sm_courses_excluded":len(sm_courses),
              "errors":0,"database_compatible":False,
              "deployment_gate":"Questionnaire and target-aware schema migrations are applied; Q2 roster import and target-aware app deployment remain pending",
              "files":file_meta}
    manifest_path=payload/"manifest.json"; manifest_path.write_text(json.dumps(manifest,indent=2)+"\n"); manifest_path.chmod(0o600)
    private_csv(output/"adviser_roster_review.csv",advisories,["section_code","adviser_employee_number","adviser_name","program_code","program_name","student_count"])
    private_csv(output/"teacher_coverage_review.csv",name_coverage,["employee_number","display_name","subject_invitations","regular_load_invitations","advisory_secondary_invitations","homeroom_adviser_invitations","total_teacher_invitations"])
    private_csv(output/"excluded_loads_audit.csv",exclusions,["section_code","subject_code","teacher_employee_number","teacher_alias","reason","review_notes"])
    private_csv(output/"excluded_sm_courses_audit.csv",sm_courses,["canvas_course_id","course_id","short_name","subject_name","term_id","course_status","section_count","canvas_section_names","active_student_enrollments","evaluation_status"])
    # Compressed transport package contains only the minimal Supabase payload.
    with zipfile.ZipFile(output/"supabase_payload.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
        for path in sorted(payload.iterdir()):
            zf.write(path,arcname=path.name)
    (output/"supabase_payload.zip").chmod(0o600)
    notes=(output/"FINALIZATION_NOTES.md")
    zero_teachers = [r for r in name_coverage if r["subject_invitations"] == 0]
    under20 = [r for r in name_coverage if 0 < r["subject_invitations"] < 20]
    collado_by_section = Counter(r["section_code"] for r in subject_targets
                                 if r["teacher_employee_number"] == COLLADO_ID and r["subject_code"] == "UCSP")
    galang_by_section = Counter(r["section_code"] for r in subject_targets if r["teacher_employee_number"] == GALANG_ID)
    zero_text = ", ".join(f"{r['display_name']} ({r['employee_number']})" for r in zero_teachers) or "none"
    collado_text = ", ".join(f"{sec}: {count}" for sec, count in sorted(collado_by_section.items())) or "none"
    galang_text = ", ".join(f"{sec}: {count}" for sec, count in sorted(galang_by_section.items())) or "none"
    coverage_note = (
        f"The two-target allocation has {len(zero_teachers)} teacher(s) with zero subject invitations ({zero_text}) "
        f"and {len(under20)} with 1-19. Collado has {sum(collado_by_section.values())} UCSP invitations across "
        f"{len(collado_by_section)} linked sections ({collado_text}); Galang has {sum(galang_by_section.values())} "
        f"across {len(galang_by_section)} sections ({galang_text}). See the local coverage CSV for the teacher-by-teacher counts."
    )
    notes.write_text(
        "# Second Quarter roster bundle\n\n"
        f"Students: {len(students)}; teachers: {len(teachers)}; subject loads: {len(loads)}; "
        f"subject invitations: {len(subject_targets)}; total target rows: {len(targets)}.\n\n"
        "The source workbooks were not modified. `SubjectLoads` drove eligible loads; the separate enrolled-student roster supplied student numbers and sections; Canvas supplied the explicit teacher identity/section resolutions. "
        "Student names and emails are omitted from the Supabase payload. Adviser roster and full teacher invitation coverage are in the local review CSVs. "
        f"Canvas courses with the `_SM` suffix are excluded from evaluation ({len(sm_courses)} course records; see the local audit). "
        "There is no full-class rule based on how many sections or students a teacher has; the allocation balances eligible invitations subject to two targets per student and the 96 maximum. "
        + coverage_note + " "
        "No roster database write occurred. The questionnaire and target-aware schema migrations have been applied; this bundle still needs the dedicated pilot/full-roster import and the matching app deployment.\n"
    )
    notes.chmod(0o600)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workbook",type=Path,required=True)
    p.add_argument("--student-roster",type=Path,help="Optional student-number/section workbook; reviewed workbook still supplies SubjectLoads and homeroom mappings")
    p.add_argument("--canvas-zip",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(finalize(a.workbook,a.canvas_zip,a.output,a.student_roster),indent=2))
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
