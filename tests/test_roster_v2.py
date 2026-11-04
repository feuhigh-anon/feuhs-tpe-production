import copy
from collections import Counter
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from feval.roster_v2 import TeacherRegistry, assignment_mode, allocate_two, allocate_balanced, section_code, subject_code
from scripts.prepare_roster_v2 import validate,prepare
from scripts.upload_roster_v2_staging import read_bundle


def reviewed():
    return {
        'Settings':[{'key':k,'value':v} for k,v in {
            'period_code':'TEST-FINALS','schedule_version':'Finals','exclude_adviser':'true',
            'seed':'42','review_status':'approved','minimum_teacher_count':'0'}.items()],
        'Students':[{'student_number':'2060001','display_name':'Synthetic Student',
            'email':'2060001@feuhighschool.edu.ph','section_code':'11GS01','review_status':'approved'}],
        'Teachers':[{'employee_number':t,'display_name':'Synthetic '+t,'review_status':'approved'} for t in ['A','B','C']],
        'SubjectLoads':[{'section_code':'11ME02','subject_code':s,'teacher_employee_number':t,
            'decision':'include','review_status':'approved','assignment_mode':'regular'} for s,t in [('MATH','A'),('SCI','B'),('ENG','C')]],
        'Homeroom':[{'section_code':'11ME02','adviser_employee_number':'A','program_code':'HR',
            'review_status':'approved'}],
        'Programs':[{'program_code':'HR','program_name':'Homeroom','school_level':'SHS','review_status':'approved'}],
        'SectionGroups':[{'section_code':'11GS01','teaching_section_code':'11ME02','review_status':'approved',
                          'review_notes':'Synthetic confirmed joint teaching group'}],
    }


class NormalizationTest(unittest.TestCase):
    def test_assignment_local_tags(self):
        for text,expected in [('11 HS6 (OL)','overload'),('Science (Overload)','overload'),
            ('Teacher (LTS)','long_term_sub'),('Teacher (Daily Sub)','daily_sub'),
            ('Teacher (DS)','daily_sub'),('Sub: Synthetic','substitute_unspecified'),
            ('12 STEM 2B','regular')]:
            self.assertEqual(assignment_mode(text),expected)

    def test_official_section_labels_and_distinct_pathways(self):
        self.assertEqual(section_code('11STEM-Health Science Sec. 12 (S.Y.26-27)'), '11HS12')
        self.assertEqual(section_code('Grade 11 ARCHITECHTURE AND DESIGN 1'), '11ARCD01')
        self.assertEqual(section_code('Grade 11 ARTS AND DESIGN 1'), '11AD01')
        self.assertEqual(section_code('Grade 7 - 1'), 'G07-1')
        self.assertEqual(section_code('12 STEM 10B'), '12S10b')

    def test_unknown_section_does_not_get_inferred(self):
        self.assertEqual(section_code('Grade 11 unknown 1'),'')
        self.assertEqual(section_code('7:30-8:30'),'')
        self.assertEqual(section_code('10:50-11:50'),'')

    def test_unicode_identity_and_ambiguous_surname(self):
        r=TeacherRegistry([{'employee_number':'1','display_name':'Cabueñas, Synthetic'},
                           {'employee_number':'2','display_name':'Cruz, Alpha'},
                           {'employee_number':'3','display_name':'Cruz, Beta'}])
        self.assertEqual(r.resolve('Cabuenas'),'1')
        self.assertEqual(r.resolve('Cruz'),'')
        self.assertEqual(r.resolve('Teacher 1 Alpha Cruz'),'2')
        self.assertEqual(r.resolve('New Science Teacher'),'')

    def test_subject_context_is_not_silently_collapsed(self):
        self.assertEqual(subject_code('Science','G07-1'),'G07SCI')
        self.assertEqual(subject_code('Science','G10-1'),'G10SCI')
        self.assertEqual(subject_code('Effective Communication / Mabisang Komunikasyon','11HS01'),'EC_MK')


class ReviewedContractTest(unittest.TestCase):
    def test_secondary_cannot_be_included(self):
        for mode in ['daily_sub','long_term_sub','substitute_unspecified','conflict','']:
            rows=reviewed();rows['SubjectLoads'][1]['assignment_mode']=mode
            self.assertTrue(any('Only regular/overload' in e for e in validate(rows)[0]))

    def test_overload_is_primary(self):
        rows=reviewed();rows['SubjectLoads'][1]['assignment_mode']='overload'
        self.assertEqual(validate(rows)[0],[])

    def test_section_group_preserves_official_membership(self):
        rows=reviewed();errors,_,_,_=validate(rows)
        self.assertEqual(errors,[])
        self.assertEqual(rows['Students'][0]['section_code'],'11GS01')
        self.assertEqual(rows['Students'][0]['teaching_section_code'],'11ME02')

    def test_unapproved_input_is_rejected(self):
        rows=reviewed();rows['Students'][0]['review_status']='needs_review'
        self.assertTrue(validate(rows)[0])

    def test_duplicate_student_is_rejected(self):
        rows=reviewed();rows['Students'].append(copy.deepcopy(rows['Students'][0]))
        self.assertTrue(validate(rows)[0])

    def test_undeclared_group_is_rejected(self):
        rows=reviewed();rows['SectionGroups']=[]
        rows['Students'][0]['teaching_section_code']='11ME02'
        self.assertTrue(validate(rows)[0])

    def test_program_level_mismatch_is_rejected(self):
        rows=reviewed();rows['Programs'][0]['school_level']='JHS'
        self.assertTrue(validate(rows)[0])

    def test_adviser_exclusion_can_make_roster_infeasible(self):
        rows=reviewed();rows['SubjectLoads']=rows['SubjectLoads'][:2]
        self.assertTrue(any('Fewer than two' in e for e in validate(rows)[0]))

    def test_shared_subject_needs_resolution(self):
        rows=reviewed();rows['SubjectLoads'][1]['subject_code']='MATH'
        self.assertTrue(any('Shared/duplicate' in e for e in validate(rows)[0]))

    def test_exclusion_without_reason_is_rejected(self):
        rows=reviewed();rows['SubjectLoads'][0]['decision']='exclude'
        self.assertTrue(any('review_notes' in e for e in validate(rows)[0]))


