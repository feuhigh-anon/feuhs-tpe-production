// Render the private offline review dataset with the bundled spreadsheet runtime.
import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const input=process.argv[2];
if (!input) throw new Error('Usage: node render_roster_workbook.mjs <review-directory>');
const data=JSON.parse(await fs.readFile(path.join(input,'workbook_data.json'),'utf8'));
const manifest=JSON.parse(await fs.readFile(path.join(input,'manifest.json'),'utf8'));
const teacherNames=new Map(data.Teachers.map(r=>[r.employee_number,r.display_name]));
const targetRows=new Map();
for(const row of data.Allocations) {
 if(!targetRows.has(row.student_number)) targetRows.set(row.student_number,[]);
 targetRows.get(row.student_number).push(row);
}
data.StudentRoster=data.Students.map(student=>{
 const targets=targetRows.get(student.student_number)??[];
 const subject=targets.filter(r=>r.target_type==='subject_teacher').sort((a,b)=>Number(a.slot)-Number(b.slot));
 const adviser=targets.find(r=>r.target_type==='homeroom_adviser');
 const program=targets.find(r=>r.target_type==='homeroom_program');
 return {student_number:student.student_number,student_name:student.display_name,
   official_section:student.section_code,teaching_section:student.teaching_section_code,
   subject_teacher_1:teacherNames.get(subject[0]?.teacher_employee_number)??'',
   subject_1:subject[0]?.subject_code??'',
   subject_teacher_2:teacherNames.get(subject[1]?.teacher_employee_number)??'',
   subject_2:subject[1]?.subject_code??'',
   homeroom_adviser:teacherNames.get(adviser?.teacher_employee_number)??'',
   homeroom_program:program?.program_code??'',status:'provisional'};
});
const wb=Workbook.create();
const summary=wb.worksheets.add('Review');
summary.showGridLines=false;
const summaryRows=[['Roster review','Finals'],['Status','Pending reconciliation and approval'],
 ['Students',manifest.students],['Required subject allocations',manifest.required_subject_evaluations],
 ['Computed subject allocations',manifest.allocated_subject_evaluations],['Required evaluation slots',manifest.four_slot_rows],
 ['Blocked slots',manifest.blocked_slots],['Adviser exclusion','Required'],
 ['Allocation status','Provisional until the source roster is approved.'],
 ['Review step','Resolve Issues and approve canonical input sheets before preparation.'],
 ['Program names','Proposed JHS/SHS homeroom labels; confirm during review.'],
 ['Official section','Retained separately from mixed teaching groups.']];
summary.getRange('A2:B13').values=summaryRows;
summary.getRange('A2:B13').format.font={name:'Arial',size:11};
summary.getRange('A2:A13').format.columnWidth=38;
summary.getRange('B2:B13').format.columnWidth=86;
summary.getRange('A2:B2').format.font={name:'Arial',size:14,bold:true};
summary.getRange('A3:B3').format.fill='#FFF2CC';
summary.getRange('A2:B13').format.rowHeight=24;
const order=['StudentRoster','Allocations','TeacherCoverage','Students','Sections','Teachers','SubjectLoads','AssignmentEvidence','Homeroom','Programs','SectionGroups','TeacherAliases','Settings','Issues'];
for (const name of order) {
 let rows=data[name]??[];
 if(name==='Allocations') {
   const names=new Map(data.Students.map(r=>[r.student_number,r.display_name]));
   const teacherNames=new Map(data.Teachers.map(r=>[r.employee_number,r.display_name]));
   rows=rows.map(r=>({student_number:r.student_number,student_name:names.get(r.student_number)??'',
     section_code:r.section_code,target_type:r.target_type,
     teacher_name:teacherNames.get(r.teacher_employee_number)??'',subject_code:r.subject_code,
     ...r}));
 }
 if(name==='TeacherCoverage') {
   const names=new Map(data.Teachers.map(r=>[r.employee_number,r.display_name]));
   rows=rows.map(r=>({teacher_employee_number:r.teacher_employee_number,
     teacher_name:names.get(r.teacher_employee_number)??'',...r}));
 }
 const sheet=wb.worksheets.add(name);
 sheet.showGridLines=false;
 let columns=rows.length?Object.keys(rows[0]):(name==='SectionGroups'?['section_code','teaching_section_code','review_status','review_notes']:['status']);
 const matrix=[columns,...rows.map(r=>columns.map(c=>{
   const v=r[c]??'';
   return typeof v==='string' && /^[=+@]/.test(v)?"'"+v:v;
 }))];
 sheet.getRangeByIndexes(0,0,matrix.length,columns.length).values=matrix;
 const used=sheet.getRangeByIndexes(0,0,matrix.length,columns.length);
 used.format.font={name:'Arial',size:10};
 used.format.columnWidth=25;
 used.format.rowHeight=20;
 sheet.getRangeByIndexes(0,0,1,columns.length).format={fill:'#244B3C',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:34,wrapText:true};
 sheet.freezePanes.freezeRows(1);
 columns.forEach((column,index)=>{
   if (/number|code|key|employee|slot/.test(column)) sheet.getRangeByIndexes(1,index,Math.max(rows.length,1),1).setNumberFormat('@');
   if (/name|source_alias|subject_teacher|homeroom_adviser/.test(column)) sheet.getRangeByIndexes(0,index,matrix.length,1).format.columnWidth=38;
   if (/source_cells|detail|notes/.test(column)) sheet.getRangeByIndexes(0,index,matrix.length,1).format.columnWidth=58;
   if (['review_status','decision','review_notes'].includes(column)) sheet.getRangeByIndexes(1,index,Math.max(rows.length,1),1).format.fill='#FFF2CC';
   if(['subject_name','source_alias','detail'].includes(column)) {
     sheet.getRangeByIndexes(1,index,Math.max(rows.length,1),1).format.wrapText=true;
     sheet.getRangeByIndexes(1,0,Math.max(rows.length,1),columns.length).format.rowHeight=52;
   }
   if(name==='Settings' && column==='key') sheet.getRangeByIndexes(0,index,matrix.length,1).format.columnWidth=36;
 });
 if (rows.length) sheet.tables.add(sheet.getRangeByIndexes(0,0,matrix.length,columns.length),true,name+'Table');
}
wb.recalculate();
console.log((await wb.inspect({kind:'region',sheetId:'Review',range:'A2:B13',maxChars:1800,tableMaxRows:12,tableMaxCols:2})).ndjson);
// Every data sheet has the same tabular layout; inspect its header and first
// rows visually without rendering the full private roster.
for(const name of ['Review',...order]) {
 const sheet=wb.worksheets.getItem(name);
 const endRow=name==='Review'?13:Math.min((data[name]?.length??0)+1,5);
 const preview=await wb.render({sheetName:name,range:name==='Review'?'A2:B13':`A1:D${Math.max(endRow,2)}`,scale:1.5,format:'png'});
 await fs.writeFile(path.join(input,`preview_${name}.png`),new Uint8Array(await preview.arrayBuffer()),{mode:0o600});
}
const file=await SpreadsheetFile.exportXlsx(wb);
const destination=path.join(input,'Finals_Roster_Review.xlsx');
await file.save(destination);
await fs.chmod(destination,0o600);
console.log(destination);
