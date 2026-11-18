
"use client";

import { useCallback, useEffect, useState } from "react";

export type UserRole = "student" | "examiner" | "admin";

export interface AuthUser {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  department?: string | null;
  is_active?: boolean;
}

interface LoginCredentials {
  email: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type?: string;
}

interface UseAuthReturn {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<AuthUser>;
  logout: () => void;
  refreshUser: () => Promise<AuthUser | null>;
}

const TOKEN_KEY = "examguard_access_token";
const USER_KEY = "examguard_user";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

function isValidUser(value: unknown): value is AuthUser {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.id === "number" &&
    Number.isInteger(candidate.id) &&
    candidate.id > 0 &&
    typeof candidate.full_name === "string" &&
    typeof candidate.email === "string" &&
    ["student", "examiner", "admin"].includes(
      candidate.role as string
    )
  );
}

function getErrorMessage(data: unknown, fallback: string): string {
  if (
    data &&
    typeof data === "object" &&
    "detail" in data &&
    typeof data.detail === "string"
  ) {
    return data.detail;
  }

  return fallback;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    }

    setUser(null);
    setToken(null);
    setError(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<AuthUser | null> => {
    if (typeof window === "undefined") {
      return null;
    }

    const storedToken = localStorage.getItem(TOKEN_KEY);

    if (!storedToken) {
      setUser(null);
      setToken(null);
      return null;
    }

    try {
      const response = await fetch(`${API_URL}/users/me`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${storedToken}`,
          Accept: "application/json",
        },
        cache: "no-store",
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          logout();
          return null;
        }

        throw new Error("Unable to verify your account.");
      }

      const currentUser: unknown = await response.json();

      if (!isValidUser(currentUser)) {
        logout();
        throw new Error("The server returned invalid user information.");
      }

      if (currentUser.is_active === false) {
        logout();
        throw new Error("Your account is inactive.");
      }

      localStorage.setItem(USER_KEY, JSON.stringify(currentUser));

      setUser(currentUser);
      setToken(storedToken);

      return currentUser;
    } catch (err) {
      if (err instanceof TypeError) {
        setError("Unable to connect to the examination server.");
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to verify authentication."
        );
      }

      return null;
    }
  }, [logout]);

  const login = useCallback(
    async (credentials: LoginCredentials): Promise<AuthUser> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            email: credentials.email.trim(),
            password: credentials.password,
          }),
        });

        const responseData: unknown = await response.json();

        if (!response.ok) {
          throw new Error(
            getErrorMessage(responseData, "Login failed. Please try again.")
          );
        }

        if (
          !responseData ||
          typeof responseData !== "object" ||
          !("access_token" in responseData) ||
          typeof responseData.access_token !== "string"
        ) {
          throw new Error("The server returned an invalid login response.");
        }

        const loginData = responseData as LoginResponse;

        const loginToken = loginData.access_token;

        const userResponse = await fetch(`${API_URL}/users/me`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${loginToken}`,
            Accept: "application/json",
          },
          cache: "no-store",
        });

        if (!userResponse.ok) {
          throw new Error("Login succeeded, but account verification failed.");
        }

        const currentUser: unknown = await userResponse.json();

        if (!isValidUser(currentUser)) {
          throw new Error("The server returned invalid user information.");
        }

        if (currentUser.is_active === false) {
          throw new Error("Your account is inactive.");
        }

        localStorage.setItem(TOKEN_KEY, loginToken);
        localStorage.setItem(USER_KEY, JSON.stringify(currentUser));

        setToken(loginToken);
        setUser(currentUser);

        return currentUser;
      } catch (err) {
        const message =
          err instanceof TypeError
            ? "Unable to connect to the examination server."
            : err instanceof Error
              ? err.message
              : "An unexpected login error occurred.";

        setError(message);
        throw new Error(message);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    let mounted = true;

    async function initializeAuthentication() {
      try {
        await refreshUser();
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    initializeAuthentication();

    return () => {
      mounted = false;
    };
  }, [refreshUser]);

  return {
    user,
    token,
    isAuthenticated: Boolean(user && token),
    isLoading,
    error,
    login,
    logout,
    refreshUser,
  };
}
