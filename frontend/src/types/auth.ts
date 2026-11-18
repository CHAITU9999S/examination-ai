
export type UserRole = "student" | "examiner" | "admin";

export interface User {
  id: number;
  full_name: string;
  email: string;
  department: string | null;
  role: UserRole;
  is_active: boolean;
  created_at?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface StudentRegisterRequest {
  full_name: string;
  email: string;
  password: string;
  department?: string | null;
}

export interface AdminUserCreateRequest {
  full_name: string;
  email: string;
  password: string;
  department?: string | null;
  role: "admin" | "examiner";
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthSession {
  user: User;
  accessToken: string;
}

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

export interface UserStatusUpdateRequest {
  is_active: boolean;
}

export interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
}

export interface ApiErrorResponse {
  detail?: string;
  message?: string;
}

export function isUserRole(value: unknown): value is UserRole {
  return (
    value === "student" ||
    value === "examiner" ||
    value === "admin"
  );
}

export function isUser(value: unknown): value is User {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.id === "number" &&
    Number.isInteger(candidate.id) &&
    candidate.id > 0 &&
    typeof candidate.full_name === "string" &&
    typeof candidate.email === "string" &&
    isUserRole(candidate.role) &&
    typeof candidate.is_active === "boolean" &&
    (candidate.department === null ||
      typeof candidate.department === "string")
  );
}
