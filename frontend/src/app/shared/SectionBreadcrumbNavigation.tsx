"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Crumb = { href: string; label: string };
type Breadcrumbs = { ancestors: Crumb[]; current: string };

const ADMIN_USERS: Crumb = { href: "/admin/sections/users", label: "Users" };
const ADMIN_EXAMS: Crumb = { href: "/admin/sections/examinations", label: "Examinations" };
const ADMIN_BANKS: Crumb = { href: "/admin/sections/question-banks", label: "Question Bank" };
const EXAMINER_EXAMS: Crumb = { href: "/admin/sections/examinations", label: "Examinations" };
const EXAMINER_BANKS: Crumb = { href: "/admin/sections/question-banks", label: "Question Bank" };

const adminSectionLabels: Record<string, string> = {
  users: "Users",
  admins: "Admins",
  examiners: "Examiners",
  students: "Students",
  "question-banks": "Question Bank",
  examinations: "Examinations",
};

function adminBreadcrumbs(pathname: string): Breadcrumbs | null {
  const sectionMatch = pathname.match(/^\/admin\/sections\/([^/]+)$/);
  if (sectionMatch) {
    const section = sectionMatch[1];
    const label = adminSectionLabels[section];
    if (!label) return null;
    const ancestors = ["admins", "examiners", "students"].includes(section) ? [ADMIN_USERS] : [];
    return { ancestors, current: label };
  }

  if (pathname === "/admin/users") return { ancestors: [ADMIN_USERS], current: "User Management" };
  if (pathname === "/admin/admins") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/admins", label: "Admins" }], current: "Admin Management" };
  if (pathname === "/admin/activity-logs") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/admins", label: "Admins" }], current: "Admin Activity Logs" };
  if (pathname === "/admin/retained-data") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/admins", label: "Admins" }, { href: "/admin/admins", label: "Admin Management" }], current: "Retained Data" };
  if (pathname === "/admin/examiners") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/examiners", label: "Examiners" }], current: "Examiner Management" };
  if (pathname === "/admin/examiner-activity-logs") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/examiners", label: "Examiners" }], current: "Examiner Activity Logs" };
  if (pathname === "/admin/students") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/students", label: "Students" }], current: "Student Management" };
  if (pathname === "/admin/schedules") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/students", label: "Students" }], current: "Student Schedule" };
  if (pathname === "/admin/performance") return { ancestors: [ADMIN_USERS, { href: "/admin/sections/students", label: "Students" }], current: "Student Performance" };
  if (pathname === "/admin/questions") return { ancestors: [ADMIN_BANKS], current: "Questions" };
  if (pathname === "/admin/exams") return { ancestors: [ADMIN_EXAMS], current: "Examinations" };

  const examQuestionBank = pathname.match(/^\/admin\/exams\/([^/]+)\/question-bank$/);
  if (examQuestionBank) return { ancestors: [ADMIN_EXAMS, { href: "/admin/exams", label: "Examinations" }], current: "Examination Bank" };
  const examDetails = pathname.match(/^\/admin\/exams\/([^/]+)$/);
  if (examDetails) return { ancestors: [ADMIN_EXAMS, { href: "/admin/exams", label: "Examinations" }], current: "Examination Details" };
  return null;
}

function staffBreadcrumbs(pathname: string, role: string): Breadcrumbs | null {
  const isAdmin = role === "admin";
  const examParent = isAdmin ? ADMIN_EXAMS : EXAMINER_EXAMS;
  const bankParent = isAdmin ? ADMIN_BANKS : EXAMINER_BANKS;

  if (pathname === "/staff/question-banks") {
    return { ancestors: bankParent ? [bankParent] : [], current: "All Question Banks" };
  }
  if (pathname === "/staff/manage-exams") {
    return { ancestors: examParent ? [examParent] : [], current: "Manage Examinations" };
  }
  if (pathname === "/staff/examinations") {
    return { ancestors: examParent ? [examParent] : [], current: "Examinations" };
  }
  if (pathname === "/staff/proctoring") {
    return {
      ancestors: [...(examParent ? [examParent] : []), { href: "/staff/manage-exams", label: "Manage Examinations" }],
      current: "Proctoring Review",
    };
  }
  if (/^\/staff\/question-banks\/[^/]+$/.test(pathname)) {
    return { ancestors: [...(bankParent ? [bankParent] : []), { href: "/staff/question-banks", label: "All Question Banks" }], current: "Question Bank Details" };
  }
  if (/^\/staff\/examinations\/[^/]+$/.test(pathname)) {
    return { ancestors: [...(examParent ? [examParent] : []), { href: "/staff/examinations", label: "Examinations" }], current: "Examination Details" };
  }
  if (/^\/staff\/manage-exams\/[^/]+\/evaluation\/[^/]+$/.test(pathname)) {
    return {
      ancestors: [...(examParent ? [examParent] : []), { href: "/staff/manage-exams", label: "Manage Examinations" }, { href: pathname.replace(/\/evaluation\/[^/]+$/, ""), label: "Examination Details" }],
      current: "Student Evaluation",
    };
  }
  if (/^\/staff\/manage-exams\/[^/]+$/.test(pathname)) {
    return { ancestors: [...(examParent ? [examParent] : []), { href: "/staff/manage-exams", label: "Manage Examinations" }], current: "Examination Details" };
  }
  return null;
}

