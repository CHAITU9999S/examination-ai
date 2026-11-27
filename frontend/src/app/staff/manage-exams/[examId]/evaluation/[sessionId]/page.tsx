"use client";
import { formatISTDateTime } from "@/lib/utils";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type HistoryItem={evaluation_number:number;marks:number;created_at?:string|null};
type QuestionReview={
 question_id:number;question_order:number;question_text:string;question_image_url?:string|null;expected_answer_image_url?:string|null;question_type:string;difficulty:string;
 maximum_marks:number;negative_marks?:number|null;expected_answer?:string|null;model_answer_text?:string|null;
 options:Array<{id:number;option_text:string;is_correct:boolean}>;
 answer_id:number|null;answer_text?:string|null;selected_options?:string[];answer_image_url?:string|null;
 ai_suggested_marks?:number|null;ai_justification?:string|null;awarded_marks?:number|null;
 evaluation_count:number;evaluation_history:HistoryItem[];examiner_feedback?:string|null;is_objective:boolean;
};
type ReviewData={session_id:number;exam_id:number;exam_title:string;subject?:string|null;exam_details?:{duration_minutes?:number|null;total_questions?:number|null;total_marks?:number|null;negative_marking_enabled?:boolean|null;proctoring_enabled?:boolean|null;max_tab_switch_warnings?:number|null;start_time?:string|null;end_time?:string|null;creator_name?:string|null};positive_marks_earned?:number|null;negative_marks_deducted?:number|null;maximum_positive_marks?:number|null;configured_negative_marks?:number|null;evaluated_questions?:number|null;correct_questions?:number|null;wrong_questions?:number|null;partially_correct_questions?:number|null;creator_name?:string|null;creator_role?:string|null;assigned_by_name?:string|null;assigned_by_role?:string|null;student_id:number;student_name:string;department?:string|null;session_status:string;started_at?:string|null;submitted_at?:string|null;face_photo_url?:string|null;result_published:boolean;result_obtained_marks?:number|null;result_total_marks?:number|null;result_grade?:string|null;questions:QuestionReview[]};
function dateText(value?:string|null){return formatISTDateTime(value, "—");}
function SessionEvaluationPageContent(){
 const params=useParams<{examId:string;sessionId:string}>();
 const router=useRouter();const search=useSearchParams();
 const examId=String(params.examId||"");const sessionId=String(params.sessionId||"");
 const readOnly=search.get("view")==="1";
 const [viewerRole,setViewerRole]=useState<"admin"|"examiner"|null>(null);
 const dashboardHref=viewerRole==="examiner"?"/examiner/dashboard":"/admin/dashboard";
 useEffect(()=>{
  if(!readOnly)return;
  let cancelled=false;
  const token=localStorage.getItem("examguard_access_token");
  if(!token){router.replace("/login");return;}
  fetch(`${API_URL}/users/me`,{headers:{Authorization:`Bearer ${token}`},cache:"no-store"})
   .then(response=>response.ok?response.json():null)
   .then(profile=>{
    if(cancelled)return;
    if(profile?.role==="admin"||profile?.role==="examiner")setViewerRole(profile.role);
    else if(profile)router.replace("/login");
   })
   .catch(()=>{if(!cancelled)setViewerRole(null);});
  return()=>{cancelled=true;};
 },[readOnly,router]);
 const requestedReturnTo=search.get("return_to");
 const previousHref=readOnly&&requestedReturnTo&&requestedReturnTo.startsWith("/admin/")&&!requestedReturnTo.startsWith("//")
  ? requestedReturnTo
  : readOnly? `/admin/exams/${examId}` : `/staff/manage-exams/${examId}`;
 const [data,setData]=useState<ReviewData|null>(null);const [index,setIndex]=useState(0);
 const [marks,setMarks]=useState("");const [feedback,setFeedback]=useState("");const [grade,setGrade]=useState("");
 const [photo,setPhoto]=useState("");const [questionImage,setQuestionImage]=useState("");const [expectedAnswerImage,setExpectedAnswerImage]=useState("");const [answerImage,setAnswerImage]=useState("");const [suggestion,setSuggestion]=useState<{suggested_marks:number;justification:string;matched_points?:string[];missed_points?:string[]}|null>(null);
 const [loading,setLoading]=useState(true);const [working,setWorking]=useState(false);const [error,setError]=useState("");const [message,setMessage]=useState("");
 const headers=()=>{const token=localStorage.getItem("examguard_access_token");if(!token){router.replace("/login");return null;}return {Authorization:`Bearer ${token}`,"Content-Type":"application/json"};};
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const h=headers();if(!h)return;const response=await fetch(`${API_URL}/grading/sessions/${sessionId}/review`,{headers:h,cache:"no-store"});const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(result.detail||"Unable to load student answers.");setData(result);setGrade(result.result_grade||"");}
  catch(err){setError(err instanceof Error?err.message:"Unable to load evaluation.");}
  finally{setLoading(false);}
 },[sessionId]);
 useEffect(()=>{void load();},[load]);
 const current=data?.questions[index]||null;
 useEffect(()=>{
  if(!data?.face_photo_url){setPhoto("");return;}
  let cancelled=false;let objectUrl:string|null=null;const token=localStorage.getItem("examguard_access_token");if(!token)return;
  fetch(API_URL+data.face_photo_url,{headers:{Authorization:`Bearer ${token}`},cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Photo unavailable");return r.blob();}).then(blob=>{objectUrl=URL.createObjectURL(blob);if(!cancelled)setPhoto(objectUrl);else URL.revokeObjectURL(objectUrl);}).catch(()=>{if(!cancelled)setPhoto("");});
  return()=>{cancelled=true;if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[data?.face_photo_url]);
 useEffect(()=>{setMarks(current?.awarded_marks!==null&&current?.awarded_marks!==undefined?String(current.awarded_marks):current?.ai_suggested_marks!==null&&current?.ai_suggested_marks!==undefined?String(current.ai_suggested_marks):"");setFeedback(current?.examiner_feedback||"");setSuggestion(current?.ai_suggested_marks!==null&&current?.ai_suggested_marks!==undefined?{suggested_marks:current.ai_suggested_marks,justification:current.ai_justification||"Saved AI suggestion"}:null);setError("");setMessage("");},[current?.answer_id,current?.awarded_marks,current?.ai_suggested_marks,current?.examiner_feedback]);
 useEffect(()=>{
  if(!current?.question_image_url){setQuestionImage("");return;}
  let cancelled=false;let objectUrl:string|null=null;const token=localStorage.getItem("examguard_access_token");if(!token)return;
  fetch(API_URL+current.question_image_url,{headers:{Authorization:`Bearer ${token}`},cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Question image unavailable");return r.blob();}).then(blob=>{objectUrl=URL.createObjectURL(blob);if(!cancelled)setQuestionImage(objectUrl);else URL.revokeObjectURL(objectUrl);}).catch(()=>{if(!cancelled)setQuestionImage("");});
  return()=>{cancelled=true;if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[current?.question_image_url]);
 useEffect(()=>{
  if(!current?.expected_answer_image_url){setExpectedAnswerImage("");return;}
  let cancelled=false;let objectUrl:string|null=null;const token=localStorage.getItem("examguard_access_token");if(!token)return;
  fetch(API_URL+current.expected_answer_image_url,{headers:{Authorization:`Bearer ${token}`},cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Expected answer image unavailable");return r.blob();}).then(blob=>{objectUrl=URL.createObjectURL(blob);if(!cancelled)setExpectedAnswerImage(objectUrl);else URL.revokeObjectURL(objectUrl);}).catch(()=>{if(!cancelled)setExpectedAnswerImage("");});
  return()=>{cancelled=true;if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[current?.expected_answer_image_url]);
 useEffect(()=>{
  if(!current?.answer_image_url){setAnswerImage("");return;}
  let cancelled=false;let objectUrl:string|null=null;const token=localStorage.getItem("examguard_access_token");if(!token)return;
  fetch(API_URL+current.answer_image_url,{headers:{Authorization:`Bearer ${token}`},cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Unable to load answer image");return r.blob();}).then(blob=>{objectUrl=URL.createObjectURL(blob);if(!cancelled)setAnswerImage(objectUrl);else URL.revokeObjectURL(objectUrl);}).catch(()=>{if(!cancelled)setAnswerImage("");});
  return()=>{cancelled=true;if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[current?.answer_image_url]);

 async function requestSuggestion(){
  if(!current?.answer_id||readOnly)return;setWorking(true);setError("");setMessage("");
  try{const h=headers();if(!h)return;const response=await fetch(`${API_URL}/grading/answers/${current.answer_id}/ai-suggestion`,{method:"POST",headers:h});const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(result.detail||"Unable to generate AI suggestion.");setSuggestion(result);setMarks(String(result.suggested_marks));}
  catch(err){setError(err instanceof Error?err.message:"AI suggestion failed.");}finally{setWorking(false);}
 }
 async function saveMarks(){
  if(!current?.answer_id||readOnly)return;const value=Number(marks);if(marks.trim()===""||!Number.isFinite(value)||value<0||value>current.maximum_marks){setError(`Enter marks between 0 and ${current.maximum_marks}.`);return;}
  setWorking(true);setError("");setMessage("");
  try{const h=headers();if(!h)return;const response=await fetch(`${API_URL}/grading/answers/${current.answer_id}/grade`,{method:"POST",headers:h,body:JSON.stringify({awarded_marks:value,examiner_feedback:feedback.trim()||null})});const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(result.detail||"Unable to save marks.");setMessage("Marks saved. The latest evaluation will be used for the student's result.");await load();}
  catch(err){setError(err instanceof Error?err.message:"Unable to save marks.");}finally{setWorking(false);}
 }
 async function publishResult(){
  if(readOnly||!data)return;setWorking(true);setError("");setMessage("");
  try{const h=headers();if(!h)return;const response=await fetch(`${API_URL}/grading/sessions/${sessionId}/publish`,{method:"POST",headers:h,body:JSON.stringify({grade:grade.trim()||null})});const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(result.detail||"Unable to publish result.");setMessage("Result published successfully to the student's account.");await load();}
  catch(err){setError(err instanceof Error?err.message:"Unable to publish result.");}finally{setWorking(false);}
 }
 if(loading)return <main className="min-h-screen bg-slate-950 p-10 text-center text-slate-300">Loading student evaluation...</main>;
 if(!data)return <main className="min-h-screen bg-slate-950 p-10 text-white"><p>{error||"Evaluation unavailable."}</p><Link href={previousHref} className="mt-4 inline-block text-cyan-300">← Previous Section</Link></main>;
 const question=current;
 const resultPercentage=data.result_total_marks!==null&&data.result_total_marks!==undefined&&Number(data.result_total_marks)>0&&data.result_obtained_marks!==null&&data.result_obtained_marks!==undefined?Number(data.result_obtained_marks)/Number(data.result_total_marks)*100:null;
 const allSubjectiveComplete=data.questions.filter(q=>!q.is_objective&&q.answer_id).every(q=>q.awarded_marks!==null&&q.awarded_marks!==undefined);
 const evaluationCount=question?.evaluation_count||0;
 const canPublish=data.session_status==="submitted"||data.session_status==="auto_submitted";
 return <main className="min-h-screen bg-slate-950 text-white">
  <header className="border-b border-white/10 bg-slate-900"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
   <div><Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">{readOnly?`${viewerRole==="examiner"?"Examiner":"Admin"} / Read-only answer review`:"Examination Evaluation"}</p></div>
   <div className="flex flex-wrap gap-2"><Link href={previousHref} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Previous Section</Link><Link href={dashboardHref} className="rounded-lg border border-blue-400/40 px-4 py-2 text-sm text-blue-300">Dashboard</Link></div>
  </div></header>
  <div className="mx-auto max-w-6xl px-5 py-8">
   {error&&<div role="alert" className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
   {message&&<div role="status" className="mb-5 rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-300">{message}</div>}
   <section className="rounded-2xl border border-white/10 bg-slate-900 p-5">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-bold">{data.exam_title}</h1><p className="mt-1 text-slate-300">{data.student_name} · {data.department||"Department not set"}</p><p className="mt-1 text-xs text-slate-400">Created by: {data.creator_name||"Unknown"} · Assigned by: {data.assigned_by_name||"Unknown"}</p><p className="mt-2 text-xs text-slate-400">Started: {dateText(data.started_at)} · Submitted: {dateText(data.submitted_at)}</p></div>
     {data.face_photo_url&&<figure className="w-28 rounded-lg border border-white/10 bg-slate-800 p-2 text-center">{photo?<img src={photo} alt="Student face captured when examination started" className="h-24 w-full rounded object-cover"/>:<div className="flex h-24 items-center justify-center text-xs text-slate-400">Photo unavailable</div>}<figcaption className="mt-1 text-[10px] text-slate-400">Start photo</figcaption></figure>}
    </div>
   </section>
   <section className="mt-5 rounded-2xl border border-white/10 bg-slate-900 p-5">
    <h2 className="text-lg font-bold">Examination Performance Summary</h2>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Questions in assigned paper</p><p className="mt-1 text-2xl font-bold">{data.questions.length}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Final marks</p><p className="mt-1 text-2xl font-bold">{data.result_published&&data.result_obtained_marks!==null&&data.result_obtained_marks!==undefined?`${data.result_obtained_marks} / ${data.result_total_marks}`:"Not published"}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Percentage</p><p className="mt-1 text-2xl font-bold">{data.result_published&&resultPercentage!==null?`${resultPercentage.toFixed(2)}%`:"Not published"}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Grade / status</p><p className="mt-1 text-2xl font-bold">{data.result_published?data.result_grade||"—":data.session_status.replaceAll("_"," ")}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Positive marks earned</p><p className="mt-1 text-xl font-bold">{data.positive_marks_earned??"Not evaluated"}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Negative marks deducted</p><p className="mt-1 text-xl font-bold">{data.negative_marks_deducted??"Not evaluated"}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Correct / Wrong</p><p className="mt-1 text-xl font-bold">{data.correct_questions??"—"} / {data.wrong_questions??"—"}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><p className="text-xs text-slate-400">Partially correct / evaluated</p><p className="mt-1 text-xl font-bold">{data.partially_correct_questions??"—"} / {data.evaluated_questions??"—"}</p></div>
    </div>
    <div className="mt-4 grid gap-2 rounded-xl bg-slate-800/70 p-4 text-sm text-slate-300 sm:grid-cols-2">
     <p>Subject: {data.subject||"Not available"}</p>
     <p>Duration: {data.exam_details?.duration_minutes!=null?`${data.exam_details.duration_minutes} minutes`:"Not available"}</p>
     <p>Total / maximum marks: {data.result_total_marks??data.exam_details?.total_marks??"Not available"}</p>
     <p>Positive marks available: {data.maximum_positive_marks??"Not available"}</p>
     <p>Configured negative marks: {data.configured_negative_marks??"Not available"}</p>
     <p>Negative marking: {data.exam_details?.negative_marking_enabled==null?"Not available":data.exam_details.negative_marking_enabled?"Enabled":"Disabled"}</p>
     <p>AI proctoring: {data.exam_details?.proctoring_enabled==null?"Not available":data.exam_details.proctoring_enabled?"Enabled":"Disabled"}</p>
     <p>Maximum tab-switch warnings: {data.exam_details?.max_tab_switch_warnings??"Not available"}</p>
     <p>Starts: {data.exam_details?.start_time?dateText(data.exam_details.start_time):"Not available"}</p>
     <p>Ends: {data.exam_details?.end_time?dateText(data.exam_details.end_time):"Not available"}</p>
    </div>
    {!data.result_published&&<p className="mt-3 text-xs text-amber-300">The result has not been published. Current per-question evaluation marks are shown below to authorized staff.</p>}
   </section>
   <section className="mt-5 rounded-2xl border border-white/10 bg-slate-900 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-slate-400">Question {question?index+1:0} of {data.questions.length}</p><h2 className="mt-1 text-xl font-bold">Student Answer Review</h2></div><p className="text-sm text-slate-400">{question?.question_type} · {question?.difficulty} · {question?.maximum_marks} positive marks · {question?.negative_marks??0} negative marks</p></div>
    
    {question&&<div className="mt-6 space-y-5">
     <div><h3 className="text-sm font-semibold text-slate-400">Published question</h3><p className="mt-2 whitespace-pre-wrap">{question.question_text}</p>{questionImage&&<img src={questionImage} alt="Examination question image" className="mt-3 max-h-64 max-w-full rounded-lg border border-white/10 object-contain"/>}{question.options.length>0&&<ul className="mt-3 space-y-2 text-sm text-slate-300">{question.options.map(o=><li key={o.id} className="rounded-lg bg-slate-800 p-2">{o.option_text}{o.is_correct&&<span className="ml-2 text-green-300">(Correct answer)</span>}</li>)}</ul>}</div>
     <div><h3 className="text-sm font-semibold text-slate-400">Expected answer</h3><p className="mt-2 whitespace-pre-wrap text-slate-300">{question.expected_answer||"No written expected answer provided."}</p>{expectedAnswerImage&&<img src={expectedAnswerImage} alt="Published expected answer image" className="mt-3 max-h-64 max-w-full rounded-lg border border-white/10 object-contain"/>}</div>
     {question.model_answer_text&&<div><h3 className="text-sm font-semibold text-slate-400">Model answer</h3><p className="mt-2 whitespace-pre-wrap text-slate-300">{question.model_answer_text}</p></div>}
     <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/5 p-4"><h3 className="text-sm font-semibold text-cyan-200">Final marks awarded for this question</h3><p className="mt-2 text-xl font-bold tabular-nums">{question.awarded_marks!==null&&question.awarded_marks!==undefined?question.awarded_marks:"Not evaluated"} / {question.maximum_marks}</p></div>
     <div className="rounded-xl bg-slate-800 p-4"><h3 className="text-sm font-semibold text-slate-400">Student's submitted answer</h3><>{question.selected_options&&question.selected_options.length>0?<ul className="mt-2 list-disc space-y-1 pl-5">{question.selected_options.map((option,i)=><li key={`${i}-${option}`} className="whitespace-pre-wrap">{option}</li>)}</ul>:<p className="mt-2 whitespace-pre-wrap">{question.answer_text||"No text answer submitted."}</p>}</>{question.answer_image_url&&<div className="mt-3">{answerImage?<img src={answerImage} alt="Student uploaded answer image" className="max-h-[480px] max-w-full rounded-lg border border-white/10 object-contain"/>:<p className="text-xs text-slate-400">Loading uploaded answer image...</p>}</div>}</div>
     {question.is_objective&&<p className="rounded-lg border border-blue-400/20 bg-blue-500/5 p-3 text-sm text-blue-200">Objective question — automatically evaluated marks: {question.awarded_marks??"Not available"} / {question.maximum_marks}</p>}
     {!question.is_objective&&<div className="space-y-4 rounded-xl border border-white/10 bg-slate-800/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">AI suggested marks and human evaluation</h3><span className="text-xs text-slate-400">Evaluation {evaluationCount}/3</span></div>
      {suggestion&&<div className="rounded-lg bg-slate-900 p-3 text-sm"><p>AI suggestion: <strong>{suggestion.suggested_marks} / {question.maximum_marks}</strong></p><p className="mt-1 text-xs text-slate-400">{suggestion.justification||"No justification available."}</p></div>}
      {question.evaluation_history.length>0&&<div><p className="text-xs font-semibold text-slate-400">Evaluation marks history</p><div className="mt-2 flex flex-wrap gap-2">{question.evaluation_history.map(h=><span key={h.evaluation_number} className={h.evaluation_number===evaluationCount?"rounded-lg border border-green-400/50 bg-green-500/10 px-3 py-2 text-sm text-green-200":"rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-300"}>Evaluation {h.evaluation_number}: {h.marks}{h.evaluation_number===evaluationCount?" · Latest":""}</span>)}</div></div>}
      {!readOnly&&<><div className="flex flex-wrap gap-2"><button type="button" onClick={requestSuggestion} disabled={working||evaluationCount>=3||!question.answer_id} className="rounded-lg border border-cyan-500/40 px-3 py-2 text-sm text-cyan-300 disabled:opacity-50">{working?"Working...":"Get AI Suggestion"}</button></div>
       <label className="block text-sm">Evaluator marks<input type="number" min="0" max={question.maximum_marks} step="0.01" value={marks} onChange={e=>setMarks(e.target.value)} disabled={working||evaluationCount>=3} className="mt-2 block w-full rounded-lg border border-white/15 bg-slate-900 px-3 py-2 text-white disabled:opacity-50"/></label>
       <label className="block text-sm">Optional feedback<textarea value={feedback} onChange={e=>setFeedback(e.target.value)} disabled={working||evaluationCount>=3} rows={3} className="mt-2 block w-full rounded-lg border border-white/15 bg-slate-900 px-3 py-2 text-white disabled:opacity-50"/></label>
       <button type="button" onClick={saveMarks} disabled={working||evaluationCount>=3||!question.answer_id} className="rounded-lg bg-green-600 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">{working?"Saving...":evaluationCount>=3?"Evaluation limit reached":"Save Evaluation"}</button>
      </>}
      {readOnly&&<p className="text-xs text-slate-400">Read-only: marks, feedback, and evaluation history are visible but cannot be changed here.</p>}
     </div>}
    </div>}
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4"><button type="button" onClick={()=>setIndex(i=>Math.max(0,i-1))} disabled={index===0} className="rounded-lg border border-white/20 px-4 py-2 text-sm disabled:opacity-40">Previous Question</button><button type="button" onClick={()=>{if(!readOnly&&question&&!question.is_objective&&question.answer_id&&(question.awarded_marks===null||question.awarded_marks===undefined)){setError("Save the marks for this question before proceeding to the next question.");return;}setError("");setIndex(i=>Math.min(data.questions.length-1,i+1));}} disabled={index>=data.questions.length-1} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold disabled:opacity-40">Next Question</button></div>
   </section>
   {!readOnly&&<section className="mt-5 rounded-2xl border border-white/10 bg-slate-900 p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div className="min-w-0 flex-1"><h2 className="font-semibold">Publish Student Result</h2><p className="mt-1 text-sm text-slate-400">The student sees the latest saved marks after publication. Grade is optional; if left blank, the standard grade is calculated from the percentage.</p>{!data.result_published&&<label className="mt-3 block max-w-xs text-sm text-slate-300">Optional grade<input value={grade} onChange={e=>setGrade(e.target.value)} maxLength={20} placeholder="e.g. A, Distinction, Pass" className="mt-1 block w-full rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-white"/></label>}</div><button type="button" onClick={publishResult} disabled={working||data.result_published||!canPublish||!allSubjectiveComplete} className="rounded-lg bg-green-600 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">{data.result_published?"Result Published":working?"Publishing...":"Publish Result"}</button></div>{!allSubjectiveComplete&&<p className="mt-3 text-xs text-amber-300">Complete evaluation of all submitted subjective answers before publishing.</p>}{data.result_published&&<p className="mt-3 text-sm text-green-300">Published result: {data.result_obtained_marks} / {data.result_total_marks} · Grade {data.result_grade||"—"}</p>}</section>}
  </div>
 </main>;
}

export default function SessionEvaluationPage() {
 return (
  <Suspense fallback={<main className="min-h-screen bg-slate-950 p-8 text-center text-slate-400">Loading student evaluation...</main>}>
   <SessionEvaluationPageContent />
  </Suspense>
 );
}
