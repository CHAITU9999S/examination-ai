
"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface LoginResponse {
  access_token?: string;
  token_type?: string;
  detail?: string;
  user?: UserResponse;
}

interface UserResponse {
  id: number;
  full_name: string;
  email: string;
  role: "student" | "examiner" | "admin";
  is_active: boolean;
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const submissionInProgress = useRef(false);
  const [sessionReplaced, setSessionReplaced] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSessionReplaced(params.get("reason") === "session_replaced");
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submissionInProgress.current) return;
    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email address and password.");
      return;
    }

    submissionInProgress.current = true;
    setLoading(true);

    try {
      const loginResponse = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const loginData: LoginResponse = await loginResponse
        .json()
        .catch(() => ({}));

      if (!loginResponse.ok) {
        throw new Error(
          loginData.detail || "Invalid email address or password."
        );
      }

      if (!loginData.access_token) {
        throw new Error("The server did not return an access token.");
      }

      let user: UserResponse;

      if (loginData.user) {
        // Newer backends return the authenticated profile with the token,
        // avoiding a second sequential request after successful sign-in.
        user = loginData.user;
      } else {
        // Keep compatibility with an older backend during deployment rollout.
        const userResponse = await fetch(`${API_URL}/users/me`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${loginData.access_token}`,
            "Content-Type": "application/json",
          },
        });

        if (!userResponse.ok) {
          throw new Error(
            "Login succeeded, but your account information could not be loaded."
          );
        }

        user = await userResponse.json();
      }

      if (!user.is_active) {
        throw new Error("Your account is inactive. Contact an administrator.");
      }

      const dashboardRoutes: Record<UserResponse["role"], string> = {
        student: "/student/dashboard",
        examiner: "/examiner/dashboard",
        admin: "/admin/dashboard",
      };

      const destination = dashboardRoutes[user.role];

      if (!destination) {
        throw new Error("Your account has an unsupported role.");
      }

      localStorage.setItem("examguard_access_token", loginData.access_token);
      localStorage.setItem("examguard_user", JSON.stringify(user));

      router.replace(destination);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the server. Please try again."
      );
    } finally {
      submissionInProgress.current = false;
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-12 text-white">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="text-3xl font-bold tracking-tight">
            ExamGuard <span className="text-blue-400">AI</span>
          </Link>

          <h1 className="mt-8 text-3xl font-bold">
            Welcome back
          </h1>

          <p className="mt-2 text-slate-400">
            Sign in to access your examination platform.
          </p>
          <p className="mt-3 text-sm text-blue-300">
            For account security, signing in here will sign out any other device using this account.
          </p>
        </div>

        <form
          onSubmit={handleLogin}
          className="rounded-2xl border border-white/10 bg-slate-900 p-7 shadow-2xl"
        >
          {sessionReplaced && (
            <div
              role="status"
              className="mb-5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
            >
              This account was signed in on another device, so this device was signed out. Sign in again to continue.
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
            >
              {error}
            </div>
          )}

          <div className="mb-5">
            <label
              htmlFor="email"
              className="mb-2 block text-sm font-medium text-slate-200"
            >
              Email address
            </label>

            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Enter your email address"
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            />
          </div>

          <div className="mb-6">
            <label
              htmlFor="password"
              className="mb-2 block text-sm font-medium text-slate-200"
            >
              Password
            </label>

            <div className="relative">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white outline-none transition placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                className="absolute inset-y-0 right-0 flex items-center px-4 text-slate-400 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
              >
                {showPassword ? (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M3 3l18 18" />
                    <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                    <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5 0 8.5 4.5 9.5 7-.4 1-1.2 2.2-2.3 3.3" />
                    <path d="M6.2 6.2C3.9 7.7 2.8 10 2.5 12c1 2.5 4.5 7 9.5 7 1.3 0 2.5-.3 3.6-.8" />
                  </svg>
                ) : (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>

          <p className="mt-6 text-center text-sm text-slate-400">
            Are you a new student?{" "}
            <Link
              href="/register"
              className="font-semibold text-blue-400 hover:text-blue-300"
            >
              Create an account
            </Link>
          </p>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Secure access for students, examiners, and administrators.
        </p>

        <div className="mt-6 text-center">
          <Link
            href="/"
            className="text-sm text-slate-400 transition hover:text-white"
          >
            ← Back to Home
          </Link>
        </div>
      </div>
    </main>
  );
}
