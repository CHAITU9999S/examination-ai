"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type SectionItem = { title: string; description: string; href: string; related?: SectionItem[] };

const sections: Record<string, { title: string; description: string; items: SectionItem[] }> = {
  "user-management": {
    title: "User Management",
    description: "All account-management areas are grouped here.",
    items: [
      { title: "User Management", description: "View, activate, deactivate, and manage all platform accounts.", href: "/admin/users" },
      { title: "Admin Management", description: "Create and manage Admin accounts.", href: "/admin/admins", related: [
        { title: "Admin Activity Logs", description: "Review administrator actions and account changes.", href: "/admin/activity-logs" },
        { title: "Retained Data", description: "Review and delete completed examinations, submissions, and grading history retained after account deletion.", href: "/admin/retained-data" },
      ] },
      { title: "Examiner Management", description: "Create and manage Examiner accounts.", href: "/admin/examiners" },
      { title: "Student Management", description: "View and manage registered Student accounts.", href: "/admin/students", related: [
        { title: "Student Schedule", description: "View student assignments and examination schedules.", href: "/admin/schedules" },
        { title: "Student Performance", description: "Review student performance and published results.", href: "/admin/performance" },
      ] },
    ],
  },
  "question-banks": {
    title: "Question Banks",
    description: "Browse available banks or manage banks you own.",
    items: [
      { title: "Question Bank", description: "Browse question banks created across the platform.", href: "/staff/question-banks" },
      { title: "Manage Question Banks", description: "Create and manage your own question banks.", href: "/examiner/question-banks" },
    ],
  },
  examinations: {
    title: "Examinations",
    description: "All examination operations are grouped here.",
    items: [
      { title: "Examinations", description: "View examinations created by Admins and Examiners.", href: "/admin/exams" },
      { title: "Manage Examinations", description: "Manage examinations that you created.", href: "/staff/manage-exams", related: [
        ] },
      { title: "Answer Grading", description: "Review answers and manage marks for examinations you own.", href: "/examiner/grading" },
      { title: "Result Publication", description: "Approve and publish results for examinations you own.", href: "/examiner/results" },
      { title: "Proctoring Review", description: "Review flagged sessions and proctoring events.", href: "/staff/proctoring" },
    ],
  },
};

export default function AdminSectionPage() {
  const params = useParams<{ section: string }>();
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [loading, setLoading] = useState(true);
  const section = useMemo(() => sections[params.section], [params.section]);

  useEffect(() => {
    async function verifyAdmin() {
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
        setAuthorized(true);
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    }
    verifyAdmin();
  }, [router]);

  if (loading) {
    return <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">Loading section...</main>;
  }
  if (!authorized || !section) {
    return (
      <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
        <p>{section ? "Verifying administrator access..." : "Section not found."}</p>
        <Link href="/admin/dashboard" className="mt-4 inline-block text-blue-300">← Admin Dashboard</Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/admin/dashboard" className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Administrator / {section.title}</p>
          </div>
          <Link href="/admin/dashboard" className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Dashboard</Link>
        </div>
      </header>
      <div className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="text-3xl font-bold">{section.title}</h1>
        <p className="mt-2 text-slate-400">{section.description}</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {section.items.map((item) => (
            <article key={item.href} className="rounded-xl border border-white/10 bg-slate-900 p-5">
              <Link href={item.href} className="font-semibold hover:text-blue-300">
                {item.title} <span className="text-blue-300">→</span>
              </Link>
              <p className="mt-2 text-sm leading-6 text-slate-400">{item.description}</p>
              {item.related && item.related.length > 0 && (
                <div className="mt-4 space-y-3 border-t border-white/10 pt-3">
                  {item.related.map((related) => (
                    <div key={related.href}>
                      <Link href={related.href} className="text-sm font-semibold text-cyan-300 hover:text-cyan-200">
                        {related.title} →
                      </Link>
                      <p className="mt-1 text-xs leading-5 text-slate-500">{related.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
