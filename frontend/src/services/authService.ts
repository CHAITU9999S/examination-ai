
import api from "./api";

export type UserRole = "student" | "examiner" | "admin";

export interface AuthUser {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  department?: string | null;
  is_active?: boolean;
  created_at?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface StudentRegistrationData {
  full_name: string;
  email: string;
  password: string;
  department?: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface PasswordChangeData {
  old_password: string;
  new_password: string;
}

const TOKEN_KEY = "examguard_access_token";
const USER_KEY = "examguard_user";

function validateLoginResponse(data: LoginResponse): void {
  if (
    !data ||
    typeof data.access_token !== "string" ||
    !data.access_token.trim()
  ) {
    throw new Error("Invalid authentication response from server.");
  }
}

export const authService = {
  async registerStudent(
    registrationData: StudentRegistrationData
  ): Promise<AuthUser> {
    return api.post<AuthUser>(
      "/auth/register",
      {
        full_name: registrationData.full_name.trim(),
        email: registrationData.email.trim(),
        password: registrationData.password,
        department: registrationData.department?.trim() || null,
      },
      { auth: false }
    );
  },

  async login(
    credentials: LoginCredentials
  ): Promise<{ user: AuthUser; token: string }> {
    const loginResponse = await api.post<LoginResponse>(
      "/auth/login",
      {
        email: credentials.email.trim(),
        password: credentials.password,
      },
      { auth: false }
    );

    validateLoginResponse(loginResponse);

    const token = loginResponse.access_token;

    const user = await api.get<AuthUser>("/users/me", {
      token,
    });

    if (!user || !user.id || !user.role) {
      throw new Error("Invalid user information returned by server.");
    }

    if (user.is_active === false) {
      throw new Error("Your account is inactive.");
    }

    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    return { user, token };
  },

  async getCurrentUser(): Promise<AuthUser> {
    const user = await api.get<AuthUser>("/users/me");

    if (!user || !user.id || !user.role) {
      throw new Error("Unable to retrieve authenticated user.");
    }

    if (user.is_active === false) {
      this.logout();
      throw new Error("Your account is inactive.");
    }

    if (typeof window !== "undefined") {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    return user;
  },

  async changePassword(
    passwordData: PasswordChangeData
  ): Promise<unknown> {
    return api.patch<unknown>(
      "/users/me/password",
      {
        old_password: passwordData.old_password,
        new_password: passwordData.new_password,
      }
    );
  },

  logout(): void {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);

    // Exam access and refresh tokens are separate from normal login tokens.
    // Clear every session-specific token so logout cannot leave a live exam
    // credential available in this browser tab.
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (
        key &&
        (
          key.startsWith("examguard_exam_token_") ||
          key.startsWith("examguard_exam_refresh_") ||
          key.startsWith("examguard_exam_id_")
        )
      ) {
        sessionStorage.removeItem(key);
      }
    }
    sessionStorage.removeItem("examguard_exam_token");
    sessionStorage.removeItem("examguard_access_token");
    sessionStorage.removeItem("examguard_active_exam_session");
  },

  getToken(): string | null {
    if (typeof window === "undefined") {
      return null;
    }

    return localStorage.getItem(TOKEN_KEY);
  },

  getStoredUser(): AuthUser | null {
    if (typeof window === "undefined") {
      return null;
    }

    const storedUser = localStorage.getItem(USER_KEY);

    if (!storedUser) {
      return null;
    }

    try {
      return JSON.parse(storedUser) as AuthUser;
    } catch {
      localStorage.removeItem(USER_KEY);
      return null;
    }
  },

  isAuthenticated(): boolean {
    return Boolean(this.getToken());
  },
};

export default authService;
