"""Build private roster review data directly from the two current timetables.

No UCSP reconciliation workbook, network requests, or database writes are used.
Writes review CSV/JSON, not an approved production import bundle.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feval.roster_v2 import (TeacherRegistry, assignment_annotations, assignment_mode, allocate_two, allocate_balanced, clean, norm, room_advisers,
                             section_code, sheet_records, student_timetable, teacher_timetable)


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_private(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    path.chmod(0o600)


def write_csv(path, rows, columns=None):
    columns = columns or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="raise")
        w.writeheader()
        w.writerows(rows)
    path.chmod(0o600)


def build(student_master, classes, teachers, identity_registry, out, aliases=None, seed=20261023, section_groups=None, load_overrides=None):
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o700)
    registry_rows = [{k:r.get(k,"") for k in ("employee_number","display_name","email")}
                     for r in csv_rows(identity_registry)]
    registry = TeacherRegistry(registry_rows, aliases)
    section_groups = section_groups or {}
    raw_students = sheet_records(student_master, "student_master")
    students = []
    findings = []

    def issue(code, entity, key, detail):
        findings.append({"code": code, "entity": entity, "key": key,
                         "detail": detail, "review_decision": "", "review_notes": ""})

    for row in raw_students:
        sid = clean(row["Student Number"])
        sec = section_code(row["K12 - Section"])
        if not sec:
            issue("UNKNOWN_STUDENT_SECTION", "student", sid, row["K12 - Section"])
        students.append({"student_number": sid, "display_name": " ".join(
            row.get(k, "") for k in ("First Name", "Middle Name", "Last Name") if row.get(k)),
            "email": sid + "@feuhighschool.edu.ph", "section_code": sec,
            "teaching_section_code": section_groups.get(sec,sec),
            "source_section": row["K12 - Section"], "review_status": "needs_review"})
    for sid, count in Counter(s["student_number"] for s in students).items():
        if not sid or count > 1:
            issue("INVALID_STUDENT_ID", "student", sid, "Blank or duplicate student number")
    student_cells = student_timetable(classes)
    teacher_cells = teacher_timetable(teachers)
    advisers_raw = room_advisers(teachers)
    annotations = assignment_annotations(teachers)
    modes = defaultdict(set)
    mode_refs = defaultdict(set)
    for r in [*teacher_cells, *annotations]:
        tid = registry.resolve(r["teacher_alias"])
        if tid:
            k=(r["section_code"], r["subject_code"],tid)
            modes[k].add(r["assignment_mode"])
            mode_refs[k].add(r["source"])
    alias_use = defaultdict(set)
    for row in [*student_cells, *teacher_cells, *advisers_raw]:
        alias_use[row["teacher_alias"]].add(row["source"])
    alias_rows = [{"source_alias": a, "employee_number": registry.resolve(a),
                   "source_cells": "; ".join(sorted(refs)), "review_status": "needs_review"}
                  for a, refs in sorted(alias_use.items())]

    teacher_evidence = defaultdict(set)
    teacher_candidates = defaultdict(set)
    teacher_section_evidence = defaultdict(set)
    for row in teacher_cells:
        tid = registry.resolve(row["teacher_alias"])
        if tid:
            teacher_section_evidence[(row["section_code"],tid)].add(row["source"])
        if tid and row["subject_code"]:
            key = (row["section_code"], row["subject_code"], tid)
            teacher_evidence[key].add(row["source"])
            teacher_candidates[key[:2]].add(tid)

    advisers = {}
    homeroom = []
    for row in advisers_raw:
        sec, tid = row["section_code"], registry.resolve(row["teacher_alias"])
        if not sec:
            continue
        homeroom.append({"section_code": sec, "adviser_employee_number": tid,
                         "adviser_name": row["teacher_alias"],
                         "program_code": "HOMEROOM-JHS" if sec.startswith("G") else "HOMEROOM-SHS",
                         "source_cell": row["source"], "review_status": "needs_review"})
        if not tid:
            issue("UNRESOLVED_ADVISER_IDENTITY", "section", sec, row["source"] + ": " + row["teacher_alias"])
        elif sec in advisers and advisers[sec] != tid:
            issue("CONFLICTING_ADVISER", "section", sec, row["source"])
            advisers[sec] = ""
        else:
            advisers[sec] = tid
    advisers = {s:t for s,t in advisers.items() if t}

    grouped = defaultdict(list)
    for row in student_cells:
        if row["kind"] == "subject":
            grouped[(row["section_code"], row["subject_code"], row["subject_label"], row["teacher_alias"])].append(row["source"])
        elif row["kind"] == "adviser":
            tid = registry.resolve(row["teacher_alias"])
            if tid and row["section_code"] in advisers and advisers[row["section_code"]] != tid:
                issue("ADVISER_SOURCE_DISAGREEMENT", "section", row["section_code"], row["source"])

    loads = []
    for (sec, code, label, alias), refs in sorted(grouped.items()):
        tid = registry.resolve(alias)
        candidates = set(teacher_candidates.get((sec, code), set()))
        possible=registry.candidates(alias)
        schedule_ids=candidates
        if code=='EC_MK':
            schedule_ids=set(teacher_candidates.get((sec,'EC'),set()))|set(teacher_candidates.get((sec,'MK'),set()))
        contextual=set(possible)&schedule_ids
        if not tid and len(contextual)==1:
            tid=next(iter(contextual))
        # The combined student timetable label is resolved only if the
        # same teacher has one unambiguous language-specific timetable entry.
        if code == "EC_MK" and tid:
            alternatives = [c for c in ("EC", "MK") if (sec, c, tid) in teacher_evidence]
            if len(alternatives) == 1:
                code = alternatives[0]
                candidates = set(teacher_candidates.get((sec, code), set()))
        evidence = teacher_evidence.get((sec, code, tid), set()) if tid else set()
        status = "corroborated" if evidence and candidates == {tid} else "needs_review"
        # Some science timetable cells give section only. Retain the weaker
        # provenance explicitly; never claim their subject was independently verified.
        if status == "needs_review" and tid and code and code != "EC_MK" and not candidates:
            evidence = teacher_section_evidence.get((sec,tid),set())
            if evidence:
                status = "teacher_section_confirmed"
        if not tid:
            issue("UNRESOLVED_TEACHER_ALIAS", "load", sec+"|"+code, alias)
        if not code or code == "EC_MK":
            issue("UNRESOLVED_SUBJECT", "load", sec, label)
        if status not in {"corroborated","teacher_section_confirmed"}:
            issue("SCHEDULE_RECONCILIATION", "load", sec+"|"+code,
                  f"Student teacher={alias}; teacher-schedule candidate count={len(candidates)}")
        loads.append({"assignment_key": f"{sec}|{code}|{tid or 'UNRESOLVED'}",
                      "section_code":sec,"subject_code":code,"subject_name":label,
                      "teacher_employee_number":tid,"teacher_alias":alias,
                      "student_source_cells":"; ".join(sorted(refs)),
                      "teacher_source_cells":"; ".join(sorted(evidence)),
                      "evidence_status":status,"review_status":"needs_review"})
    # Assignment-specific overload register entries must survive stale class aliases.
    existing={(r["section_code"],r["subject_code"],r["teacher_employee_number"]) for r in loads}
    for r in [*annotations,*teacher_cells]:
        tid=registry.resolve(r["teacher_alias"])
        key=(r["section_code"],r["subject_code"],tid)
        if r["assignment_mode"]!="overload" or not tid or not r["subject_code"] or key in existing:
            continue
        loads.append(dict(assignment_key="|".join(key),section_code=key[0],subject_code=key[1],
            subject_name=r.get("subject_label") or key[1],teacher_employee_number=tid,
            teacher_alias=r["teacher_alias"],student_source_cells="",teacher_source_cells=r["source"],
            evidence_status="assignment_register_confirmed",review_status="needs_review"))
        existing.add(key)
    # Explicit user corrections retain their provenance and do not edit source workbooks.
    for override in load_overrides or []:
        sec,code,tid=(override[k] for k in ("section_code","subject_code","teacher_employee_number"))
        if tid not in registry.rows or not override.get("provenance"):
            raise ValueError("Override needs an existing identity and provenance")
        loads=[r for r in loads if (r["section_code"],r["subject_code"])!=(sec,code)]
        loads.append(dict(assignment_key=f"{sec}|{code}|{tid}",section_code=sec,
            subject_code=code,subject_name=override["subject_name"],teacher_employee_number=tid,
            teacher_alias=registry.rows[tid]["display_name"],student_source_cells="",
            teacher_source_cells=override["provenance"],evidence_status="user_confirmed",
            assignment_mode=override["assignment_mode"],review_status="needs_review"))
    for r in loads:
        key=(r["section_code"],r["subject_code"],r["teacher_employee_number"])
        observed=set(modes.get(key,set()))
        # Section-only science cells still carry assignment-local overload tags.
        if not observed:
            observed=set(modes.get((key[0],"",key[2]),set()))
        observed.discard("regular") if len(observed)>1 else None
        mode=r.get("assignment_mode") or (next(iter(observed)) if len(observed)==1 else
            "conflict" if observed else assignment_mode(r["teacher_alias"]))
        r["assignment_mode"]=mode
        r["allocation_priority"]="primary" if mode in {"regular","overload"} else "secondary"
        r["assignment_mode_sources"]="; ".join(sorted(mode_refs.get(key,set())))
        if mode=="conflict":
            issue("ASSIGNMENT_MODE_CONFLICT","load",r["assignment_key"],"Conflicting current-workbook tags; excluded from primary pool")
    # Conflicting student timetable teacher rows never enter the eligible pool.
    shared = Counter((l["section_code"],l["subject_code"]) for l in loads)
    for key, count in shared.items():
        if count > 1:
            issue("SHARED_OR_CONFLICTING_LOAD", "load", "|".join(key), f"{count} source mappings; requires explicit disposition")
    eligible = [r for r in loads if r["evidence_status"] in {"corroborated","teacher_section_confirmed","user_confirmed","assignment_register_confirmed"}
                and r["allocation_priority"]=="primary" and shared[(r["section_code"],r["subject_code"])] == 1]
    occupied = Counter(s["section_code"] for s in students)
    for sec in occupied:
        if section_groups.get(sec,sec) not in advisers:
            issue("MISSING_ADVISER", "section", sec, "No uniquely resolved adviser; four-target allocation blocked")

    # Provisional allocation can be computed for review when adviser identity
    # and at least two corroborated non-adviser teachers exist for every student.
    allocated, quota = [], []
    allocation_policy="minimum_20_balanced_cap"
    try:
        allocated, quota = allocate_two(students, eligible, advisers, seed)
    except ValueError as exc:
        issue("QUOTA_SCENARIO_REJECTED", "allocation", "minimum_20_balanced_cap", str(exc))
        # Keep the same minimum and find the smallest feasible global cap.
        # Record the failed tight-cap scenario rather than silently dropping it.
        allocation_policy="provisional_minimum20_minimax_cap"
        try:
            allocated,quota=allocate_balanced(students,eligible,advisers,seed,minimum=20)
        except ValueError as second:
            issue("ALLOCATION_BLOCKED", "allocation", "all_students", str(second))
    hr_by_sec = {r["section_code"]:r for r in homeroom}
    pool_count=len(quota)
    if quota:
        pool_ids={r['teacher_employee_number'] for r in quota}
        for r in quota:
            r['status']='provisional'
        for tid in sorted(set(registry.rows)-pool_ids):
            quota.append({'teacher_employee_number':tid,'eligible_students':0,
                'minimum':0,'maximum':0,'allocated':0,'status':'no_confirmed_pool_needs_review'})
            issue('NO_CONFIRMED_POOL','teacher',tid,'Identity registry entry has no confirmed non-adviser candidate pool; review active roster membership')
    for r in quota:
        tid=r["teacher_employee_number"]
        r["primary_load_count"]=sum(x["teacher_employee_number"]==tid for x in eligible)
        r["secondary_evidence_count"]=sum(registry.resolve(x["teacher_alias"])==tid and x["assignment_mode"] in {"daily_sub","long_term_sub","substitute_unspecified"} for x in annotations)
    assignments = []
    by_student = defaultdict(list)
    for row in allocated:
        by_student[row["student_number"]].append(row)
    for student in students:
        sid, sec = student["student_number"], student["section_code"]
        teaching_sec=student["teaching_section_code"]
        rows = sorted(by_student[sid],key=lambda r:r["teacher_employee_number"])
        for slot in (1,2):
            load = rows[slot-1] if len(rows)==2 else {}
            assignments.append({"student_number":sid,"section_code":sec,
                "target_type":"subject_teacher","slot":str(slot),
                "teacher_employee_number":load.get("teacher_employee_number",""),
                "subject_code":load.get("subject_code",""),"program_code":"",
                "assignment_key":load.get("assignment_key",""),
                "status":"provisional" if load else "blocked"})
        hr = hr_by_sec.get(teaching_sec,{})
        assignments.append({"student_number":sid,"section_code":sec,
            "target_type":"homeroom_adviser","slot":"1",
            "teacher_employee_number":advisers.get(teaching_sec,""),"subject_code":"","program_code":"",
            "assignment_key":"HR-ADVISER|"+sec,
            "status":"provisional" if teaching_sec in advisers else "blocked"})
        assignments.append({"student_number":sid,"section_code":sec,
            "target_type":"homeroom_program","slot":"1","teacher_employee_number":"",
            "subject_code":"","program_code":hr.get("program_code",""),
            "assignment_key":"HR-PROGRAM|"+sec,
            "status":"provisional" if hr.get("program_code") else "blocked"})
    sections = [{"section_code":s,"school_level":"JHS" if s.startswith("G") else "SHS",
                 "grade_level":int(s[1:3]) if s.startswith("G") else int(s[:2]),
                 "teaching_section_code":section_groups.get(s,s),
                 "students":n,"adviser_employee_number":advisers.get(section_groups.get(s,s),""),
                 "candidate_subject_teachers":len({r['teacher_employee_number'] for r in eligible if r['section_code']==section_groups.get(s,s)}),
                 "review_status":"needs_review"} for s,n in sorted(occupied.items())]
    datasets = {"Students":students,"Sections":sections,"Teachers":registry_rows,
                "SubjectLoads":loads,"Homeroom":homeroom,
                "AssignmentEvidence":[dict(section_code=r["section_code"],subject_code=r["subject_code"],
                    teacher_alias=r["teacher_alias"],teacher_employee_number=registry.resolve(r["teacher_alias"]),
                    assignment_mode=r["assignment_mode"],source=r["source"],review_status="needs_review")
                    for r in [*annotations,*teacher_cells] if r["assignment_mode"]!="regular"],"TeacherAliases":alias_rows,
                "Allocations":assignments,"TeacherCoverage":quota,"Issues":findings}
    datasets["SectionGroups"]=[{"section_code":s,"teaching_section_code":t,
        "review_status":"needs_review","review_notes":"User identified mixed teaching/adviser group; retain official section"}
        for s,t in sorted(section_groups.items())]
    datasets["Programs"]=[{"program_code":"HOMEROOM-"+level,"program_name":"Homeroom Program",
        "school_level":level,"review_status":"needs_review"} for level in ("JHS","SHS")]
    datasets["Settings"]=[{"key":k,"value":v} for k,v in {
        "period_code":"SY2026-2027-S1-FINALS","schedule_version":"Finals",
        "exclude_adviser":"true","seed":str(seed),
        "minimum_teacher_count":"20",
        "maximum_teacher_count":str(max((r['maximum'] for r in quota),default=0)) if quota else "",
        "review_status":"needs_review"}.items()]
    for r in datasets["Teachers"]:
        r["review_status"]="needs_review"
    for r in loads:
        r["decision"]="";r["review_notes"]=""
    for name, rows in datasets.items():
        if rows:
            write_csv(out/(name+".csv"),rows)
    manifest = {"contract":"roster-v2-review","period_status":"draft",
                "schedule_version":"Finals","exclude_adviser":True,"seed":seed,
                "allocation_policy":allocation_policy,
                "students":len(students),"occupied_sections":len(occupied),
                "subject_loads":len(loads),"secondary_loads":sum(r["allocation_priority"]=="secondary" for r in loads),"eligible_review_loads":len(eligible),
                "subject_corroborated_loads":sum(r["evidence_status"]=="corroborated" for r in eligible),
                "teacher_section_only_loads":sum(r["evidence_status"]=="teacher_section_confirmed" for r in eligible),
                "resolved_adviser_sections":sum(section_groups.get(s,s) in advisers for s in occupied),
                "allocated_subject_evaluations":len(allocated),"required_subject_evaluations":2*len(students),
                "teacher_identity_records":len(registry_rows),"confirmed_subject_teacher_pools":pool_count,
                "four_slot_rows":len(assignments),"blocked_slots":sum(r["status"]=="blocked" for r in assignments),
                "issue_codes":dict(Counter(r["code"] for r in findings)),
                "upload_ready":False,"review_required":True,
                "load_corrections_sha256":hashlib.sha256(json.dumps(load_overrides or [],sort_keys=True).encode()).hexdigest(),
                "alias_resolutions_sha256":hashlib.sha256(json.dumps(aliases or {},sort_keys=True).encode()).hexdigest(),
                "section_groups_sha256":hashlib.sha256(json.dumps(section_groups,sort_keys=True).encode()).hexdigest(),
                "source_files":[{"filename":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in (student_master,classes,teachers,identity_registry)]}
    write_private(out/"manifest.json",manifest)
    # Workbook renderer consumes JSON; source identities remain in ignored output.
    write_private(out/"workbook_data.json",datasets)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--students",type=Path,required=True)
    p.add_argument("--classes",type=Path,required=True)
    p.add_argument("--teachers",type=Path,required=True)
    p.add_argument("--identity-registry",type=Path,required=True,
                   help="Teacher identity CSV only; old assignment rows are not read.")
    p.add_argument("--aliases",type=Path,help="Reviewed JSON mapping source aliases to employee numbers.")
    p.add_argument("--section-groups",type=Path,help="Reviewed/proposed JSON mapping official sections to teaching groups")
    p.add_argument("--output-dir",type=Path,default=Path("exports/roster_v2_review"))
    p.add_argument("--load-overrides",type=Path,help="Provenance-bearing user corrections JSON")
    p.add_argument("--seed",type=int,default=20261023)
    a=p.parse_args()
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        p.error("Output directory must be new or empty; preserve previous review versions")
    print(json.dumps(build(a.students,a.classes,a.teachers,a.identity_registry,a.output_dir,
                           json.loads(a.aliases.read_text()) if a.aliases else None,a.seed,
                           json.loads(a.section_groups.read_text()) if a.section_groups else None,
                           json.loads(a.load_overrides.read_text()) if a.load_overrides else None),indent=2))


if __name__=="__main__":
    main()