class AllocationTest(unittest.TestCase):
    def test_two_distinct_teachers_excludes_adviser_and_duplicate_subject(self):
        rows=reviewed();errors,_,eligible,homes=validate(rows)
        self.assertFalse(errors)
        eligible.append({**eligible[1],'assignment_key':'SECOND-B','subject_code':'BIO'})
        selected,coverage=allocate_two(rows['Students'],eligible,{'11ME02':'A'},seed=9,minimum=0)
        self.assertEqual(len(selected),2)
        self.assertEqual({r['teacher_employee_number'] for r in selected},{'B','C'})
        self.assertEqual({r['section_code'] for r in selected},{'11ME02'})

    def test_seed_is_reproducible_and_input_order_independent(self):
        students=[{'student_number':str(i),'section_code':'S'} for i in range(8)]
        eligible=[{'section_code':'S','teacher_employee_number':t,'assignment_key':t,'subject_code':t}
                  for t in ['A','B','C','D','E']]
        a,c=allocate_two(students,eligible,{'S':'A'},seed=12,minimum=0,maximum=5)
        b,d=allocate_two(list(reversed(students)),list(reversed(eligible)),{'S':'A'},seed=12,minimum=0,maximum=5)
        self.assertEqual(a,b);self.assertEqual(c,d)
        self.assertEqual(Counter(r['student_number'] for r in a),Counter({str(i):2 for i in range(8)}))
        self.assertTrue(all(r['allocated']<=5 for r in c))

    def test_infeasible_quota_does_not_silently_relax(self):
        students=[{'student_number':str(i),'section_code':'S'} for i in range(3)]
        loads=[{'section_code':'S','teacher_employee_number':t,'assignment_key':t,'subject_code':t}
               for t in ['A','B','C']]
        with self.assertRaisesRegex(ValueError,'No feasible allocation'):
            allocate_two(students,loads,{'S':'A'},minimum=0,maximum=1)

    def test_missing_adviser_blocks_allocation(self):
        with self.assertRaisesRegex(ValueError,'Missing unique adviser'):
            allocate_two([{'student_number':'1','section_code':'S'}],[],{},minimum=0)

    def test_minimax_finds_smallest_feasible_cap(self):
        students=[{'student_number':str(i),'section_code':'S'} for i in range(6)]
        loads=[{'section_code':'S','teacher_employee_number':t,'assignment_key':t,'subject_code':t}
               for t in ['A','B','C','D']]
        selected,coverage=allocate_balanced(students,loads,{'S':'A'},minimum=0)
        self.assertEqual(max(r['allocated'] for r in coverage),4)
        self.assertEqual(len(selected),12)


class BundleTest(unittest.TestCase):
    def test_reviewed_bundle_has_four_targets_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'synthetic.xlsx';source.write_bytes(b'synthetic fixture')
            with patch('scripts.prepare_roster_v2.reviewed_rows',return_value=reviewed()):
                manifest=prepare(source,root/'bundle')
            self.assertEqual(manifest['counts']['evaluation_allocations'],4)
            m,digest,payload=read_bundle(root/'bundle')
            self.assertEqual(len(payload['evaluation_allocations']),4)
            self.assertEqual({r['section_code'] for r in payload['evaluation_allocations']},{'11GS01'})
            self.assertEqual({r['teaching_section_code'] for r in payload['evaluation_allocations']},{'11ME02'})
            with (root/'bundle/students.csv').open('a') as handle:
                handle.write('tampered\n')
            with self.assertRaisesRegex(ValueError,'checksum'):
                read_bundle(root/'bundle')

    def test_rejected_review_creates_no_release_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'synthetic.xlsx';source.write_bytes(b'synthetic fixture')
            rows=reviewed();rows['Teachers'][0]['review_status']='needs_review'
            with patch('scripts.prepare_roster_v2.reviewed_rows',return_value=rows):
                with self.assertRaisesRegex(ValueError,'Roster rejected'):
                    prepare(source,root/'bundle')
            self.assertFalse((root/'bundle').exists())


if __name__=='__main__':
    unittest.main()
