
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

interface StoredUser {
  id?: number;
  full_name?: string;
  email?: string;
  role?: "student" | "examiner" | "admin";
}

export default function Navbar() {
  const router = useRouter();
  const pathname = usePathname();

  const [user, setUser] = useState<StoredUser | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);

    const token = localStorage.getItem("examguard_access_token");
    const storedUser = localStorage.getItem("examguard_user");

    if (!token || !storedUser) {
      setUser(null);
      return;
    }

    try {
      const parsedUser = JSON.parse(storedUser) as StoredUser;
      setUser(parsedUser);
    } catch {
      setUser(null);
    }
  }, [pathname]);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function logout() {
    localStorage.removeItem("examguard_access_token");
    localStorage.removeItem("examguard_user");

    setUser(null);
    setMenuOpen(false);

    router.replace("/login");
  }

  const dashboardLink =
    user?.role === "admin"
      ? "/admin/dashboard"
      : user?.role === "examiner"
        ? "/examiner/dashboard"
        : "/student/dashboard";

  const navigationLinks =
    user?.role === "admin"
      ? [
          { label: "Dashboard", href: "/admin/dashboard" },
          { label: "Manage Users", href: "/admin/users" },
          { label: "Manage Students", href: "/admin/students" },
          { label: "Manage Admins", href: "/admin/admins" },
          { label: "Manage Examiners", href: "/admin/examiners" },
          { label: "Examinations", href: "/staff/examinations" },
          { label: "Manage Examination", href: "/staff/manage-exams" },
          { label: "Create Examination", href: "/examiner/exams" },
          { label: "Question Banks", href: "/staff/question-banks" },
          { label: "Manage Question Bank", href: "/examiner/question-banks" },
          { label: "Question Library", href: "/examiner/questions" },
          { label: "Grading", href: "/examiner/grading" },
          { label: "Result Review & Publication", href: "/examiner/results" },
          { label: "Proctoring Review", href: "/staff/proctoring" },
          { label: "Examination Schedules", href: "/admin/schedules" },
          { label: "Student Performance History", href: "/admin/performance" },
          { label: "Admin Activity Logs", href: "/admin/activity-logs" },
          { label: "Account Security", href: "/account/security" },
        ]
      : user?.role === "examiner"
        ? [
            { label: "Dashboard", href: "/examiner/dashboard" },
            { label: "Examinations", href: "/staff/examinations" },
            { label: "Manage Examination", href: "/staff/manage-exams" },
            { label: "Create Examination", href: "/examiner/exams" },
            { label: "Question Banks", href: "/staff/question-banks" },
            { label: "Manage Question Bank", href: "/examiner/question-banks" },
            { label: "Question Library", href: "/examiner/questions" },
            { label: "Grading", href: "/examiner/grading" },
            { label: "Result Review & Publication", href: "/examiner/results" },
            { label: "Proctoring Review", href: "/staff/proctoring" },
            { label: "Account Security", href: "/account/security" },
          ]
        : [
            { label: "Dashboard", href: "/student/dashboard" },
            { label: "Examinations", href: "/student/exams" },
            { label: "My Results", href: "/student/results" },
            { label: "Account Security", href: "/account/security" },
          ];

  if (!mounted) {
    return (
      <header className="border-b border-white/10 bg-slate-900 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <Link href="/" className="text-2xl font-bold">
            ExamGuard <span className="text-blue-400">AI</span>
          </Link>
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-900 text-white shadow-lg">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <Link
          href={user ? dashboardLink : "/"}
          className="text-2xl font-bold"
        >
          ExamGuard <span className="text-blue-400">AI</span>
        </Link>

        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={menuOpen}
          className="rounded-lg border border-white/20 px-3 py-2 text-xl md:hidden"
        >
          {menuOpen ? "×" : "☰"}
        </button>

        <nav className="hidden items-center gap-6 md:flex">
          {user ? (
            <>
              {navigationLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`text-sm transition hover:text-blue-400 ${
                    (pathname === link.href || pathname.startsWith(`${link.href}/`))
                      ? "font-semibold text-blue-400"
                      : "text-slate-300"
                  }`}
                >
                  {link.label}
                </Link>
              ))}

              <div className="flex items-center gap-3 border-l border-white/10 pl-5">
                <span className="max-w-36 truncate text-sm text-slate-300">
                  {user.full_name || user.email || "Account"}
                </span>

                <button
                  type="button"
                  onClick={logout}
                  className="rounded-lg border border-red-400/30 px-4 py-2 text-sm text-red-300 transition hover:bg-red-500/10"
                >
                  Logout
                </button>
              </div>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="text-sm text-slate-300 transition hover:text-blue-400"
              >
                Login
              </Link>

              <Link
                href="/register"
                className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold transition hover:bg-blue-500"
              >
                Register
              </Link>
            </>
          )}
        </nav>

        {menuOpen && (
          <nav className="w-full space-y-2 border-t border-white/10 pt-4 md:hidden">
            {user ? (
              <>
                <div className="mb-3 border-b border-white/10 pb-3">
                  <p className="font-semibold">
                    {user.full_name || "Account"}
                  </p>

                  <p className="text-xs capitalize text-slate-400">
                    {user.role}
                  </p>
                </div>

                {navigationLinks.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`block rounded-lg px-4 py-3 text-sm transition hover:bg-white/10 ${
                      (pathname === link.href || pathname.startsWith(`${link.href}/`))
                        ? "bg-blue-500/10 text-blue-400"
                        : "text-slate-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}

                <button
                  type="button"
                  onClick={logout}
                  className="mt-2 w-full rounded-lg border border-red-400/30 px-4 py-3 text-left text-sm text-red-300 hover:bg-red-500/10"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="block rounded-lg px-4 py-3 text-sm text-slate-300 hover:bg-white/10"
                >
                  Login
                </Link>

                <Link
                  href="/register"
                  className="block rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold hover:bg-blue-500"
                >
                  Register
                </Link>
              </>
            )}
          </nav>
        )}
      </div>
    </header>
  );
}
