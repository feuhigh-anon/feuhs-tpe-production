"""Offline schedule reconciliation and persisted, adviser-excluding allocation.

The timetable workbooks are evidence, never an import-ready database payload.
No network access or workbook mutation occurs in this module.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook


def clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def norm(value):
    text = unicodedata.normalize("NFKD", clean(value)).casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def name_tokens(value):
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode().lower()
    return {t for t in re.findall(r"[a-z]+",text) if len(t)>1}


SECTION_ALIASES = {
    "HS": ("healthscience", "hs"),
    "DT": ("digitaltechnologies", "digitaltechnology", "dt"),
    "ES": ("engineeringscience", "es"),
    "ARCD": ("architectureanddesign", "architechtureanddesign", "architecturaldesign", "arcd"),
    "AF": ("accountingandfinance", "af"),
    "ME": ("marketingandentrepreneurship", "marketingandentreprenuership", "marketing", "me"),
    "ML": ("mediaandlanguages", "medialanguage", "mals", "ml"),
    "PS": ("politicalscience", "politicalstudies", "polsci", "ps"),
    "PSY": ("psychology", "psych", "psy"),
    "AD": ("artsanddesign", "artsdesign", "artsd", "artd", "arts", "ad"),
    "TH": ("tourismandhospitality", "thm", "th"),
    "GS": ("generalstudies", "gs", "ge"),
}


def section_code(value):
    text = clean(value)
    if ":" in text:
        return ""  # Time intervals are not section headers.
    text = re.sub(r"\(?S\.?Y\.?\s*\d{2,4}\s*-\s*\d{2,4}\)?", "", text, flags=re.I)
    key = norm(text).replace("grade", "").replace("sec", "")
    key = re.sub(r"^11(?:stem|assh|be)(?=[a-z])", "11", key)
    m = re.fullmatch(r"g?0?(7|8|9|10)(\d{1,2})", key)
    if m:
        return f"G{int(m[1]):02d}-{int(m[2])}"
    m = re.fullmatch(r"12(stem|abm|humss|gas|s|a|h|g)(\d+)([ab])", key)
    if m:
        strand = {"stem": "S", "abm": "A", "humss": "H", "gas": "G"}.get(m[1], m[1].upper())
        return f"12{strand}{int(m[2]):02d}{m[3]}"
    if key.startswith("11"):
        for code, aliases in SECTION_ALIASES.items():
            for alias in aliases:
                m = re.fullmatch(r"11" + alias + r"(\d+)", key)
                if m:
                    return f"11{code}{int(m[1]):02d}"
    return ""


SUBJECT_ALIASES = {
    "GM": ("generalmathematics", "genmath", "gm"),
    "GS": ("generalscience", "gensci", "gs"),
    "EC": ("effectivecommunication", "ec"),
    "MK": ("mabisangkomunikasyon", "mabkom", "mk"),
    "PKLP": ("pagaaralngkasaysayanatlipunangpilipino", "pklp"),
    "LCS": ("lifeandcareerskills", "lifecareerskills", "lcs", "lc"),
    "BIO1": ("biology1", "bio1"), "CHEM1": ("chemistry1", "chem1", "c1"),
    "GB1": ("generalbiology1", "genbio1", "gb1"),
    "GC1": ("generalchemistry1", "genchem1", "gc1"),
    "GP1": ("generalphysics1", "genphys1", "gp1"),
    "PHYS1": ("physics1", "phys1", "p1"), "TRIG1": ("trigonometry1", "trigo", "trig", "trig1"),
    "UCSP": ("understandingculturesocietyandpolitics", "ucsp"),
    "CPAR": ("contemporaryphilippineartsfromtheregions", "cpar"),
    "ENT": ("entrepreneurship", "entrep", "ent"),
    "PR2": ("practicalresearch2", "pr2", "research2"),
    "WR": ("introductiontoworldreligionsandbeliefsystems", "worldreligions", "wr"),
    "PPG": ("philippinepoliticsandgovernance", "politicsandgovernance", "phpg", "ppg"),
    "PG": ("philippinegovernance", "phg"),
    "PHILO": ("introductiontothephilosophyofthehumanperson", "introductiontophilosophy", "philosophy", "philo"),
    "DIASS": ("disciplinesandideasintheappliedsocialsciences", "diass"),
    "AE": ("appliedeconomics", "appecon", "ae"),
    "BM": ("businessmathematics", "businessmath", "busmath", "bm"),
    "BUS1": ("business1", "bus1"),
    "BASACC": ("basacc", "basicaccounting"),
    "IOM": ("introductiontoorganizationandmanagement", "introductiontoorganizationmanagement", "organizationandmanagement", "orgman", "iom"),
    "FABM2": ("fundamentalsofaccountancybusinessandmanagement2", "fabm2"),
    "ET": ("empowermenttechnologies", "etech", "et"),
    "FPL": ("filipinosapilinglarang", "fpl"),
    "HOPE3": ("physicaleducation3and4", "healthoptimizingphysicaleducation3", "hope34", "hope3", "pe34"),
    "ARTS1": ("arts1", "arts"), "FITA": ("filipinoidentitythroughthearts", "fita"),
    "CL1": ("contemporaryliterature1", "cl1"), "CC1": ("creativecomposition1", "cc1"),
}
JHS_SUBJECTS = {"AP": ("aralingpanlipunan", "ap"), "ENG": ("english",),
                "EP": ("valueseducation", "values", "ep"), "FIL": ("filipino",),
                "MAPEH": ("mapeh",), "MATH": ("mathematics", "math"),
                "SCI": ("science",), "TLE": ("tle", "technologyandlivelihoodeducation")}


def subject_code(value, section=""):
    key = norm(value)
    key = {"liifeandcareerskills":"lifeandcareerskills", "worldreligion":"worldreligions"}.get(key,key)
    if section.startswith("G"):
        for code, aliases in JHS_SUBJECTS.items():
            if key in aliases or any(key.startswith(a) and key[len(a):].isdigit() for a in aliases):
                return section.split("-")[0] + code
    if key == "effectivecommunicationmabisangkomunikasyon":
        return "EC_MK"  # The source does not resolve the language-specific class.
    for code, aliases in SUBJECT_ALIASES.items():
        if key in aliases:
            return code
    return ""


def sheet_records(path, sheet_name):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        it = book[sheet_name].iter_rows(values_only=True)
        headers = [clean(v) for v in next(it)]
        return [{k: clean(v) for k, v in zip(headers, row) if k}
                for row in it if any(v is not None for v in row)]
    finally:
        book.close()


CLASS_SHEETS = ("JHS", "Grade 12 - A", "Grade 12 - B", "Grade 11 STEM", "Grade 11  BE", "Grade 11 ASSH")
TEACHER_SHEETS = ("JHS", "PE", "MATH&TECH", "PHYSCI", "BIOSCI", "HUMANITIES",
                  "FILIPINO", "ENGLISH", "SOCSCI (Finals)", "MARKETING", "ACCOUNTING")


def student_timetable(path):
    """Read explicit section blocks; ignore hidden templates and planning tabs."""
    book = load_workbook(path, data_only=True)
    results = []
    try:
        for name in CLASS_SHEETS:
            sheet = book[name]
            for col in range(2, sheet.max_column + 1, 7):
                section = ""
                for row in range(1, sheet.max_row + 1):
                    label = clean(sheet.cell(row, col).value)
                    found = section_code(label)
                    if found:
                        section = found
                        continue
                    if not section:
                        continue
                    for offset in range(1, 6):
                        cell = sheet.cell(row, col + offset)
                        value = clean(cell.value)
                        m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)\s*", value)
                        if not m:
                            continue
                        subject, alias = m.groups()
                        is_hr = norm(subject) == "homeroom"
                        code = "HOMEROOM" if is_hr else subject_code(subject, section)
                        results.append({"section_code": section, "subject_code": code,
                                        "subject_label": subject, "teacher_alias": alias,
                                        "source": f"{name}!{cell.coordinate}",
                                        "kind": "adviser" if is_hr else "subject"})
    finally:
        book.close()
    return results


def room_advisers(path):
    """The hidden room/adviser register is explicitly selected, not all hidden tabs."""
    book = load_workbook(path, data_only=True)
    result = []
    try:
        sheet = book["ROOM ASSIGNMENT"]
        for section_col, name_col in ((1, 2), (4, 5)):
            group = ""
            grade = 11
            for row in range(1, 54):
                left, right = clean(sheet.cell(row, section_col).value), clean(sheet.cell(row, name_col).value)
                if row >= 31:
                    grade = 12
                if norm(left) == "section":
                    group = right
                    continue
                if not group or not re.fullmatch(r"\d+[ABab]?", left) or not right:
                    continue
                code = section_code(f"{grade} {group} {left}")
                if code:
                    result.append({"section_code": code, "teacher_alias": right,
                                   "source": f"ROOM ASSIGNMENT!{sheet.cell(row,name_col).coordinate}"})
        for row in range(5, 13):
            result.append({"section_code": section_code(sheet.cell(row, 8).value),
                           "teacher_alias": clean(sheet.cell(row, 9).value),
                           "source": f"ROOM ASSIGNMENT!I{row}"})
    finally:
        book.close()
    return result


SECTION_IN_TEXT = re.compile(
    r"(?:Grade\s*)?(?:G(?:rade\s*)?(?:7|8|9|10)\s*-\s*\d+|"
    r"11\s*(?:Health\s*Science|Engineering\s*Science|HS|DT|ES|ArcD|ArtD|Arts\s*&\s*Design|Arts|A\s*&\s*D|AD|"
    r"M\s*&\s*L|M\s*&\s*E|MALS|ML|ME|PolSci|Psych|Psy|PS|THM|TH|AF|GS)\s*\d+|"
    r"12\s*(?:STEM|ABM|HUMSS|GAS|S|A|H|G)\s*\d+\s*[ABab]|"
    r"(?:STEM|ABM|HUMSS|GAS)\s*\d+\s*[ABab])", re.I)


def assignment_mode(value):
    """Classify assignment-local tags; never inherit a teacher's global load count."""
    text = clean(value)
    if re.search(r"\b(?:LTS|long[ -]*term\s*(?:sub|substitute))\b", text, re.I):
        return "long_term_sub"
    if re.search(r"\b(?:DS|daily\s*(?:sub|substitute))\b", text, re.I):
        return "daily_sub"
    if re.search(r"\b(?:OL|overload)\b", text, re.I):
        return "overload"
    if re.search(r"\bsub(?:stitute)?\s*:", text, re.I):
        return "substitute_unspecified"
    return "regular"


