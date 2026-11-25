"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const routeTemplates = [
  "/admin/dashboard", "/admin/users", "/admin/admins", "/admin/examiners",
  "/admin/students", "/admin/exams", "/admin/exams/[examId]",
  "/admin/exams/[examId]/question-bank", "/admin/questions",
  "/admin/sections/[section]", "/admin/activity-logs",
  "/admin/examiner-activity-logs", "/admin/performance",
  "/admin/retained-data", "/admin/schedules",
  "/examiner/dashboard", "/examiner/exams", "/examiner/exams/[examId]/question-bank",
  "/examiner/exams/[examId]/select-question-bank", "/examiner/question-banks",
  "/examiner/question-banks/[bankId]", "/examiner/questions",
  "/examiner/grading", "/examiner/results",
  "/student/dashboard", "/student/exams", "/student/exam/[sessionId]",
  "/student/results", "/student/results/[sessionId]",
  "/staff/examinations", "/staff/examinations/[examId]",
  "/staff/manage-exams", "/staff/manage-exams/[examId]",
  "/staff/manage-exams/[examId]/evaluation/[sessionId]",
  "/staff/proctoring", "/staff/question-banks", "/staff/question-banks/[bankId]",
];

const labels: Record<string, string> = {
  dashboard: "Dashboard",
  users: "Users",
  admins: "Admin Management",
  examiners: "Examiner Management",
  students: "Student Management",
  exams: "Examinations",
  questions: "Questions",
  sections: "Sections",
  "activity-logs": "Admin Activity Logs",
  "examiner-activity-logs": "Examiner Activity Logs",
  performance: "Student Performance",
  "retained-data": "Retained Data",
  schedules: "Student Schedules",
  "question-bank": "Examination Bank",
  "question-banks": "Question Banks",
  "select-question-bank": "Select Question Bank",
  grading: "Evaluation",
  results: "Results",
  exam: "Examination",
  examinations: "Examinations",
  "manage-exams": "Manage Examinations",
  proctoring: "Proctoring Review",
  evaluation: "Evaluation",
};

function routeMatches(template: string, pathname: string) {
  const pattern = template
    .split("/")
    .map((part) => part.startsWith("[") ? "[^/]+" : part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("/");
  return new RegExp(`^${pattern}$`).test(pathname);
}

function titleFor(template: string, actualPath: string) {
  const templateParts = template.split("/").filter(Boolean);
  const actualParts = actualPath.split("/").filter(Boolean);
  const last = templateParts[templateParts.length - 1];
  if (last?.startsWith("[") && actualParts.length) {
    if (template.includes("/evaluation/")) return "Student Evaluation";
    if (template.includes("/question-bank")) return "Question Bank Details";
    if (template.includes("/select-question-bank")) return "Select Question Bank";
    if (template.includes("/manage-exams/")) return "Examination Details";
    if (template.includes("/examinations/")) return "Examination Details";
    if (template.includes("/results/")) return "Result Details";
    if (template.includes("/question-banks/")) return "Question Bank Details";
    return "Details";
  }
  return labels[last] || last.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function SectionBreadcrumbNavigation() {
  const pathname = usePathname() || "";

  // Account Management already provides its role-aware Dashboard link.
  if (
    pathname === "/account/management" ||
    pathname === "/account/security" ||
    !/^\/(admin|examiner|student|staff)(\/|$)/.test(pathname)
  ) return null;

  const dashboardHref = pathname.startsWith("/admin/")
    ? "/admin/dashboard"
    : pathname.startsWith("/student/")
      ? "/student/dashboard"
      : pathname.startsWith("/staff/")
        ? "/examiner/dashboard"
        : "/examiner/dashboard";

  if (pathname === dashboardHref) return null;

  const parts = pathname.split("/").filter(Boolean);
  const ancestors: { href: string; label: string }[] = [];

  for (let index = 1; index < parts.length; index += 1) {
    const href = "/" + parts.slice(0, index).join("/");
    const template = routeTemplates.find((candidate) => routeMatches(candidate, href));
    if (template && href !== dashboardHref) {
      ancestors.push({ href, label: titleFor(template, href) });
    }
  }

  const currentTemplate = routeTemplates.find((candidate) => routeMatches(candidate, pathname));
  const currentLabel = currentTemplate
    ? titleFor(currentTemplate, pathname)
    : titleFor("/" + parts.join("/"), pathname);

  return (
    <nav aria-label="Previous sections" className="mx-auto mb-5 flex w-full max-w-7xl flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-slate-900/80 px-4 py-3 text-sm">
      <Link
        href={dashboardHref}
        className="font-semibold text-blue-300 transition hover:text-blue-200"
      >
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
      <span aria-current="page" className="font-semibold text-white">{currentLabel}</span>
    </nav>
  );
}
