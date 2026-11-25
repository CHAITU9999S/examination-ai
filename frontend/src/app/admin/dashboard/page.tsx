
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

interface NavigationItem {
  title: string;
  description: string;
  href: string;
  related?: NavigationItem[];
}

interface NavigationGroup {
  title: string;
  description: string;
  items: NavigationItem[];
}

const navigationGroups: NavigationGroup[] = [
  {
    title: "User Management",
    description: "Manage all platform accounts and review user-related activity.",
    items: [
      {
        title: "User Management",
        description: "View, activate, deactivate, and manage platform users.",
        href: "/admin/users",
      },
      {
        title: "Admin Management",
        description: "Manage administrator accounts.",
        href: "/admin/admins",
        related: [
          {
            title: "Admin Activity Logs",
            description: "Review administrator actions and account changes.",
            href: "/admin/activity-logs",
          },
        ],
      },
      {
        title: "Examiner Management",
        description: "Manage examiner accounts and access.",
        href: "/admin/examiners",
      },
      {
        title: "Student Management",
        description: "View registered students and their account status.",
        href: "/admin/students",
        related: [
          {
            title: "Student Schedules",
            description: "View active student assignments and examination opening and closing times.",
            href: "/admin/schedules",
          },
          {
            title: "Student Performance",
            description: "Review published results and long-term student performance.",
            href: "/admin/performance",
          },
        ],
      },
    ],
  },
  {
    title: "Question Banks",
    description: "Browse and manage question banks and the platform question library.",
    items: [
      {
        title: "Question Banks",
        description: "Browse question banks created by all Admins and Examiners.",
        href: "/staff/question-banks",
      },
      {
        title: "Manage Question Banks",
        description: "Create and manage your own question banks and questions.",
        href: "/examiner/question-banks",
      },
      {
        title: "All Questions",
        description: "View every existing question across the platform and safely delete individual questions.",
        href: "/admin/questions",
      },
      {
        title: "Question Library",
        description: "Create and manage standalone questions for examination preparation.",
        href: "/examiner/questions",
      },
    ],
  },
  {
    title: "Examinations",
    description: "Create, manage, grade, publish, and review examinations.",
    items: [
      {
        title: "Examinations",
        description: "View all examinations created by Admins and Examiners, with Admin deletion controls.",
        href: "/admin/exams",
      },
      {
        title: "Manage Examinations",
        description: "View and manage examinations you created.",
        href: "/staff/manage-exams",
        related: [
          {
            title: "Proctoring Review",
            description: "Review flagged sessions and recorded proctoring events.",
            href: "/staff/proctoring",
          },
        ],
      },
      {
        title: "Create Examination",
        description: "Create a new examination.",
        href: "/examiner/exams",
      },
      {
        title: "Answer Grading",
        description: "Review answers and approve or change marks only for examinations you created.",
        href: "/examiner/grading",
      },
      {
        title: "Result Publication",
        description: "Review and publish results only for examinations you created.",
        href: "/examiner/results",
      },
    ],
  },
  {
    title: "Account Security",
    description: "Change your account password and maintain account security.",
    items: [
      {
        title: "Account Security",
        description: "Change your account password.",
        href: "/account/security",
      },
    ],
  },
];

export default function AdminDashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [questionResetAvailable, setQuestionResetAvailable] = useState<boolean | null>(null);
  const [questionResetBusy, setQuestionResetBusy] = useState(false);
  const [questionResetMessage, setQuestionResetMessage] = useState("");

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

        const resetStatusResponse = await fetch(
          `${API_URL}/admin/questions/reset-status`,
          { headers, cache: "no-store" }
        );
        if (resetStatusResponse.ok) {
          const resetStatus = await resetStatusResponse.json();
          setQuestionResetAvailable(Boolean(resetStatus.available));
          if (!resetStatus.available) setQuestionResetMessage(resetStatus.message || "The one-time question deletion is unavailable.");
        } else {
          setQuestionResetAvailable(false);
        }

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


  async function deleteAllQuestionsOnce() {
    if (questionResetBusy || !questionResetAvailable) return;
    const confirmed = window.confirm(
      "DANGER: This permanently deletes every question, its options, exam-paper links, and dependent student answer records. Existing examinations may become unusable. Examination sessions and existing result snapshots will be retained. This action can be used only once. Continue?"
    );
    if (!confirmed) return;
    const finalConfirmation = window.confirm(
      "Final confirmation: permanently delete ALL questions from ExamGuard AI now?"
    );
    if (!finalConfirmation) return;

    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    setQuestionResetBusy(true);
    setQuestionResetMessage("");
    try {
      const response = await fetch(`${API_URL}/admin/questions/all`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to delete all questions.");
      setQuestionResetAvailable(false);
      setQuestionResetMessage(data.message || "All questions were deleted. This action is now disabled.");
      setStatistics((current) => current ? { ...current, total_questions: 0 } : current);
    } catch (resetError) {
      setQuestionResetMessage(
        resetError instanceof Error ? resetError.message : "Unable to delete all questions."
      );
    } finally {
      setQuestionResetBusy(false);
    }
  }

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


        {questionResetAvailable && (
          <section className="mb-10 rounded-xl border border-red-500/40 bg-red-950/30 p-6">
            <h2 className="text-lg font-bold text-red-300">One-time question reset</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
              Permanently delete all questions and dependent answer records from the database. Existing examinations may become unusable. Examination sessions and saved result snapshots are retained where possible. This option disappears permanently after successful use.
            </p>
            <button
              type="button"
              onClick={deleteAllQuestionsOnce}
              disabled={questionResetBusy}
              className="mt-4 rounded-lg bg-red-700 px-5 py-3 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
            >
              {questionResetBusy ? "Deleting questions..." : "Delete all questions (one time only)"}
            </button>
            {questionResetMessage && (
              <p role="status" className="mt-3 text-sm text-red-200">{questionResetMessage}</p>
            )}
          </section>
        )}
        {!questionResetAvailable && questionResetMessage && (
          <p role="status" className="mb-8 text-sm text-slate-300">{questionResetMessage}</p>
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

          <div className="space-y-6">
            {navigationGroups.map((group) => (
              <section
                key={group.title}
                className="rounded-2xl border border-white/10 bg-slate-900 p-6"
              >
                <div className="mb-5">
                  <h3 className="text-xl font-bold">{group.title}</h3>
                  <p className="mt-1 text-sm text-slate-400">{group.description}</p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  {group.items.map((item) => (
                    <article
                      key={item.href}
                      className="rounded-xl border border-white/10 bg-slate-800/70 p-4"
                    >
                      <Link
                        href={item.href}
                        className="group inline-flex font-semibold text-white transition hover:text-blue-400"
                      >
                        {item.title} <span className="ml-2 text-blue-400">→</span>
                      </Link>
                      <p className="mt-2 text-sm leading-6 text-slate-400">
                        {item.description}
                      </p>

                      {item.related && item.related.length > 0 && (
                        <div className="mt-4 border-t border-white/10 pt-3">
                          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Related sections
                          </p>
                          <div className="space-y-3">
                            {item.related.map((relatedItem) => (
                              <div key={relatedItem.href}>
                                <Link
                                  href={relatedItem.href}
                                  className="text-sm font-semibold text-cyan-300 hover:text-cyan-200"
                                >
                                  {relatedItem.title} →
                                </Link>
                                <p className="mt-1 text-xs leading-5 text-slate-500">
                                  {relatedItem.description}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