def assignment_annotations(path):
    """Keep conflicting current-workbook tags visible rather than guessing precedence."""
    book = load_workbook(path, data_only=True)
    rows = []
    try:
        for sheet_name, first, last, sec_col, alias_col in (
            ("SOCSCI (Finals)",64,95,17,19), ("Sheet2",2,18,1,2)):
            sheet=book[sheet_name]
            for rr in range(first,last+1):
                sec=section_code("12 "+clean(sheet.cell(rr,sec_col).value))
                value=clean(sheet.cell(rr,alias_col).value)
                for alias in re.split(r"\s*&\s*",value):
                    if sec and alias:
                        rows.append(dict(section_code=sec, subject_code="UCSP",
                            teacher_alias=alias, assignment_mode=assignment_mode(alias),
                            source=f"{sheet_name}!{sheet.cell(rr,alias_col).coordinate}"))
    finally:
        book.close()
    return rows


def teacher_timetable(path):
    book = load_workbook(path, data_only=True)
    result = []
    try:
        for name in TEACHER_SHEETS:
            sheet = book[name]
            for row in range(2, sheet.max_row + 1):
                for col in range(1, min(sheet.max_column, 28) + 1):
                    if norm(sheet.cell(row, col).value) != "time":
                        continue
                    if norm(sheet.cell(row, col + 1).value) != "monday":
                        continue
                    hr_row = row - 1
                    if clean(sheet.cell(hr_row, col).value).lower().startswith("homeroom:"):
                        hr_row -= 1
                    teacher = clean(sheet.cell(hr_row, col).value)
                    if not teacher:
                        continue
                    jhs_subject = clean(sheet.cell(hr_row, col + 3).value).split(":")[-1]
                    for rr in range(row + 1, sheet.max_row + 1):
                        if norm(sheet.cell(rr, col).value) == "time":
                            break
                        # Stop before another teacher's header, not at arbitrary row counts.
                        if rr + 1 <= sheet.max_row and norm(sheet.cell(rr + 1, col).value) == "time":
                            break
                        for cc in range(col + 1, min(col + 6, sheet.max_column + 1)):
                            cell = sheet.cell(rr, cc)
                            value = clean(cell.value)
                            m = SECTION_IN_TEXT.search(value)
                            if not m:
                                continue
                            raw_section = m.group()
                            if re.search(r"11\s*A\s*&?\s*D\s*\d+",raw_section,re.I) and re.search(r"\(STEM\)",value,re.I):
                                raw_section=re.sub(r"A\s*&?\s*D","ArcD",raw_section,flags=re.I)
                            if norm(raw_section).startswith(("stem", "abm", "humss", "gas")):
                                raw_section = "12 " + raw_section
                            code = section_code(raw_section)
                            if not code:
                                continue
                            subject = value[:m.start()] + value[m.end():]
                            subject = re.sub(r"\([^)]*\)", "", subject).strip(" -\n")
                            subject = re.sub(r"^\d.*?(?:AM|PM)\s*", "", subject, flags=re.I)
                            if name == "JHS":
                                subject = re.sub(r"\s+\d+.*$", "", jhs_subject)
                            mode=assignment_mode(value)
                            subject_id=subject_code(subject,code)
                            # A named subject's overload header can classify that subject only.
                            if mode=="regular" and subject_id and re.search(
                                r"\b"+re.escape(subject_id)+r"\s+(?:OL|Overload)\b",teacher,re.I):
                                mode="overload"
                            result.append({"section_code": code, "subject_code": subject_id,
                                           "subject_label": subject, "teacher_alias": teacher,
                                           "assignment_mode": mode, "raw_assignment":value,
                                           "source": f"{name}!{cell.coordinate}"})
    finally:
        book.close()
    return result


