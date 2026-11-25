"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Student {
  id: number;
  full_name: string;
  email: string;
  department?: string | null;
  is_active: boolean;
}

export default function StudentManagementPage() {
  const router = useRouter();
  const [students, setStudents] = useState<Student[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("name-asc");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return null;
    }
    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, [router]);

  const loadStudents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(`${API_URL}/admin/students`, {
        headers,
        cache: "no-store",
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) throw new Error(data.detail || "Unable to load students.");
      setStudents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load students.");
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    void loadStudents();
  }, [loadStudents]);

  async function updateStudentStatus(student: Student) {
    const nextStatus = !student.is_active;
    if (!window.confirm(`Are you sure you want to ${nextStatus ? "activate" : "deactivate"} ${student.full_name}'s account?`)) return;
    setActionId(student.id);
    setError("");
    setMessage("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(`${API_URL}/admin/users/${student.id}/status`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ is_active: nextStatus }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to update student status.");
      setMessage(`${student.full_name}'s account has been ${nextStatus ? "activated" : "deactivated"}.`);
      await loadStudents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update student status.");
    } finally {
      setActionId(null);
    }
  }

  async function deleteStudent(student: Student) {
    const confirmed = window.confirm(
      `Delete student ${student.full_name} (${student.email})? The account will be anonymized and cannot log in. Unfinished attempts and assignments will be removed. Completed examination attempts, answers, marks, results, and grading history will be retained for Admin review and can be deleted later from Retained Data.`
    );
    if (!confirmed) return;
    setActionId(student.id);
    setError("");
    setMessage("");
    try {
      const headers = getHeaders();
      if (!headers) return;
      const response = await fetch(`${API_URL}/admin/users/${student.id}/with-records`, {
        method: "DELETE",
        headers,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to delete student.");
      setMessage(data.message || `${student.full_name}'s account was deleted.`);
      await loadStudents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete student.");
    } finally {
      setActionId(null);
    }
  }

  const visibleStudents = [...students]
    .filter((student) => !searchTerm.trim() || [student.full_name, student.email, student.department].some((value) => String(value || "").toLowerCase().includes(searchTerm.trim().toLowerCase())))
    .sort((a, b) => {
      if (sortBy === "name-desc") return b.full_name.localeCompare(a.full_name);
      if (sortBy === "department") return String(a.department || "").localeCompare(String(b.department || ""));
      if (sortBy === "status") return Number(Boolean(b.is_active)) - Number(Boolean(a.is_active));
      return a.full_name.localeCompare(b.full_name);
    });

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student Management</p></div>
          <AdminSectionNavigation previousHref="/admin/sections/students" previousLabel="Students" />
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h1 className="text-3xl font-bold">Student Management</h1><p className="mt-2 text-sm text-slate-400">Activate, deactivate, or delete student accounts while preserving completed examination records.</p></div>
          <button type="button" onClick={loadStudents} disabled={loading} className="rounded-lg border border-white/20 px-4 py-2.5 text-sm disabled:opacity-50">{loading ? "Refreshing..." : "Refresh Students"}</button>
        </div>
        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        {message && <div role="status" className="mt-5 rounded-lg border border-green-500/30 bg-green-500/10 p-4 text-green-300">{message}</div>}
        <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{visibleStudents.length} student account(s)</p>
            <div className="flex flex-wrap gap-3">
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search student name, email, department" aria-label="Search students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white" />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort students" className="rounded-lg border border-white/15 bg-slate-800 px-3 py-2 text-sm text-white"><option value="name-asc">Name A to Z</option><option value="name-desc">Name Z to A</option><option value="department">Department</option><option value="status">Status</option></select>
            </div>
          </div>
          {loading ? <p className="py-10 text-center text-slate-400">Loading students...</p> : visibleStudents.length === 0 ? <p className="py-10 text-center text-slate-400">No students registered yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[950px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Department</th><th className="p-3">Status</th><th className="p-3">Student ID</th><th className="p-3">Actions</th></tr></thead>
                <tbody>{visibleStudents.map((student) => <tr key={student.id} className="border-b border-white/5">
                  <td className="p-3 font-medium">{student.full_name}</td>
                  <td className="p-3 text-slate-300">{student.email}</td>
                  <td className="p-3 text-slate-300">{student.department || "—"}</td>
                  <td className="p-3"><span className={student.is_active ? "text-emerald-300" : "text-amber-300"}>{student.is_active ? "Active" : "Deactivated"}</span></td>
                  <td className="p-3 text-slate-500">{student.id}</td>
                  <td className="p-3"><div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => updateStudentStatus(student)} disabled={actionId === student.id} className="rounded-lg border border-blue-400/40 px-3 py-2 text-xs font-semibold text-blue-300 disabled:opacity-50">{actionId === student.id ? "Working..." : student.is_active ? "Deactivate" : "Activate"}</button>
                    <button type="button" onClick={() => deleteStudent(student)} disabled={actionId === student.id} className="rounded-lg border border-red-400/40 px-3 py-2 text-xs font-semibold text-red-300 disabled:opacity-50">Delete</button>
                  </div></td>
                </tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
        <p className="mt-4 text-xs text-slate-500">Deleting a student anonymizes the account. Completed examination history is retained; unfinished attempts and future assignments are removed according to the existing retention rules.</p>
      </div>
    </main>
  );
}
