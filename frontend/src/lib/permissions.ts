
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
  | "create_exam"
  | "view_own_exams"
  | "manage_grading"
  | "view_proctoring_events"
  | "manage_students"
  | "manage_examiners"
  | "manage_admins"
  | "manage_all_exams"
  | "view_platform_statistics"
  | "manage_platform_settings";

export const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  student: [
    "view_student_dashboard",
    "view_available_exams",
    "start_exam",
    "submit_exam",
    "manage_own_answers",
    "view_own_results",
  ],

  examiner: [
    "view_examiner_dashboard",
    "manage_questions",
    "create_exam",
    "view_own_exams",
    "manage_grading",
    "view_proctoring_events",
  ],

  admin: [
    "view_admin_dashboard",
    "view_platform_statistics",
    "manage_students",
    "manage_examiners",
    "manage_admins",
    "manage_all_exams",
    "view_proctoring_events",
    "manage_platform_settings",
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
  ],

  examiner: [
    "/examiner/dashboard",
    "/examiner/questions",
    "/examiner/exams",
    "/examiner/grading",
  ],

  admin: [
    "/admin/dashboard",
    "/admin/users",
    "/admin/admins",
    "/admin/examiners",
    "/admin/exams",
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