def teacher_name(value):
    value = re.sub(r"^Sub(?:stitute)?:\s*", "", clean(value), flags=re.I)
    value = re.sub(r"^Teacher:\s*", "", clean(value), flags=re.I).lstrip("*")
    value = re.sub(r"^Teacher\s+\d+\s+(?=[A-Za-z])", "", value, flags=re.I)
    value = re.split(r"\s*(?:\(|\s[-=]\s)", value)[0].strip()
    value = re.sub(r"\s+\d+\s+.*$", "", value)
    value = re.sub(r",?\s*(?:Jr\.?|Sr\.?)\s*$", "", value, flags=re.I)
    return value


class TeacherRegistry:
    """Explicit identity registry; never deduplicate ambiguous surnames."""
    def __init__(self, rows, aliases=None):
        self.rows = {r["employee_number"]: r for r in rows}
        self.aliases = {norm(k): v for k, v in (aliases or {}).items()}

    def candidates(self, value):
        name = teacher_name(value)
        if norm(value) in self.aliases:
            key = self.aliases[norm(value)]
            return [key] if key in self.rows else []
        if re.search(r"(?:^teacher\s*\d|^new\b|^soc\s*sci\s*\d|^ss\d|^nst$|[/&])", name, re.I):
            return []
        tokens = name_tokens(name)
        matches = []
        for key, row in self.rows.items():
            candidate = name_tokens(row["display_name"])
            if norm(name) == norm(row["display_name"]) or (tokens and tokens <= candidate):
                matches.append(key)
        return matches

    def resolve(self, value):
        matches=self.candidates(value)
        return matches[0] if len(matches)==1 else ""


