
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
}

interface NavigationItem {
  title: string;
  description: string;
  href: string;
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
    title: "Users",
    description: "Manage Admins, Examiners, Students, and all user accounts.",
    slug: "users",
    items: [
      { title: "Admins", description: "Manage administrator accounts and activity.", href: "/admin/sections/admins" },
      { title: "Examiners", description: "Manage Examiner accounts and activity.", href: "/admin/sections/examiners" },
      { title: "Students", description: "Manage student accounts, schedules, and performance.", href: "/admin/sections/students" },
      { title: "User Management", description: "View and manage all platform accounts.", href: "/admin/users" },
    ],
  },
  {
    title: "Question Bank",
    description: "Browse question banks and manage the question banks you own.",
    slug: "question-banks",
    items: [
      { title: "All Question Banks", description: "Browse question banks created across the platform.", href: "/staff/question-banks" },
      { title: "Manage Question Banks", description: "Create and manage question banks that you own.", href: "/examiner/question-banks" },
    ],
  },
  {
    title: "Examinations",
    description: "View and manage examinations, grade answers, publish results, and review proctoring.",
    slug: "examinations",
    items: [
      { title: "Create Examination", description: "Create a new examination and configure its question paper.", href: "/examiner/exams" },
      { title: "Manage Examinations", description: "Manage examinations created by the logged-in account.", href: "/staff/manage-exams" },
      { title: "Examinations", description: "View all examinations created by Admins and Examiners.", href: "/admin/exams" },
      { title: "Student Tracking", description: "View students and examinations assigned by your account.", href: "/admin/performance?from=examinations" },
    ],
  },
  {
    title: "Results",
    description: "Review submitted answers, evaluate examinations, and publish results for examinations you created.",
    slug: "results",
    href: "/examiner/results",
    items: [],
  },
  {
    title: "Account Management",
    description: "Manage your personal details, password, and recent login history.",
    slug: "account-management",
    href: "/account/management",
    items: [],
  },
];

export default function AdminDashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [questionBankCount, setQuestionBankCount] = useState<number | null>(null);
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
          { headers, cache: "no-store" }
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

        const banksResponse = await fetch(`${API_URL}/question-banks/browse`, { headers, cache: "no-store" });
        if (banksResponse.ok) {
          const banksData = await banksResponse.json();
          setQuestionBankCount(Array.isArray(banksData) ? banksData.length : 0);
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
    { label: "Total Users", value: statistics?.total_users },
    { label: "Students", value: statistics?.total_students },
    { label: "Examiners", value: statistics?.total_examiners },
    { label: "Administrators", value: statistics?.total_admins },
    { label: "Active Users", value: statistics?.active_users },
    { label: "Inactive Users", value: statistics?.inactive_users },
    { label: "Examinations", value: statistics?.total_exams },
    { label: "Question Banks", value: questionBankCount ?? undefined },
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
          <p className="text-sm font-medium text-blue-400">ADMINISTRATION</p>
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
          <h2 className="mb-5 text-xl font-bold">Platform Overview</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {statisticCards.map((card) => (
              <article
                key={card.label}
                className="rounded-xl border border-white/10 bg-slate-900 p-6"
              >
                <p className="text-sm text-slate-400">{card.label}</p>
                <p className="mt-3 text-3xl font-bold">
                  {card.value === undefined ? "—" : card.value.toLocaleString()}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-5 text-xl font-bold">Management</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {navigationGroups.map((group) => (
              <article
                key={group.slug}
                className="group flex min-h-52 flex-col rounded-xl border border-white/10 bg-slate-900 p-6 transition hover:border-blue-400/50 hover:bg-slate-800"
              >
                <h3 className="text-xl font-bold transition group-hover:text-blue-400">{group.title}</h3>
                <p className="mt-2 flex-1 text-sm leading-6 text-slate-400">{group.description}</p>
                <Link
                  href={group.href || `/admin/sections/${group.slug}`}
                  className="mt-5 inline-flex min-h-12 w-fit items-center justify-center gap-2 rounded-lg bg-cyan-600 px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:ring-offset-2 focus:ring-offset-slate-900"
                >
                  View <span aria-hidden="true">→</span>
                </Link>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
