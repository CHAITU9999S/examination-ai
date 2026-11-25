"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type RetainedItem = {
  kind: string;
  id: number;
  title: string;
  owner_id: number;
  owner_name: string;
  owner_role: string;
  description: string;
};

const KIND_LABELS: Record<string, string> = {
  completed_exam: "Completed examination",
  completed_submission: "Completed student submission",
  exam_configuration_revision: "Examination configuration history",
  exam_question_marks_revision: "Question-paper marks history",
  answer_mark_revision: "Answer grading history",
};

export default function RetainedDataPage() {
  const router = useRouter();
  const [items, setItems] = useState<RetainedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState("");

  const loadItems = useCallback(async () => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    try {
      const response = await fetch(`${API_URL}/admin/retained-data`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) throw new Error("Unable to load retained records.");
      const data = await response.json();
      setItems(data.items || []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load retained records.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    async function verifyAndLoad() {
      const token = localStorage.getItem("examguard_access_token");
      if (!token) {
        router.replace("/login");
        return;
      }
      try {
        const response = await fetch(`${API_URL}/users/me`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });
        if (!response.ok) {
          router.replace("/login");
          return;
        }
        const user = await response.json();
        if (user.role !== "admin") {
          router.replace("/login");
          return;
        }
        await loadItems();
      } catch {
        router.replace("/login");
      }
    }
    verifyAndLoad();
  }, [loadItems, router]);

  async function deleteItem(item: RetainedItem) {
    const label = KIND_LABELS[item.kind] || "retained record";
    if (!window.confirm(`Delete this ${label.toLowerCase()} permanently? This cannot be undone.`)) return;
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    const key = `${item.kind}-${item.id}`;
    setDeleting(key);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        `${API_URL}/admin/retained-data/${encodeURIComponent(item.kind)}/${item.id}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to delete this retained record.");
      setMessage(data.message || "Retained record deleted.");
      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete this retained record.");
    } finally {
      setDeleting("");
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/admin/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Administrator / Retained Data</p>
          </div>
          <Link href="/admin/sections/user-management" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← User Management
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="text-3xl font-bold">Retained Data</h1>
        <p className="mt-2 max-w-3xl text-slate-400">
          Completed examinations, student submissions, and grading history are preserved when an account is deleted.
          Review these records here and permanently delete an individual record whenever it is no longer needed.
        </p>

        {error && <div role="alert" className="mt-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>}
        {message && <div role="status" className="mt-6 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">{message}</div>}

        {loading ? (
          <p className="mt-8 text-slate-400">Loading retained records...</p>
        ) : items.length === 0 ? (
          <div className="mt-8 rounded-xl border border-white/10 bg-slate-900 p-6 text-slate-300">
            No retained records are currently available.
          </div>
        ) : (
          <div className="mt-8 space-y-4">
            <p className="text-sm text-slate-400">{items.length} retained record(s)</p>
            {items.map((item) => {
              const key = `${item.kind}-${item.id}`;
              return (
                <article key={key} className="flex flex-col gap-4 rounded-xl border border-white/10 bg-slate-900 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-cyan-300">
                      {KIND_LABELS[item.kind] || item.kind.replaceAll("_", " ")}
                    </p>
                    <h2 className="mt-1 break-words font-semibold">{item.title}</h2>
                    <p className="mt-1 text-sm text-slate-400">{item.description}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      Original account: {item.owner_name} · {item.owner_role}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => deleteItem(item)}
                    disabled={deleting !== ""}
                    className="shrink-0 rounded-lg border border-red-400/40 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {deleting === key ? "Deleting..." : "Delete retained record"}
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
