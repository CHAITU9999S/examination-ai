"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Bank = { id: number; name: string; description?: string | null; subject?: string | null; question_count: number };

export default function QuestionBanksPage() {
  const router = useRouter();
  const [banks, setBanks] = useState<Bank[]>([]);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const headers = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return null; }
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  }, [router]);

  const loadBanks = useCallback(async () => {
    const auth = headers();
    if (!auth) return;
    const response = await fetch(`${API_URL}/question-banks`, { headers: auth, cache: "no-store" });
    if (!response.ok) throw new Error("Unable to load question banks.");
    setBanks(await response.json());
  }, [headers]);

  useEffect(() => { loadBanks().catch((e) => setError(e.message)); }, [loadBanks]);

  async function createBank(event: FormEvent) {
    event.preventDefault(); setError(""); setWorking(true);
    try {
      const auth = headers(); if (!auth) return;
      const response = await fetch(`${API_URL}/question-banks`, {
        method: "POST", headers: auth,
        body: JSON.stringify({ name: name.trim(), subject: subject.trim() || null, description: description.trim() || null }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to create question bank.");
      setName(""); setSubject(""); setDescription("");
      await loadBanks();
      router.push(`/examiner/question-banks/${data.bank_id}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to create question bank."); }
    finally { setWorking(false); }
  }

  async function deleteBank(id: number) {
    if (!window.confirm("Delete this question bank? Saved questions and examination records will be kept.")) return;
    const auth = headers(); if (!auth) return;
    const response = await fetch(`${API_URL}/question-banks/${id}`, { method: "DELETE", headers: auth });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { setError(data.detail || "Unable to delete question bank."); return; }
    await loadBanks();
  }

  return <main className="min-h-screen bg-slate-950 text-white">
    <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <div><Link href="/examiner/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="text-sm text-slate-400">My Question Banks</p></div>
        <Link href="/examiner/exams" className="rounded-lg border border-white/20 px-4 py-2 text-sm">Examinations</Link>
      </div>
    </header>
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <div><h1 className="text-3xl font-bold">My Question Banks</h1><p className="mt-2 text-slate-400">Create and manage question banks whenever you need. You can use their questions in your examinations.</p></div>
      {error && <p role="alert" className="rounded-lg bg-red-500/10 p-4 text-red-300">{error}</p>}
      <form onSubmit={createBank} className="space-y-4 rounded-2xl border border-white/10 bg-slate-900 p-6">
        <h2 className="text-xl font-semibold">Create a Question Bank</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm">Bank name<input required maxLength={150} value={name} onChange={e=>setName(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3" placeholder="Example: Mathematics" /></label>
          <label className="text-sm">Subject (optional)<input maxLength={100} value={subject} onChange={e=>setSubject(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3" /></label>
        </div>
        <label className="block text-sm">Description (optional)<textarea maxLength={500} value={description} onChange={e=>setDescription(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3" rows={2} /></label>
        <button disabled={working} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold disabled:opacity-50">{working ? "Creating..." : "Create Bank"}</button>
      </form>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Saved Question Banks ({banks.length})</h2>
        {banks.length === 0 ? <p className="rounded-xl border border-white/10 p-6 text-slate-400">You have not created a question bank yet.</p> : banks.map(bank=><article key={bank.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-900 p-5">
          <div><h3 className="font-semibold">{bank.name}</h3><p className="mt-1 text-sm text-slate-400">{bank.subject || "No subject"} · {bank.question_count} question(s)</p>{bank.description && <p className="mt-1 text-sm text-slate-500">{bank.description}</p>}</div>
          <div className="flex gap-2"><Link href={`/examiner/question-banks/${bank.id}`} className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold">Manage Questions</Link><button onClick={()=>deleteBank(bank.id)} className="rounded-lg border border-red-500/40 px-4 py-2 text-sm text-red-300">Delete</button></div>
        </article>)}
      </section>
    </div>
  </main>;
}
