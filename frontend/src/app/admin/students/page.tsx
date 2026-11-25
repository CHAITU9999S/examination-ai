"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Student {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
}

export default function StudentManagementPage() {
  const router = useRouter();
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    fetch(`${API_URL}/admin/students`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 || response.status === 403) { router.replace("/login"); return; }
      if (!response.ok) throw new Error(data.detail || "Unable to load student accounts.");
      setStudents(Array.isArray(data) ? data : []);
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load students."))
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5">
          <div><Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link><p className="mt-1 text-sm text-slate-400">Administrator / Student Management</p></div>
          <AdminSectionNavigation previousHref="/admin/sections/students" previousLabel="Students" />
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-5 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h1 className="text-3xl font-bold">Student Accounts</h1><p className="mt-2 text-sm text-slate-400">All registered Student accounts, including deactivated accounts.</p></div>
          <Link href="/admin/users" className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold hover:bg-blue-500">Manage Account Status</Link>
        </div>
        {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</div>}
        <section className="mt-7 rounded-2xl border border-white/10 bg-slate-900 p-5">
          <p className="mb-4 text-sm text-slate-400">{students.length} student account(s)</p>
          {loading ? <p className="py-10 text-center text-slate-400">Loading students...</p> : students.length === 0 ? <p className="py-10 text-center text-slate-400">No students registered yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Status</th><th className="p-3">Student ID</th></tr></thead>
                <tbody>{students.map((student) => <tr key={student.id} className="border-b border-white/5"><td className="p-3 font-medium">{student.full_name}</td><td className="p-3 text-slate-300">{student.email}</td><td className="p-3"><span className={student.is_active ? "text-emerald-300" : "text-amber-300"}>{student.is_active ? "Active" : "Deactivated"}</span></td><td className="p-3 text-slate-500">{student.id}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
