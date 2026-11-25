
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface User {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

interface Statistics {
  total_users: number;
  total_students: number;
  total_examiners: number;
  total_admins: number;
  active_users: number;
  inactive_users: number;
  total_exams: number;
  total_questions: number;
  total_sessions: number;
}

interface NavigationGroup {
  title: string;
  description: string;
  slug: string;
  href?: string;
  items: NavigationItem[];
}

const navigationGroups: NavigationGroup[] = [
  {
    title: "User Management",
    description: "Manage users, administrators, examiners, students, schedules, performance, and administrator activity.",
    slug: "user-management",
    items: [
      { title: "User Management", description: "View and manage all platform accounts.", href: "/admin/users" },
      { title: "Admin Management", description: "Create and manage administrator accounts and review Admin Activity Logs.", href: "/admin/admins" },
      { title: "Examiner Management", description: "Create and manage examiner accounts.", href: "/admin/examiners" },
      { title: "Student Management", description: "Manage students, view Student Schedules, and review Student Performance.", href: "/admin/students" },
      { title: "Student Schedule", description: "View student examination assignments and schedules.", href: "/admin/schedules" },
      { title: "Student Performance", description: "Review student examination performance and published results.", href: "/admin/performance" },
      { title: "Admin Activity Logs", description: "Review administrator actions and account changes.", href: "/admin/activity-logs" },
    ],
  },
  {
    title: "Question Banks",
    description: "Browse existing question banks and manage your own question banks.",
    slug: "question-banks",
    items: [
      { title: "Question Bank", description: "Browse question banks created across the platform.", href: "/staff/question-banks" },
      { title: "Manage Question Banks", description: "Create and manage question banks that you own.", href: "/examiner/question-banks" },
    ],
  },
  {
    title: "Examinations",
    description: "View and manage examinations, grade answers, publish results, and review proctoring.",
    slug: "examinations",
    items: [
      { title: "Examinations", description: "View examinations created by Admins and Examiners.", href: "/admin/exams" },
      { title: "Manage Examinations", description: "Manage examinations that you created.", href: "/staff/manage-exams" },
      { title: "Answer Grading", description: "Review answers and manage marks for examinations you own.", href: "/examiner/grading" },
      { title: "Result Publication", description: "Approve and publish results for examinations you own.", href: "/examiner/results" },
      { title: "Proctoring Review", description: "Review flagged sessions and proctoring events.", href: "/staff/proctoring" },
    ],
  },
  {
    title: "Account Security",
    description: "Change your account password and maintain account security.",
    slug: "account-security",
    href: "/account/security",
    items: [],
  },
];

export default function AdminDashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      const token = localStorage.getItem("examguard_access_token");

      if (!token) {
        router.replace("/login");
        return;
      }

      try {
        const headers = {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        };

        const userResponse = await fetch(`${API_URL}/users/me`, {
          headers,
        });

        if (!userResponse.ok) {
          throw new Error("Unable to verify your account.");
        }

        const currentUser: User = await userResponse.json();

        if (currentUser.role !== "admin") {
          router.replace("/login");
          return;
        }

        setUser(currentUser);

        const statsResponse = await fetch(
          `${API_URL}/admin/dashboard`,
          { headers }
        );

        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setStatistics(statsData);
        } else if (statsResponse.status === 404) {
          setStatistics(null);
          setError(
            "Dashboard statistics endpoint is not available yet. You can still use the management pages."
          );
        } else {
          throw new Error("Unable to load dashboard statistics.");
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load the dashboard."
        );
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [router]);


  function handleLogout() {
    localStorage.removeItem("examguard_access_token");
    localStorage.removeItem("examguard_user");
    router.replace("/login");
  }

  const statisticCards = [
    {
      label: "Total Users",
      value: statistics?.total_users,
    },
    {
      label: "Students",
      value: statistics?.total_students,
    },
    {
      label: "Examiners",
      value: statistics?.total_examiners,
    },
    {
      label: "Administrators",
      value: statistics?.total_admins,
    },
    {
      label: "Active Users",
      value: statistics?.active_users,
    },
    {
      label: "Inactive Users",
      value: statistics?.inactive_users,
    },
    {
      label: "Examinations",
      value: statistics?.total_exams,
    },
    {
      label: "Questions",
      value: statistics?.total_questions,
    },
    {
      label: "Exam Sessions",
      value: statistics?.total_sessions,
    },
  ];

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <p className="text-slate-300">Loading administrator dashboard...</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">
              Administrator Dashboard
            </p>
          </div>

          <button
            onClick={handleLogout}
            className="rounded-lg border border-red-400/30 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-500/10"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <section className="mb-10">
          <p className="text-sm font-medium text-blue-400">
            ADMINISTRATION
          </p>

          <h1 className="mt-2 text-3xl font-bold">
            Welcome, {user?.full_name || "Administrator"}
          </h1>

          <p className="mt-2 text-slate-400">
            Manage users, examinations, and platform access.
          </p>
        </section>

        {error && (
          <div
            role="alert"
            className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/10 px-5 py-4 text-sm text-amber-300"
          >
            {error}
          </div>
        )}


        <section className="mb-12">
          <h2 className="mb-5 text-xl font-bold">
            Platform Overview
          </h2>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {statisticCards.map((card) => (
              <article
                key={card.label}
                className="rounded-xl border border-white/10 bg-slate-900 p-6"
              >
                <p className="text-sm text-slate-400">
                  {card.label}
                </p>

                <p className="mt-3 text-3xl font-bold">
                  {card.value === undefined
                    ? "—"
                    : card.value.toLocaleString()}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-5 text-xl font-bold">
            Management
          </h2>

          <div className="grid gap-4 sm:grid-cols-2">
            {navigationGroups.map((group) => (
              <Link
                key={group.slug}
                href={group.href || `/admin/sections/${group.slug}`}
                className="rounded-2xl border border-white/10 bg-slate-900 p-6 transition hover:border-blue-400/50 hover:bg-slate-800"
              >
                <h3 className="text-xl font-bold">{group.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">{group.description}</p>
                {group.items.length > 0 && (
                  <p className="mt-4 text-xs font-semibold text-blue-300">
                    {group.items.length} sections inside <span aria-hidden="true">→</span>
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