def allocate_two(students, eligible, advisers, seed=20261023, minimum=20, maximum=None):
    """Minimum-cost bipartite flow via a totally-unimodular LP.

    The seed randomizes ties under teacher quotas, rather than promising a
    uniform sample of all feasible rosters. Results are persisted by the caller.
    """
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix

    by_section = defaultdict(list)
    for load in eligible:
        by_section[load["section_code"]].append(load)
    choices, contexts = {}, {}
    for student in sorted(students, key=lambda r: r["student_number"]):
        sid = student["student_number"]
        sec = student.get("teaching_section_code") or student["section_code"]
        if sec not in advisers:
            raise ValueError(f"Missing unique adviser for section {sec}")
        teachers = defaultdict(list)
        for load in by_section[sec]:
            if load["teacher_employee_number"] != advisers[sec]:
                teachers[load["teacher_employee_number"]].append(load)
        if len(teachers) < 2:
            raise ValueError(f"Section {sec} has fewer than two eligible non-adviser teachers")
        choices[sid] = sorted(teachers)
        for tid, loads in teachers.items():
            contexts[(sid, tid)] = min(loads, key=lambda r: hashlib.sha256(
                f"{seed}|context|{sid}|{r['assignment_key']}".encode()).digest())
    pairs = [(sid, tid) for sid in sorted(choices) for tid in choices[sid]]
    teacher_ids = sorted({tid for _, tid in pairs})
    if not pairs:
        raise ValueError("No allocation candidates")
    si = {s: i for i, s in enumerate(sorted(choices))}
    ti = {t: i for i, t in enumerate(teacher_ids)}
    pools = Counter(t for _, t in pairs)
    total = 2 * len(students)
    cap = maximum if maximum is not None else int(np.ceil(total / len(teacher_ids))) + 10
    lower = {t: min(minimum, pools[t]) for t in teacher_ids}
    upper = {t: min(cap, pools[t]) for t in teacher_ids}
    if any(lower[t] > upper[t] for t in teacher_ids):
        raise ValueError("Teacher minimum exceeds maximum")
    # Water-fill an equal-count target, capped by legitimate eligibility pools.
    target = {t: 0.0 for t in teacher_ids}
    remaining, active = float(total), set(teacher_ids)
    while active:
        level = remaining / len(active)
        saturated = {t for t in active if upper[t] < level}
        if not saturated:
            for t in active:
                target[t] = level
            break
        for t in saturated:
            target[t] = float(upper[t])
            remaining -= upper[t]
        active -= saturated
    n, nt, ns = len(pairs), len(teacher_ids), len(students)
    eq = lil_matrix((ns + nt, n + 2 * nt))
    for j, (sid, tid) in enumerate(pairs):
        eq[si[sid], j] = 1
        eq[ns + ti[tid], j] = 1
    for t, i in ti.items():
        eq[ns + i, n + 2*i] = -1
        eq[ns + i, n + 2*i+1] = 1
    # Fractional targets break integrality in the equality RHS. Round the
    # target vector to integers without changing its total before solving.
    rounded = {t: int(target[t]) for t in teacher_ids}
    for t in sorted(teacher_ids, key=lambda t: (-(target[t]-rounded[t]), t))[:total-sum(rounded.values())]:
        rounded[t] += 1
    # Explicit inequalities enforce quotas even when a rounded target lies
    # outside one teacher's bounds.
    bounds = [(0, 1)] * n + [(0, None)] * (2*nt)
    teacher_matrix = eq[ns:, :].tocsr()[:, :n]
    from scipy.sparse import hstack, vstack, csr_matrix
    zero = csr_matrix((nt, 2*nt))
    ub = vstack([hstack([teacher_matrix, zero]), hstack([-teacher_matrix, zero])]).tocsr()
    costs = [int.from_bytes(hashlib.sha256(f"{seed}|{s}|{t}".encode()).digest()[:8], "big") / 2**64 * .001 for s,t in pairs]
    costs += [1.] * (2*nt)
    solved = linprog(costs, A_eq=eq.tocsr(), b_eq=[2]*ns+[rounded[t] for t in teacher_ids],
                     A_ub=ub, b_ub=[upper[t] for t in teacher_ids]+[-lower[t] for t in teacher_ids],
                     bounds=bounds, method="highs")
    if not solved.success:
        raise ValueError("No feasible allocation under declared quotas: " + solved.message)
    if any(abs(v-round(v)) > 1e-6 for v in solved.x[:n]):
        raise ValueError("Allocation solver returned fractional assignments")
    selected = [(s,t) for (s,t), value in zip(pairs, solved.x[:n]) if value > .5]
    if Counter(s for s,_ in selected) != Counter({s:2 for s in choices}):
        raise ValueError("Allocation failed exact-two verification")
    counts = Counter(t for _,t in selected)
    if any(not lower[t] <= counts[t] <= upper[t] for t in teacher_ids):
        raise ValueError("Allocation failed teacher quota verification")
    result = [{"student_number": s, **contexts[(s,t)], "target_type": "subject_teacher"} for s,t in selected]
    summary = [{"teacher_employee_number":t,"eligible_students":pools[t],"minimum":lower[t],
                "maximum":upper[t],"allocated":counts[t]} for t in teacher_ids]
    return result, summary


def allocate_balanced(students, eligible, advisers, seed=20261023, minimum=20):
    """Find the smallest feasible global teacher cap, then minimize imbalance.

    The minimum is a declared invitation-count scenario, not a reliability
    threshold. Eligibility and adviser exclusion are never relaxed.
    """
    best,coverage=allocate_two(students,eligible,advisers,seed,minimum,len(students))
    low=0
    high=max(r['allocated'] for r in coverage)
    while low<high:
        middle=(low+high)//2
        try:
            selected,details=allocate_two(students,eligible,advisers,seed,minimum,middle)
        except ValueError as exc:
            if 'No feasible allocation' not in str(exc) and 'minimum exceeds maximum' not in str(exc):
                raise
            low=middle+1
        else:
            high=middle
            best,coverage=selected,details
    # best may come from the initial unconstrained trial when every lower cap
    # was infeasible. Re-solve at the proven cap for consistent metadata.
    return allocate_two(students,eligible,advisers,seed,minimum,high)
