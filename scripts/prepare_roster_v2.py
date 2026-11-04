"""Validate a reviewed flat XLSX roster and build a four-target offline bundle.

This is the replacement input contract. It does not use a UCSP reconciliation
file and never uploads, creates Auth users, activates, or opens a period.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feval.roster_v2 import allocate_two, clean
from scripts.build_schedule_roster import write_csv, write_private


REQUIRED = {
    "Students": {"student_number","display_name","email","section_code","review_status"},
    "Teachers": {"employee_number","display_name","review_status"},
    "SubjectLoads": {"section_code","subject_code","teacher_employee_number","review_status","decision","assignment_mode"},
    "Homeroom": {"section_code","adviser_employee_number","program_code","review_status"},
    "Programs": {"program_code","program_name","school_level","review_status"},
    "Settings": {"key","value"},
    "SectionGroups": {"section_code","teaching_section_code","review_status","review_notes"},
}


def reviewed_rows(path):
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Use a flat .xlsx review workbook")
    book = load_workbook(path, read_only=True, data_only=False)
    result = {}
    try:
        for name, required in REQUIRED.items():
            if name not in book.sheetnames:
                raise ValueError("Missing required sheet: " + name)
            iterator = book[name].iter_rows(values_only=True)
            headers = [clean(v) for v in next(iterator)]
            if len([h for h in headers if h]) != len(set(h for h in headers if h)):
                raise ValueError("Duplicate headers in " + name)
            if required - set(headers):
                raise ValueError(f"Missing columns in {name}: {sorted(required-set(headers))}")
            rows=[]
            for row in iterator:
                if not any(v is not None for v in row):
                    continue
                if any(isinstance(v,str) and v.startswith("=") for v in row):
                    raise ValueError("Formulas are not allowed in import data sheets: " + name)
                rows.append({h:clean(v) for h,v in zip(headers,row) if h})
            result[name]=rows
    finally:
        book.close()
    return result


def validate(rows):
    errors=[]
    def require(condition, message):
        if not condition:
            errors.append(message)
    for name in REQUIRED:
        if name != "SectionGroups":
            require(bool(rows.get(name)), "Empty required sheet: " + name)
    settings_rows=rows.get("Settings",[])
    require(len(settings_rows)==len({r["key"] for r in settings_rows}),"Duplicate Settings keys")
    settings={r["key"]:r["value"] for r in settings_rows}
    require(settings.get("review_status")=="approved","Settings.review_status must be approved")
    require(bool(settings.get("period_code")),"Production period_code is required")
    require(settings.get("schedule_version")=="Finals","Finals schedule selection is required")
    require(settings.get("exclude_adviser")=="true","exclude_adviser must be true")
    try:
        int(settings.get("seed",""))
        require(int(settings.get("minimum_teacher_count","20"))>=0,"Teacher minimum must be nonnegative")
        if settings.get("maximum_teacher_count"):
            require(int(settings["maximum_teacher_count"])>=0,"Teacher maximum must be nonnegative")
    except ValueError:
        errors.append("Seed and teacher quota fields must be integers")
    for name,key in (("Students","student_number"),("Teachers","employee_number"),("Homeroom","section_code"),("Programs","program_code")):
        vals=[r[key] for r in rows.get(name,[])]
        require(all(vals) and len(vals)==len(set(vals)), f"Blank or duplicate {name}.{key}")
        require(all(r.get("review_status")=="approved" for r in rows.get(name,[])), f"All {name} rows must be approved")
    students=rows.get("Students",[]);teachers=rows.get("Teachers",[])
    teacher_ids={r["employee_number"] for r in teachers}
    require(all(r.get("display_name") for r in teachers),"Blank teacher display name")
    require(all(r.get("display_name") and r.get("section_code") for r in students),"Blank student name or section")
    require(all(r.get("email")==r["student_number"]+"@feuhighschool.edu.ph" for r in students),"Student email convention mismatch")
    homes={r["section_code"]:r for r in rows.get("Homeroom",[])}
    programs={r["program_code"]:r for r in rows.get("Programs",[])}
    require(all(p.get("school_level") in {"JHS","SHS"} and p.get("program_name") for p in programs.values()),"Invalid program school level/name")
    for h in homes.values():
        require(h["adviser_employee_number"] in teacher_ids,"Unknown adviser for section "+h["section_code"])
        p=programs.get(h["program_code"])
        require(p is not None,"Unknown program for section "+h["section_code"])
        if p:
            require(p["school_level"]==("JHS" if h["section_code"].startswith("G") else "SHS"),"Program level mismatch for "+h["section_code"])
    occupied={s["section_code"] for s in students}
    group_rows=rows.get("SectionGroups",[])
    require(len(group_rows)==len({r['section_code'] for r in group_rows}),"Duplicate section group mapping")
    groups={r['section_code']:r['teaching_section_code'] for r in group_rows}
    require(all(r['review_status']=='approved' and r['review_notes'] for r in group_rows),"Section group mappings need approval and provenance notes")
    require(all(v not in groups or groups[v]==v for v in groups.values()),"Section groups must not chain or cycle")
    for s in students:
        expected=groups.get(s['section_code'],s['section_code'])
        require(not s.get('teaching_section_code') or s['teaching_section_code']==expected,"Undeclared student teaching group")
        s['teaching_section_code']=expected
    occupied_teaching={groups.get(s,s) for s in occupied}
    require(occupied_teaching<=set(homes),"Missing section adviser/program mappings")
    eligible=[]
    for r in rows.get("SubjectLoads",[]):
        require(r.get("review_status")=="approved","Subject load not approved: "+r.get("section_code",""))
        require(r.get("decision") in {"include","exclude"},"Every subject load needs include/exclude decision")
        if r.get("decision")!="include":
            require(bool(r.get("review_notes")),"Excluded loads require review_notes")
            continue
        require(r.get("assignment_mode") in {"regular","overload"},"Only regular/overload loads may be included in primary roster")
        require(r.get("allocation_priority","primary")=="primary","Secondary assignments cannot enter primary allocation")
        require(r["teacher_employee_number"] in teacher_ids,"Unknown teacher in included load")
        require(bool(r["section_code"] and r["subject_code"] and r["subject_code"]!="EC_MK"),"Unresolved included subject/section")
        eligible.append({"assignment_key":"|".join((r["section_code"],r["subject_code"],r["teacher_employee_number"])),
                         "section_code":r["section_code"],"subject_code":r["subject_code"],
                         "teacher_employee_number":r["teacher_employee_number"]})
    pairs=Counter((r["section_code"],r["subject_code"]) for r in eligible)
    require(all(n==1 for n in pairs.values()),"Shared/duplicate section-subject rows must be resolved before allocation")
    # A teacher who is also the adviser is filtered before the solver runs.
    by_section=defaultdict(set)
    for r in eligible:
        h=homes.get(r["section_code"])
        if h and h["adviser_employee_number"]!=r["teacher_employee_number"]:
            by_section[r["section_code"]].add(r["teacher_employee_number"])
    for sec in sorted(occupied_teaching):
        require(len(by_section[sec])>=2,"Fewer than two non-adviser subject teachers in "+sec)
    return errors,settings,eligible,homes


def prepare(path, output):
    if output.exists():
        raise ValueError("Output directory must not exist; preserve earlier bundles")
    rows=reviewed_rows(path)
    errors,settings,eligible,homes=validate(rows)
    if errors:
        # No release files are written for an unapproved or invalid workbook.
        raise ValueError("Roster rejected:\n"+"\n".join(sorted(set(errors))))
    selected,coverage=allocate_two(rows["Students"],eligible,
        {s:h["adviser_employee_number"] for s,h in homes.items()},int(settings["seed"]),
        int(settings.get("minimum_teacher_count","20")),
        int(settings["maximum_teacher_count"]) if settings.get("maximum_teacher_count") else None)
    targets=[]
    student_by_id={s['student_number']:s for s in rows['Students']}
    for r in selected:
        student=student_by_id[r['student_number']]
        targets.append({"student_number":r["student_number"],"section_code":student["section_code"],
                        "teaching_section_code":student['teaching_section_code'],
                        "target_type":"subject_teacher","target_key":"SUBJECT|"+r["assignment_key"],
                        "teacher_employee_number":r["teacher_employee_number"],
                        "subject_code":r["subject_code"],"program_code":""})
    for s in rows["Students"]:
        h=homes[s["teaching_section_code"]]
        for kind in ("homeroom_adviser","homeroom_program"):
            targets.append({"student_number":s["student_number"],"section_code":s["section_code"],
                "teaching_section_code":s['teaching_section_code'],
                "target_type":kind,"target_key":kind.upper()+"|"+s["teaching_section_code"],
                "teacher_employee_number":h["adviser_employee_number"] if kind=="homeroom_adviser" else "",
                "subject_code":"","program_code":h["program_code"] if kind=="homeroom_program" else ""})
    assert len(targets)==4*len(rows["Students"])
    output.mkdir(parents=True,mode=0o700)
    manifest={"contract":"roster-v2-validated","period_code":settings["period_code"],
        "schedule_version":"Finals","exclude_adviser":True,"seed":int(settings["seed"]),
        "source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "counts":{"students":len(rows["Students"]),"eligible_loads":len(eligible),
                  "subject_allocations":len(selected),"evaluation_allocations":len(targets)},
        "errors":0,"database_compatible":False,
        "deployment_gate":"Requires target-aware schema, RLS/RPC and portal migration before upload/activation",
        "files":{}}
    files={"students":rows["Students"],"teachers":rows["Teachers"],"subject_loads":eligible,
           "homeroom":rows["Homeroom"],"programs":rows["Programs"],
           "evaluation_allocations":targets,"teacher_coverage":coverage}
    if rows['SectionGroups']:
        files['section_groups']=rows['SectionGroups']
    for name,data in files.items():
        p=output/(name+".csv");write_csv(p,data)
        manifest["files"][p.name]={"rows":len(data),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    write_private(output/"manifest.json",manifest)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("workbook",type=Path)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(prepare(a.workbook,a.output_dir),indent=2))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__=="__main__":
    main()
