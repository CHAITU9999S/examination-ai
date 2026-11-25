"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AdminSectionNavigation from "../admin/components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Exam = { id:number; title:string; subject?:string|null; duration_minutes:number; total_questions:number; start_time?:string|null; end_time?:string|null; max_marks?:number|null; created_by?:number };
type Student = { student_id:number; full_name:string; email:string; department?:string|null; is_active:boolean; session_id?:number|null; session_status?:string|null; student_exam_status:string };
type Review = { questions:Array<{question_order:number;evaluation_count:number; awarded_marks:number|null; maximum_marks:number; evaluation_history:Array<{evaluation_number:number;marks:number}>;is_objective:boolean}> };
type ResultRow = {session_id:number; student_id:number; result_published:boolean; obtained_marks:number|null; total_marks:number|null; grade:string|null; session_status:string};
function dateText(value?:string|null){if(!value)return "Not assigned";const d=new Date(value);return Number.isNaN(d.getTime())?"Not available":d.toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Kolkata"})+" IST";}
function statusText(value:string){return ({schedule_not_started:"Schedule not started yet",not_taken:"Exam not taken by the student",partially_attempted:"Partially attempted",completed:"Exam completed"} as Record<string,string>)[value]||value;}
export default function ExamStudentRoster({examId,readOnly=false}:{examId:string;readOnly?:boolean}){
 const router=useRouter();
 const [exam,setExam]=useState<Exam|null>(null);
 const [students,setStudents]=useState<Student[]>([]);
 const [results,setResults]=useState<ResultRow[]>([]);
 const [reviews,setReviews]=useState<Record<number,Review>>({});
 const [eligible,setEligible]=useState<Array<{id:number;full_name:string;email:string;department?:string|null}>>([]);
 const [selectedIds,setSelectedIds]=useState<number[]>([]);
 const [eligibleSearch,setEligibleSearch]=useState("");
 const [eligibleSort,setEligibleSort]=useState("name-asc");
 const [showAssign,setShowAssign]=useState(false);
 const [assignmentClosed,setAssignmentClosed]=useState(false);
 const [assignmentMessage,setAssignmentMessage]=useState("");
 const [search,setSearch]=useState("");
 const [sort,setSort]=useState("name-asc");
 const [loading,setLoading]=useState(true);
 const [saving,setSaving]=useState(false);
 const [error,setError]=useState("");
 const [dashboardHref,setDashboardHref]=useState(readOnly?"/admin/dashboard":"/examiner/dashboard");
 const [previousHref,setPreviousHref]=useState(readOnly?"/admin/sections/examinations":"/admin/sections/examinations");
 const getHeaders=useCallback(()=>{const token=localStorage.getItem("examguard_access_token");if(!token){router.replace("/login");return null;}return {Authorization:`Bearer ${token}`,"Content-Type":"application/json"};},[router]);
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const h=getHeaders();if(!h)return;
   const [profileR,examR,assignmentR,resultR]=await Promise.all([
    fetch(`${API_URL}/users/me`,{headers:h,cache:"no-store"}),
    fetch(`${API_URL}/exams/${examId}`,{headers:h,cache:"no-store"}),
    fetch(`${API_URL}/exams/${examId}/assignments`,{headers:h,cache:"no-store"}),
    fetch(`${API_URL}/results/exams/${examId}`,{headers:h,cache:"no-store"}),
   ]);
   const profile=await profileR.json().catch(()=>({}));const e=await examR.json().catch(()=>({}));const a=await assignmentR.json().catch(()=>({}));const r=await resultR.json().catch(()=>({}));
   if([profileR,examR,assignmentR].some(x=>x.status===401||x.status===403)){throw new Error(a.detail||e.detail||"You do not have permission to view this examination.");}
   if(!profileR.ok||!examR.ok||!assignmentR.ok)throw new Error(e.detail||a.detail||"Unable to load examination details.");
   if(readOnly&&profile.role!=="admin"){router.replace("/login");return;}
   if(!readOnly&&Number(e.created_by)!==Number(profile.id)){throw new Error("Only the examination creator can manage this examination.");}
   const admin=profile.role==="admin";setDashboardHref(admin?"/admin/dashboard":"/examiner/dashboard");setPreviousHref(readOnly?"/admin/exams":admin?"/staff/manage-exams":"/examiner/dashboard");
   setExam(e);setStudents(Array.isArray(a.students)?a.students:[]);setAssignmentClosed(Boolean(a.assignment_closed));
   setResults(Array.isArray(r.results)?r.results:[]);
   if(!readOnly&&!a.assignment_closed){const er=await fetch(`${API_URL}/exams/${examId}/eligible-students`,{headers:h,cache:"no-store"});const ed=await er.json().catch(()=>({}));if(er.ok)setEligible(Array.isArray(ed.students)?ed.students:[]);else if(er.status===409){setAssignmentClosed(true);setEligible([]);}else throw new Error(ed.detail||"Unable to load unassigned students.");}
   else setEligible([]);
   const completed=(Array.isArray(a.students)?a.students:[]).filter((s:Student)=>s.session_id&&["submitted","auto_submitted","expired"].includes(s.session_status||""));
   const reviewEntries=await Promise.all(completed.map(async(s:Student)=>{
    const response=await fetch(`${API_URL}/grading/sessions/${s.session_id}/review`,{headers:h,cache:"no-store"});
    if(!response.ok)return [s.student_id,null] as const;
    return [s.student_id,await response.json()] as const;
   }));
   setReviews(Object.fromEntries(reviewEntries.filter((x)=>x[1])));
  }catch(err){setError(err instanceof Error?err.message:"Unable to load examination.");}
  finally{setLoading(false);}
 },[examId,readOnly,router,getHeaders]);
 useEffect(()=>{void load();},[load]);
 const visible=useMemo(()=>[...students].filter(s=>!search.trim()||[s.full_name,s.email,s.department].some(v=>String(v||"").toLowerCase().includes(search.trim().toLowerCase()))).sort((a,b)=>{
  if(sort==="name-desc")return b.full_name.localeCompare(a.full_name);
  if(sort==="department")return String(a.department||"").localeCompare(String(b.department||""));
  if(sort==="status")return statusText(a.student_exam_status).localeCompare(statusText(b.student_exam_status));
  return a.full_name.localeCompare(b.full_name);
 }),[students,search,sort]);
 const resultBySession=Object.fromEntries(results.map(r=>[r.session_id,r]));
 const visibleEligible=useMemo(()=>[...eligible].filter(s=>!eligibleSearch.trim()||[s.full_name,s.email,s.department].some(v=>String(v||"").toLowerCase().includes(eligibleSearch.trim().toLowerCase()))).sort((a,b)=>eligibleSort==="name-desc"?b.full_name.localeCompare(a.full_name):eligibleSort==="department"?String(a.department||"").localeCompare(String(b.department||"")):a.full_name.localeCompare(b.full_name)),[eligible,eligibleSearch,eligibleSort]);
 async function assignSelected(){
  if(assignmentClosed){setAssignmentMessage("Exam has ended. New students cannot be assigned.");return;}
  if(selectedIds.length===0){setAssignmentMessage("Select at least one student.");return;}
  setSaving(true);setAssignmentMessage("");setError("");
  try{const h=getHeaders();if(!h)return;const response=await fetch(`${API_URL}/exams/${examId}/assignments`,{method:"POST",headers:h,body:JSON.stringify({student_ids:selectedIds})});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||"Unable to assign students.");setAssignmentMessage("Selected students were assigned successfully.");setSelectedIds([]);setShowAssign(false);await load();}
  catch(err){setAssignmentMessage(err instanceof Error?err.message:"Unable to assign students.");}
  finally{setSaving(false);}
 }
 if(loading)return <main className="min-h-screen bg-slate-950 p-10 text-center text-slate-300">Loading examination...</main>;
 return <main className="min-h-screen bg-slate-950 text-white">
  <header className="border-b border-white/10 bg-slate-900"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
   <div><Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">{readOnly?"Administrator / Examination viewing":"Manage Examination / Students"}</p></div>
   <AdminSectionNavigation previousHref={previousHref} previousLabel="Previous Section" dashboardHref={dashboardHref}/>
  </div></header>
  <div className="mx-auto max-w-7xl px-6 py-10">
   {error&&<div role="alert" className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
   {exam&&<section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-bold">{exam.title}</h1><p className="mt-1 text-slate-400">{exam.subject||"No subject"}</p></div>
     {!readOnly&&<button type="button" onClick={()=>{if(assignmentClosed){setAssignmentMessage("Exam has ended. New students cannot be assigned.");return;}setShowAssign(true);setAssignmentMessage("");}} className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold hover:bg-blue-500">＋ Assign to New Student</button>}
    </div>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 text-sm">
     <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">Start time</p><p className="mt-1">{dateText(exam.start_time)}</p></div>
     <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">End time</p><p className="mt-1">{dateText(exam.end_time)}</p></div>
     <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">Questions per student</p><p className="mt-1">{exam.total_questions}</p></div>
     <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">Maximum time</p><p className="mt-1">{exam.duration_minutes} minutes</p></div>
     <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">Maximum marks</p><p className="mt-1">{exam.max_marks??"Not available"}</p></div>
    </div>
   </section>}
   {assignmentMessage&&<div role="status" className="mt-5 rounded-xl border border-blue-400/30 bg-blue-500/10 p-4 text-sm text-blue-200">{assignmentMessage}</div>}
   {showAssign&&!readOnly&&<section className="mt-6 rounded-2xl border border-blue-400/30 bg-slate-900 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold">Assign New Students</h2><p className="text-sm text-slate-400">{eligible.length} unassigned student(s)</p></div><button type="button" onClick={()=>setShowAssign(false)} className="rounded-lg border border-white/20 px-3 py-2 text-sm">Close</button></div>
    {assignmentClosed?<p className="mt-4 text-amber-300">Exam has ended. New students cannot be assigned.</p>:eligible.length===0?<p className="mt-4 text-slate-400">No unassigned active students are available.</p>:<><div className="mt-4 flex flex-wrap gap-3"><input type="search" value={eligibleSearch} onChange={e=>setEligibleSearch(e.target.value)} placeholder="Search unassigned students" aria-label="Search unassigned students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm"/><select value={eligibleSort} onChange={e=>setEligibleSort(e.target.value)} aria-label="Sort unassigned students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm"><option value="name-asc">Name A to Z</option><option value="name-desc">Name Z to A</option><option value="department">Department</option></select></div><div className="mt-4 max-h-64 space-y-2 overflow-y-auto">{visibleEligible.length===0?<p className="p-4 text-sm text-slate-400">No students match your search.</p>:visibleEligible.map(s=><label key={s.id} className="flex items-center gap-3 rounded-lg bg-slate-800 p-3 text-sm"><input type="checkbox" checked={selectedIds.includes(s.id)} onChange={e=>setSelectedIds(current=>e.target.checked?[...current,s.id]:current.filter(id=>id!==s.id))}/><span className="flex-1">{s.full_name}<span className="ml-2 text-xs text-slate-400">{s.department||"Department not set"} · {s.email}</span></span></label>)}</div></>}
    <button type="button" onClick={assignSelected} disabled={saving||assignmentClosed||eligible.length===0} className="mt-4 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold disabled:opacity-50">{saving?"Assigning...":`Assign ${selectedIds.length} selected student(s)`}</button>
   </section>}
   <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Assigned Students</h2><p className="mt-1 text-sm text-slate-400">{visible.length} student(s)</p></div><div className="flex flex-wrap gap-3"><input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search student or department" aria-label="Search students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm"/><select value={sort} onChange={e=>setSort(e.target.value)} aria-label="Sort students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm"><option value="name-asc">Name A to Z</option><option value="name-desc">Name Z to A</option><option value="department">Department</option><option value="status">Exam status</option></select><button type="button" onClick={load} className="rounded-lg border border-white/20 px-3 py-2 text-sm">Refresh</button></div></div>
    {visible.length===0?<p className="py-10 text-center text-slate-400">No students are assigned to this examination.</p>:<div className="mt-5 space-y-3">{visible.map(student=>{
     const review=student.session_id?reviews[student.student_id]:undefined;const answers=review?.questions||[];const manualAnswers=answers.filter(q=>!q.is_objective);const graded=manualAnswers.filter(q=>q.awarded_marks!==null&&q.awarded_marks!==undefined);const latestEvaluation=Math.max(0,...manualAnswers.map(q=>q.evaluation_count||0));const result=student.session_id?resultBySession[student.session_id]:undefined;
     const evaluationLabel=student.student_exam_status!=="completed"?"Exam not completed":manualAnswers.length===0?"Automatically evaluated":graded.length===0?"Evaluate 0/3":`Evaluated ${latestEvaluation}/3 ${latestEvaluation>=3?"— no further evaluation":"— can evaluate again"}`;
     const gradeLabel=student.student_exam_status!=="completed"?"Exam not completed":manualAnswers.length>0&&!graded.length?"Not evaluated":result?.result_published?(result.grade||"Grade assigned"):"Grade not assigned";
     return <article key={student.student_id} className="rounded-xl border border-white/10 bg-slate-800/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{student.full_name}</h3><p className="mt-1 text-xs text-slate-400">{student.department||"Department not set"} · {student.email}</p><p className="mt-2 text-xs text-cyan-300">{statusText(student.student_exam_status)}</p></div><div className="flex flex-wrap gap-2">
       {student.session_id&&<Link href={`/staff/manage-exams/${examId}/evaluation/${student.session_id}${readOnly?"?view=1":""}`} className="rounded-lg border border-cyan-500/40 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10">{readOnly?"View Answers & Marks":"Evaluate Answers"}</Link>}
       {student.session_id&&<Link href={`/staff/proctoring?session_id=${student.session_id}`} className="rounded-lg border border-white/20 px-3 py-2 text-xs hover:bg-white/10">Proctoring Review</Link>}
      </div></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3 text-sm">
       <div className="rounded-lg bg-slate-900/70 p-3"><p className="text-xs text-slate-500">Evaluation</p><p className="mt-1 font-medium">{evaluationLabel}</p>{graded.map((q,i)=><p key={q.question_order} className="mt-1 text-xs text-slate-400">Q{q.question_order}: {q.evaluation_history.map(h=>h.marks).join(" → ")||q.awarded_marks} / {q.maximum_marks} · Latest: {q.awarded_marks}</p>)}</div>
       <div className="rounded-lg bg-slate-900/70 p-3"><p className="text-xs text-slate-500">Grade</p><p className="mt-1 font-medium">{gradeLabel}</p></div>
       <div className="rounded-lg bg-slate-900/70 p-3"><p className="text-xs text-slate-500">Result</p><p className="mt-1 font-medium">{result?.result_published?"Result published":result?"Evaluated — awaiting publication":"Not evaluated"}</p>{result&&<p className="mt-1 text-xs text-slate-400">Latest: {result.obtained_marks??"—"} / {result.total_marks??"—"}</p>}</div>
      </div>
     </article>;
    })}</div>}
   </section>
   <div className="mt-6 flex flex-wrap gap-3"><Link href={`/staff/examinations/${examId}`} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">View Question Paper</Link><Link href="/staff/proctoring" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">Open Proctoring Review</Link></div>
  </div>
 </main>;
}