function examinerBreadcrumbs(pathname: string, role: string): Breadcrumbs | null {
  const isAdmin = role === "admin";
  const bankParent = isAdmin ? ADMIN_BANKS : EXAMINER_BANKS;
  const examParent = isAdmin ? ADMIN_EXAMS : EXAMINER_EXAMS;
  const bankAncestors: Crumb[] = [
    bankParent,
    { href: "/examiner/question-banks", label: "Manage Question Banks" },
  ];
  const createExamAncestors: Crumb[] = isAdmin
    ? [ADMIN_EXAMS, { href: "/examiner/exams", label: "Create Examination" }]
    : [{ href: "/examiner/exams", label: "Create Examination" }];

  if (pathname === "/examiner/exams") {
    return { ancestors: [examParent], current: "Create Examination" };
  }
  if (pathname === "/examiner/question-banks") {
    return { ancestors: [bankParent], current: "Manage Question Banks" };
  }
  if (/^\/examiner\/question-banks\/[^/]+$/.test(pathname)) {
    return { ancestors: bankAncestors, current: "Question Bank Details" };
  }
  const examQuestionBank = pathname.match(/^\/examiner\/exams\/([^/]+)\/question-bank$/);
  if (examQuestionBank) {
    const ancestors = isAdmin
      ? [ADMIN_EXAMS, { href: "/staff/manage-exams", label: "Manage Examinations" }, { href: `/staff/manage-exams/${examQuestionBank[1]}`, label: "Examination Details" }]
      : [{ href: "/examiner/exams", label: "Create Examination" }];
    return { ancestors, current: "Examination Bank" };
  }
  if (/^\/examiner\/exams\/[^/]+\/select-question-bank$/.test(pathname)) {
    return { ancestors: createExamAncestors, current: "Select Question Bank" };
  }
  if (pathname === "/examiner/questions") {
    return { ancestors: bankAncestors, current: "Questions" };
  }
  if (pathname === "/examiner/grading") {
    return { ancestors: [examParent, { href: "/staff/manage-exams", label: "Manage Examinations" }], current: "Evaluation" };
  }
  if (pathname === "/examiner/results") {
    return { ancestors: [examParent, { href: "/staff/manage-exams", label: "Manage Examinations" }], current: "Results" };
  }
  return null;
}

function studentBreadcrumbs(pathname: string): Breadcrumbs | null {
  if (pathname === "/student/exams") return { ancestors: [], current: "Examinations" };
  if (/^\/student\/exam\/[^/]+$/.test(pathname)) return { ancestors: [{ href: "/student/exams", label: "Examinations" }], current: "Examination" };
  if (pathname === "/student/results") return { ancestors: [], current: "Results" };
  if (/^\/student\/results\/[^/]+$/.test(pathname)) return { ancestors: [{ href: "/student/results", label: "Results" }], current: "Result Details" };
  return null;
}

export default function SectionBreadcrumbNavigation() {
  const pathname = usePathname() || "";
  const [role, setRole] = useState("examiner");

  useEffect(() => {
    try {
      const storedUser = localStorage.getItem("examguard_user");
      const user = storedUser ? JSON.parse(storedUser) : null;
      if (user?.role) setRole(String(user.role));
    } catch {
      setRole("examiner");
    }
  }, [pathname]);

  if (
    pathname === "/account/management" ||
    pathname === "/account/security" ||
    pathname === "/admin/dashboard" ||
    pathname === "/examiner/dashboard" ||
    pathname === "/student/dashboard" ||
    !/^\/(admin|examiner|student|staff)(\/|$)/.test(pathname)
  ) return null;

  const examinerSharedSection = role === "examiner" &&
    /^\/admin\/sections\/(question-banks|examinations)$/.test(pathname);
  const dashboardHref = examinerSharedSection
    ? "/examiner/dashboard"
    : pathname.startsWith("/admin/") ||
      (role === "admin" && (pathname.startsWith("/examiner/") || pathname.startsWith("/staff/")))
      ? "/admin/dashboard"
      : pathname.startsWith("/student/")
        ? "/student/dashboard"
        : "/examiner/dashboard";

  const breadcrumbs =
    pathname.startsWith("/admin/")
      ? adminBreadcrumbs(pathname)
      : pathname.startsWith("/student/")
        ? studentBreadcrumbs(pathname)
        : pathname.startsWith("/staff/")
          ? staffBreadcrumbs(pathname, role)
          : examinerBreadcrumbs(pathname, role);

  const pathParts = pathname.split("/").filter(Boolean);
  const lastPart = pathParts[pathParts.length - 1];
  const current = breadcrumbs?.current || lastPart?.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) || "Details";
  const ancestors = breadcrumbs?.ancestors || [];

  return (
    <nav aria-label="Previous sections" className="mx-auto mb-5 flex w-full max-w-7xl flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-slate-900/80 px-4 py-3 text-sm">
      <Link href={dashboardHref} className="font-semibold text-blue-300 transition hover:text-blue-200">
        Dashboard
      </Link>
      {ancestors.map((item) => (
        <span key={item.href} className="flex items-center gap-2">
          <span aria-hidden="true" className="text-slate-500">/</span>
          <Link href={item.href} className="text-slate-300 transition hover:text-white">
            {item.label}
          </Link>
        </span>
      ))}
      <span aria-hidden="true" className="text-slate-500">/</span>
      <span aria-current="page" className="font-semibold text-white">{current}</span>
    </nav>
  );
}
