export type UserRole = "student" | "examiner" | "admin";

export type Permission =
  | "view_student_dashboard"
  | "view_examiner_dashboard"
  | "view_admin_dashboard"
  | "view_available_exams"
  | "start_exam"
  | "submit_exam"
  | "manage_own_answers"
  | "view_own_results"
  | "manage_questions"
  | "view_question_banks"
  | "manage_question_banks"
  | "create_exam"
  | "view_own_exams"
  | "manage_grading"
  | "view_result_review"
  | "view_proctoring_events"
  | "manage_students"
  | "manage_examiners"
  | "manage_admins"
  | "manage_all_exams"
  | "view_platform_statistics"
  | "manage_platform_settings"
  | "view_exam_schedules"
  | "view_student_performance_history"
  | "view_admin_activity_logs"
  | "manage_account_security";

export const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  student: [
    "view_student_dashboard",
    "view_available_exams",
    "start_exam",
    "submit_exam",
    "manage_own_answers",
    "view_own_results",
    "manage_account_security",
  ],

  examiner: [
    "view_examiner_dashboard",
    "manage_questions",
    "view_question_banks",
    "manage_question_banks",
    "create_exam",
    "view_own_exams",
    "manage_grading",
    "view_result_review",
    "view_proctoring_events",
    "manage_account_security",
  ],

  admin: [
    // Administrators also have the examination-management capabilities
    // available to Examiners, limited to examinations and banks they own
    // when an operation is owner-scoped.
    "view_admin_dashboard",
    "manage_questions",
    "view_question_banks",
    "manage_question_banks",
    "create_exam",
    "view_own_exams",
    "manage_grading",
    "view_result_review",
    "view_proctoring_events",
    "manage_account_security",
    "view_platform_statistics",
    "manage_students",
    "manage_examiners",
    "manage_admins",
    "manage_all_exams",
    "manage_platform_settings",
    "view_exam_schedules",
    "view_student_performance_history",
    "view_admin_activity_logs",
  ],
};

export const ROLE_DASHBOARD_PATH: Record<UserRole, string> = {
  student: "/student/dashboard",
  examiner: "/examiner/dashboard",
  admin: "/admin/dashboard",
};

export const ROLE_ALLOWED_PATHS: Record<UserRole, string[]> = {
  student: [
    "/student/dashboard",
    "/student/exams",
    "/student/exam",
    "/student/results",
    "/account/security",
  ],

  examiner: [
    "/examiner/dashboard",
    "/examiner/questions",
    "/examiner/exams",
    "/examiner/question-banks",
    "/examiner/grading",
    "/examiner/results",
    "/staff/examinations",
    "/staff/manage-exams",
    "/staff/question-banks",
    "/staff/proctoring",
    "/account/security",
  ],

  admin: [
    "/admin/dashboard",
    "/admin/users",
    "/admin/students",
    "/admin/admins",
    "/admin/examiners",
    "/admin/exams",
    "/admin/schedules",
    "/admin/performance",
    "/admin/activity-logs",
    "/examiner/questions",
    "/examiner/exams",
    "/examiner/question-banks",
    "/examiner/grading",
    "/examiner/results",
    "/staff/examinations",
    "/staff/manage-exams",
    "/staff/question-banks",
    "/staff/proctoring",
    "/account/security",
  ],
};

export function isValidRole(role: unknown): role is UserRole {
  return (
    typeof role === "string" &&
    ["student", "examiner", "admin"].includes(role)
  );
}

export function hasPermission(
  role: UserRole,
  permission: Permission
): boolean {
  return ROLE_PERMISSIONS[role].includes(permission);
}

export function hasAnyPermission(
  role: UserRole,
  permissions: Permission[]
): boolean {
  return permissions.some((permission) =>
    hasPermission(role, permission)
  );
}

export function hasAllPermissions(
  role: UserRole,
  permissions: Permission[]
): boolean {
  return permissions.every((permission) =>
    hasPermission(role, permission)
  );
}

export function canAccessPath(
  role: UserRole,
  pathname: string
): boolean {
  const allowedPaths = ROLE_ALLOWED_PATHS[role];

  return allowedPaths.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`)
  );
}

export function getDashboardPath(role: UserRole): string {
  return ROLE_DASHBOARD_PATH[role];
}

export function canManageRole(
  currentRole: UserRole,
  targetRole: UserRole
): boolean {
  // Only administrators can manage accounts.
  if (currentRole !== "admin") {
    return false;
  }

  return ["student", "examiner", "admin"].includes(targetRole);
}

export function canCreateRole(
  currentRole: UserRole,
  targetRole: UserRole
): boolean {
  // Public registration is handled separately and is student-only.
  // Admin account creation must use the protected admin backend.
  return (
    currentRole === "admin" &&
    (targetRole === "admin" || targetRole === "examiner")
  );
}

export function canDeleteRole(
  currentRole: UserRole,
  targetRole: UserRole
): boolean {
  return (
    currentRole === "admin" &&
    ["student", "examiner", "admin"].includes(targetRole)
  );
}

export function canPubliclyRegister(role: UserRole): boolean {
  return role === "student";
}
