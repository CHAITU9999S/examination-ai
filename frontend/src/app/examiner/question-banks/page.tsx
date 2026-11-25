"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AdminSectionNavigation from "../../admin/components/AdminSectionNavigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Bank = {
  id: number; name: string; description?: string | null; subject?: string | null;
  question_count: number; question_types?: Record<string, number>;
  difficulty_counts?: Record<string, number>; maximum_marks?: number;
  created_at?: string | null;
  created_by_name?: string;
  created_by_role?: string;
};

const typeLabels: Record<string, string> = {
  MCQ: "MCQ", multi_select: "Multi-select", short_answer: "Short answer",
  long_answer: "Long answer", image_upload: "Image upload",
};
function formatDate(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString();
}

export default function QuestionBanksPage() {
  const router = useRouter();
  const [banks, setBanks] = useState<Bank[]>([]);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [dashboardHref, setDashboardHref] = useState("/examiner/dashboard");

  const headers = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return null; }
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  }, [router]);

  const loadBanks = useCallback(async () => {
    const auth = headers();
    if (!auth) return;
    const [profileResponse, response] = await Promise.all([
      fetch(`${API_URL}/users/me`, { headers: auth, cache: "no-store" }),
      fetch(`${API_URL}/question-banks`, { headers: auth, cache: "no-store" }),
    ]);
    const profile = await profileResponse.json().catch(() => ({}));
    const data = await response.json().catch(() => ({}));
    if (profileResponse.status === 401 || response.status === 401) { router.replace("/login"); return; }
    if (!profileResponse.ok || !response.ok) throw new Error(data.detail || "Unable to load your question banks.");
    if (profile.role !== "admin" && profile.role !== "examiner") { router.replace("/login"); return; }
    setDashboardHref(profile.role === "admin" ? "/admin/dashboard" : "/examiner/dashboard");
    setBanks(Array.isArray(data) ? data : []);
  }, [headers, router]);

  useEffect(() => { loadBanks().catch((e) => setError(e.message)); }, [loadBanks]);

  const visibleBanks = useMemo(() => [...banks]
    .filter((bank) => [bank.name, bank.subject, bank.description]
      .some((value) => String(value || "").toLowerCase().includes(search.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "questions-low") return a.question_count - b.question_count;
      if (sortBy === "questions-high") return b.question_count - a.question_count;
      if (sortBy === "marks-high") return (b.maximum_marks || 0) - (a.maximum_marks || 0);
      if (sortBy === "oldest") return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime() || b.id - a.id;
    }), [banks, search, sortBy]);

  async function editBank(bank: Bank) {
    const nextName = window.prompt("Question bank name", bank.name);
    if (nextName === null) return;
    const nextSubject = window.prompt("Subject (leave empty for none)", bank.subject || "");
    if (nextSubject === null) return;
    const nextDescription = window.prompt("Description (leave empty for none)", bank.description || "");
    if (nextDescription === null) return;
    const auth = headers(); if (!auth) return;
    const response = await fetch(`${API_URL}/question-banks/${bank.id}`, {
      method: "PATCH", headers: auth,
      body: JSON.stringify({ name: nextName.trim(), subject: nextSubject.trim() || null, description: nextDescription.trim() || null }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { setError(data.detail || "Unable to update question bank."); return; }
    await loadBanks();
  }

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
    if (!window.confirm("Delete this question bank? Unused questions may also be deleted. Questions used in other banks, examinations, or student records will be kept.")) return;
    const auth = headers(); if (!auth) return;
    const response = await fetch(`${API_URL}/question-banks/${id}`, { method: "DELETE", headers: auth });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { setError(data.detail || "Unable to delete question bank."); return; }
    await loadBanks();
  }

  return <main className="min-h-screen bg-slate-950 text-white">
    <header className="border-b border-white/10 bg-slate-900 px-6 py-5">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <div><Link href={dashboardHref} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="text-sm text-slate-400">Manage Question Banks</p></div>
        <AdminSectionNavigation previousHref="/admin/sections/question-banks" previousLabel="Question Bank" dashboardHref={dashboardHref} />
      </div>
    </header>
    <div className="mx-auto max-w-7xl space-y-8 px-6 py-10">
      <div><h1 className="text-3xl font-bold">Manage Question Banks</h1><p className="mt-2 text-slate-400">Only question banks created by your signed-in account appear here. You can view, edit, and manage your own banks.</p></div>
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
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">My Question Banks ({visibleBanks.length})</h2>
          <div className="flex flex-wrap gap-2">
            <input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search my banks" aria-label="Search my question banks" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm"/>
            <select value={sortBy} onChange={e=>setSortBy(e.target.value)} aria-label="Sort my question banks" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm">
              <option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name">Name A to Z</option><option value="questions-low">Fewest questions</option><option value="questions-high">Most questions</option><option value="marks-high">Maximum marks: high to low</option>
            </select>
          </div>
        </div>
        {visibleBanks.length === 0 ? <p className="rounded-xl border border-white/10 p-6 text-slate-400">{banks.length === 0 ? "You have not created any question banks yet." : "No question banks match your search."}</p> : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleBanks.map(bank=><article key={bank.id} className="flex h-full flex-col rounded-xl border border-white/10 bg-slate-900 p-5">
              <div className="flex-1">
                <h3 className="text-lg font-semibold">{bank.name}</h3>
                <p className="mt-1 text-sm text-cyan-300">{bank.subject || "Subject not specified"}</p>
                {bank.description && <p className="mt-2 text-sm text-slate-400">{bank.description}</p>}
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">Questions</p><p className="mt-1 font-semibold">{bank.question_count}</p></div>
                  <div className="rounded-lg bg-slate-800 p-3"><p className="text-xs text-slate-400">Maximum marks</p><p className="mt-1 font-semibold">{Number(bank.maximum_marks || 0).toLocaleString()}</p></div>
                </div>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">Difficulty levels</p>
                <div className="mt-2 flex flex-wrap gap-2">{["easy","medium","hard"].map(level=><span key={level} className="rounded-md bg-slate-800 px-2.5 py-1.5 text-xs capitalize text-slate-300">{level}: {bank.difficulty_counts?.[level] || 0}</span>)}</div>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">Question types</p>
                <div className="mt-2 flex flex-wrap gap-2">{Object.entries(typeLabels).map(([type,label])=><span key={type} className="rounded-md bg-slate-800 px-2.5 py-1.5 text-xs text-slate-300">{label}: {bank.question_types?.[type] || 0}</span>)}</div>
                <div className="mt-4 border-t border-white/10 pt-3 text-xs text-slate-400"><p>Created by: <span className="font-medium text-slate-200">{bank.created_by_name || "You"}</span> <span className="capitalize">({bank.created_by_role || "current user"})</span></p><p className="mt-1">Created: {formatDate(bank.created_at)}</p></div>
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <Link href={`/examiner/question-banks/${bank.id}`} className="rounded-lg bg-cyan-600 px-3 py-2 text-sm font-semibold">View / Manage Questions</Link>
                <button type="button" onClick={()=>editBank(bank)} className="rounded-lg border border-white/20 px-3 py-2 text-sm">Edit Bank</button>
                <button type="button" onClick={()=>deleteBank(bank.id)} className="rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-300">Delete Bank</button>
              </div>
            </article>)}
          </div>
        )}
      </section>
    </div>
  </main>;
}
