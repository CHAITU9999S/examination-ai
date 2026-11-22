"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Question = { id:number; question_text:string; question_type:string; difficulty:string; subject:string; marks:number; negative_marks?:number; expected_answer?:string|null; model_answer_text?:string|null; tags?:string[]; options:{id:number;option_text:string;is_correct:boolean}[] };

export default function QuestionBankDetailPage() {
  const params = useParams<{bankId:string}>();
  const bankId = params.bankId;
  const router = useRouter();
  const [questions,setQuestions] = useState<Question[]>([]);
  const [bankName,setBankName] = useState("Question Bank");
  const [text,setText] = useState("");
  const [type,setType] = useState("MCQ");
  const [difficulty,setDifficulty] = useState("easy");
  const [subject,setSubject] = useState("");
  const [marks,setMarks] = useState("1");
  const [expected,setExpected] = useState("");
  const [optionTexts,setOptionTexts] = useState(["",""]);
  const [correct,setCorrect] = useState<string[]>(["0"]);
  const [error,setError] = useState("");
  const [working,setWorking] = useState(false);
  const headers = useCallback(()=>{const token=localStorage.getItem("examguard_access_token");if(!token){router.replace("/login");return null;}return {Authorization:`Bearer ${token}`,"Content-Type":"application/json"};},[router]);
  const load = useCallback(async()=>{const auth=headers();if(!auth)return;const [banksRes,questionsRes]=await Promise.all([fetch(`${API_URL}/question-banks`,{headers:auth}),fetch(`${API_URL}/question-banks/${bankId}/questions`,{headers:auth})]);if(!banksRes.ok||!questionsRes.ok)throw new Error("Unable to load this question bank.");const banks=await banksRes.json();const bank=banks.find((item:{id:number;name:string})=>item.id===Number(bankId));if(bank)setBankName(bank.name);setQuestions(await questionsRes.json());},[bankId,headers]);
  useEffect(()=>{load().catch(e=>setError(e.message));},[load]);
  async function addQuestion(event:FormEvent){event.preventDefault();setError("");setWorking(true);try{const auth=headers();if(!auth)return;const isChoice=type==="MCQ"||type==="multi_select";const payload={question_text:text,question_type:type,subject:subject.trim(),difficulty,options:isChoice?optionTexts:[],expected_answer:expected||null,marks:Number(marks),negative_marks:0,correct_option_index:type==="MCQ"?Number(correct[0]??0):null,correct_option_indices:type==="multi_select"?correct.map(Number):[]};const response=await fetch(`${API_URL}/question-banks/${bankId}/questions`,{method:"POST",headers:auth,body:JSON.stringify(payload)});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||"Unable to add question.");setText("");setExpected("");setOptionTexts(["",""]);setCorrect(["0"]);await load();}catch(e){setError(e instanceof Error?e.message:"Unable to add question.");}finally{setWorking(false);}}
  async function editQuestion(question: Question) {
    const questionText = window.prompt("Question text", question.question_text);
    if (questionText === null) return;
    const questionType = window.prompt("Type: MCQ, multi_select, short_answer, long_answer, image_upload", question.question_type);
    if (questionType === null) return;
    const difficultyValue = window.prompt("Difficulty: easy, medium, hard", question.difficulty);
    if (difficultyValue === null) return;
    const subjectValue = window.prompt("Subject", question.subject || "");
    if (subjectValue === null) return;
    const marksValue = window.prompt("Maximum marks", String(question.marks));
    if (marksValue === null) return;
    const expectedValue = window.prompt("Expected answer (optional)", question.expected_answer || "");
    if (expectedValue === null) return;
    const isChoice = questionType === "MCQ" || questionType === "multi_select";
    let optionValues = question.options.map((option) => option.option_text);
    let correctIndexes = question.options.map((option, index) => option.is_correct ? index : -1).filter((index) => index >= 0);
    if (isChoice) {
      const changedOptions = [];
      for (let index = 0; index < Math.max(optionValues.length, 2); index += 1) {
        const value = window.prompt("Option " + (index + 1), optionValues[index] || "");
        if (value === null) return;
        changedOptions.push(value);
      }
      optionValues = changedOptions;
      const correctValue = window.prompt("Correct option number(s), starting from 1. For multiple select, separate numbers with commas.", correctIndexes.map((index) => index + 1).join(",") || "1");
      if (correctValue === null) return;
      correctIndexes = correctValue.split(",").map((value) => Number(value.trim()) - 1).filter((value) => Number.isInteger(value) && value >= 0 && value < optionValues.length);
    }
    const auth = headers(); if (!auth) return;
    const payload = {
      question_text: questionText.trim(), question_type: questionType,
      subject: subjectValue.trim(), difficulty: difficultyValue,
      marks: Number(marksValue), negative_marks: Number(question.negative_marks || 0),
      expected_answer: expectedValue.trim() || null,
      model_answer_text: question.model_answer_text || null,
      options: isChoice ? optionValues : [],
      correct_option_index: questionType === "MCQ" ? correctIndexes[0] ?? null : null,
      correct_option_indices: questionType === "multi_select" ? correctIndexes : [],
      tags: question.tags || [],
    };
    const response = await fetch(`${API_URL}/question-banks/${bankId}/questions/${question.id}`, { method: "PATCH", headers: auth, body: JSON.stringify(payload) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { setError(data.detail || "Unable to update question."); return; }
    await load();
  }
  async function removeQuestion(id:number){
    if (!window.confirm("Delete this question from your question banks? Any existing examination copy will stay unchanged.")) return;
    const auth=headers();if(!auth)return;
    const response=await fetch(`${API_URL}/question-banks/${bankId}/questions/${id}/delete`,{method:"DELETE",headers:auth});
    const data=await response.json().catch(()=>({}));
    if(!response.ok){setError(data.detail||"Unable to delete question.");return;}
    await load();
  }
  const choice=type==="MCQ"||type==="multi_select";
  return <main className="min-h-screen bg-slate-950 text-white"><header className="border-b border-white/10 bg-slate-900 px-6 py-5"><div className="mx-auto flex max-w-6xl justify-between"><div><Link href="/examiner/question-banks" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="text-sm text-slate-400">Manage Questions</p></div><Link href="/examiner/question-banks" className="rounded-lg border border-white/20 px-4 py-2 text-sm">All Banks</Link></div></header>
  <div className="mx-auto max-w-6xl space-y-8 px-6 py-10"><div><h1 className="text-3xl font-bold">{bankName}</h1><p className="mt-2 text-slate-400">Add questions now and use them in examinations later.</p></div>{error&&<p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}
  <form onSubmit={addQuestion} className="space-y-4 rounded-2xl border border-white/10 bg-slate-900 p-6"><h2 className="text-xl font-semibold">Add a Question</h2><textarea required value={text} onChange={e=>setText(e.target.value)} rows={3} placeholder="Write your question" className="w-full rounded-lg border border-slate-700 bg-slate-800 p-3"/>
  <div className="grid gap-4 sm:grid-cols-3"><label className="text-sm">Question type<select value={type} onChange={e=>setType(e.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3"><option value="MCQ">MCQ</option><option value="multi_select">Multiple select</option><option value="short_answer">Short answer</option><option value="long_answer">Long answer</option><option value="image_upload">Image upload</option></select></label><label className="text-sm">Difficulty<select value={difficulty} onChange={e=>setDifficulty(e.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3"><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label><label className="text-sm">Subject<input required value={subject} onChange={e=>setSubject(e.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3"/></label></div>
  <label className="block text-sm">Maximum marks<input required type="number" min="0.01" step="0.01" value={marks} onChange={e=>setMarks(e.target.value)} className="mt-2 w-full rounded-lg bg-slate-800 p-3"/></label>
  {choice&&<div className="grid gap-3 sm:grid-cols-2">{optionTexts.map((value,index)=><label key={index} className="text-sm">Option {index+1}<input required value={value} onChange={e=>setOptionTexts(old=>old.map((v,i)=>i===index?e.target.value:v))} className="mt-2 w-full rounded-lg bg-slate-800 p-3"/><span className="mt-2 flex items-center gap-2 text-xs"><input type={type==="MCQ"?"radio":"checkbox"} name="correct" checked={correct.includes(String(index))} onChange={()=>setCorrect(old=>type==="MCQ"?[String(index)]:old.includes(String(index))?old.filter(v=>v!==String(index)):[...old,String(index)])}/> Correct answer</span></label>)}</div>}
  <label className="block text-sm">Expected answer (optional)<textarea value={expected} onChange={e=>setExpected(e.target.value)} rows={2} className="mt-2 w-full rounded-lg bg-slate-800 p-3"/></label>
  <button disabled={working} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold disabled:opacity-50">{working?"Saving...":"Add Question"}</button></form>
  <section className="space-y-3"><h2 className="text-xl font-semibold">Questions in this bank ({questions.length})</h2>{questions.length===0?<p className="rounded-xl border border-white/10 p-6 text-slate-400">No questions have been added yet.</p>:questions.map(q=><article key={q.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-white/10 bg-slate-900 p-5"><div><p className="text-xs text-cyan-300">{q.question_type} · {q.difficulty} · {q.marks} marks</p><p className="mt-2 whitespace-pre-wrap">{q.question_text}</p>{q.options?.map(o=><p key={o.id} className="mt-1 text-sm text-slate-400">{o.option_text}{o.is_correct?" (Correct)":""}</p>)}</div><div className="flex gap-2"><button onClick={()=>editQuestion(q)} className="rounded-lg border border-white/20 px-3 py-2 text-sm">Edit</button><button onClick={()=>removeQuestion(q.id)} className="rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-300">Delete</button></div></article>)}</section></div></main>;
}
