
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

interface SidebarUser {
  id?: number;
  full_name?: string;
  email?: string;
  role?: "student" | "examiner" | "admin";
}

interface NavigationItem {
  label: string;
  href: string;
  icon: string;
}

interface SidebarProps {
  className?: string;
  onNavigate?: () => void;
}

const navigation: Record<string, NavigationItem[]> = {
  admin: [
    { label: "Dashboard", href: "/admin/dashboard", icon: "⌂" },
    { label: "Manage Users", href: "/admin/users", icon: "♙" },
    { label: "Manage Admins", href: "/admin/admins", icon: "♧" },
    { label: "Manage Examiners", href: "/admin/examiners", icon: "♧" },
    { label: "Examinations", href: "/staff/examinations", icon: "▤" },
    { label: "Manage Examination", href: "/staff/manage-exams", icon: "▣" },
    { label: "Create Examination", href: "/examiner/exams", icon: "+" },
    { label: "Question Banks", href: "/staff/question-banks", icon: "▤" },
    { label: "Manage Question Bank", href: "/examiner/question-banks", icon: "▣" },
  ],
  examiner: [
    { label: "Dashboard", href: "/examiner/dashboard", icon: "⌂" },
    { label: "Examinations", href: "/staff/examinations", icon: "▤" },
    { label: "Manage Examination", href: "/staff/manage-exams", icon: "▣" },
    { label: "Create Examination", href: "/examiner/exams", icon: "+" },
    { label: "Question Banks", href: "/staff/question-banks", icon: "▤" },
    { label: "Manage Question Bank", href: "/examiner/question-banks", icon: "▣" },
    { label: "Grading", href: "/examiner/grading", icon: "✓" },
  ],
  student: [
    { label: "Dashboard", href: "/student/dashboard", icon: "⌂" },
    { label: "Examinations", href: "/student/exams", icon: "▣" },
  ],
};

export default function Sidebar({
  className = "",
  onNavigate,
}: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [user, setUser] = useState<SidebarUser | null>(null);
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
      setUser(JSON.parse(storedUser) as SidebarUser);
    } catch {
      setUser(null);
    }
  }, [pathname]);

  function logout() {
    localStorage.removeItem("examguard_access_token");
    localStorage.removeItem("examguard_user");

    setUser(null);
    onNavigate?.();

    router.replace("/login");
  }

  if (!mounted) {
    return (
      <aside
        className={`w-full rounded-xl border border-white/10 bg-slate-900 p-5 text-white ${className}`}
      >
        <p className="font-bold">
          ExamGuard <span className="text-blue-400">AI</span>
        </p>
      </aside>
    );
  }

  if (!user || !user.role || !navigation[user.role]) {
    return (
      <aside
        className={`w-full rounded-xl border border-white/10 bg-slate-900 p-5 text-white ${className}`}
      >
        <p className="font-bold">
          ExamGuard <span className="text-blue-400">AI</span>
        </p>

        <p className="mt-3 text-sm text-slate-400">
          Please log in to access navigation.
        </p>

        <Link
          href="/login"
          onClick={onNavigate}
          className="mt-4 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-500"
        >
          Login
        </Link>
      </aside>
    );
  }

  return (
    <aside
      className={`flex w-full flex-col rounded-xl border border-white/10 bg-slate-900 p-5 text-white ${className}`}
    >
      <div className="border-b border-white/10 pb-5">
        <Link
          href={
            user.role === "admin"
              ? "/admin/dashboard"
              : user.role === "examiner"
                ? "/examiner/dashboard"
                : "/student/dashboard"
          }
          onClick={onNavigate}
          className="text-xl font-bold"
        >
          ExamGuard <span className="text-blue-400">AI</span>
        </Link>

        <p className="mt-1 text-xs capitalize text-slate-400">
          {user.role} workspace
        </p>
      </div>

      <div className="border-b border-white/10 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/20 text-lg font-bold text-blue-300">
          {(user.full_name || user.email || "U")
            .trim()
            .charAt(0)
            .toUpperCase()}
        </div>

        <p className="mt-3 truncate text-sm font-semibold">
          {user.full_name || "User"}
        </p>

        <p className="mt-1 break-all text-xs text-slate-400">
          {user.email || ""}
        </p>
      </div>

      <nav className="flex-1 space-y-2 py-5">
        <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Main Menu
        </p>

        {navigation[user.role].map((item) => {
          const active = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm transition ${
                active
                  ? "bg-blue-600 font-semibold text-white"
                  : "text-slate-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span
                aria-hidden="true"
                className="w-6 text-center text-lg"
              >
                {item.icon}
              </span>

              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 pt-5">
        <button
          type="button"
          onClick={logout}
          className="w-full rounded-lg border border-red-400/30 px-4 py-3 text-left text-sm font-semibold text-red-300 transition hover:bg-red-500/10"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}
