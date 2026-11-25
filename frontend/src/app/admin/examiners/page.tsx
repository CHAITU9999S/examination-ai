
"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Examiner {
  id: number;
  full_name: string;
  email: string;
  department?: string | null;
  role: "examiner";
  is_active: boolean | null;
}

export default function ExaminerManagementPage() {
  const router = useRouter();

  const [examiners, setExaminers] = useState<Examiner[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const getHeaders = useCallback(() => {
    const token = localStorage.getItem("examguard_access_token");

    if (!token) {
      router.replace("/login");
      return null;
    }

    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, [router]);

  const loadExaminers = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(`${API_URL}/admin/users`, {
        method: "GET",
        headers,
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load examiner accounts.");
      }

      const data = await response.json();

      const userList = Array.isArray(data)
        ? data
        : Array.isArray(data.users)
          ? data.users
          : null;

      if (!userList) {
        throw new Error("Unexpected user list returned by the server.");
      }

      setExaminers(
        userList.filter(
          (user: Examiner) => user.role === "examiner"
        )
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load examiner accounts."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadExaminers();
  }, [loadExaminers]);

  async function createExaminer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setMessage("");

    if (!fullName.trim() || !email.trim() || !password) {
      setError("Please complete all required fields.");
      return;
    }

    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }

    setCreating(true);

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(`${API_URL}/admin/users`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          department: department.trim() || null,
          password,
          role: "examiner",
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to create examiner account."
        );
      }

      setMessage("Examiner account created successfully.");

      setFullName("");
      setEmail("");
      setDepartment("");
      setPassword("");

      await loadExaminers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create examiner account."
      );
    } finally {
      setCreating(false);
    }
  }

  async function updateStatus(examiner: Examiner) {
    const nextStatus = examiner.is_active !== true;

    const confirmed = window.confirm(
      `Are you sure you want to ${
        nextStatus ? "activate" : "deactivate"
      } ${examiner.full_name}'s account?`
    );

    if (!confirmed) return;

    setActionId(examiner.id);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(
        `${API_URL}/admin/users/${examiner.id}/status`,
        {
          method: "PATCH",
          headers,
          body: JSON.stringify({
            is_active: nextStatus,
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to update examiner status."
        );
      }

      setMessage(
        `${examiner.full_name}'s account status was updated.`
      );

      await loadExaminers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to update examiner status."
      );
    } finally {
      setActionId(null);
    }
  }

  async function deleteExaminer(examiner: Examiner) {
    const confirmed = window.confirm(
      `Delete examiner ${examiner.full_name} (${examiner.email})? Existing examination records may prevent deletion.`
    );

    if (!confirmed) return;

    setActionId(examiner.id);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(
        `${API_URL}/admin/users/${examiner.id}/with-records`,
        {
          method: "DELETE",
          headers,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to delete examiner account."
        );
      }

      setMessage("Examiner account deleted successfully.");

      await loadExaminers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete examiner account."
      );
    } finally {
      setActionId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link
              href="/admin/dashboard"
              className="text-2xl font-bold"
            >
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>

            <p className="mt-1 text-sm text-slate-400">
              Administrator / Examiner Management
            </p>
          </div>

          <Link
            href="/admin/dashboard"
            className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="text-3xl font-bold">
          Examiner Management
        </h1>

        <p className="mt-2 text-slate-400">
          Create and manage examiner accounts and their access.
        </p>

        {error && (
          <div
            role="alert"
            className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-300"
          >
            {error}
          </div>
        )}

        {message && (
          <div
            role="status"
            className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-300"
          >
            {message}
          </div>
        )}

        <section className="mt-8 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-xl font-bold">
            Create Examiner
          </h2>

          <p className="mt-2 text-sm text-slate-400">
            Only an administrator can create examiner accounts.
          </p>

          <form
            onSubmit={createExaminer}
            className="mt-6 grid gap-5 sm:grid-cols-2"
          >
            <div>
              <label
                htmlFor="fullName"
                className="mb-2 block text-sm font-medium"
              >
                Full name
              </label>

              <input
                id="fullName"
                type="text"
                required
                maxLength={150}
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Enter examiner's full name"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="mb-2 block text-sm font-medium"
              >
                Email address
              </label>

              <input
                id="email"
                type="email"
                required
                maxLength={255}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Enter examiner's email"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="department"
                className="mb-2 block text-sm font-medium"
              >
                Department (Optional)
              </label>

              <input
                id="department"
                type="text"
                maxLength={100}
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
                placeholder="Enter department"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-sm font-medium"
              >
                Temporary password
              </label>

              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={8}
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Create a temporary password"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  className="absolute inset-y-0 right-3 flex items-center text-slate-400 transition hover:text-white"
                >
                  {showPassword ? (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-5 w-5"
                      aria-hidden="true"
                    >
                      <path d="M3 3l18 18" />
                      <path d="M10.6 10.6a2 2 0 002.8 2.8" />
                      <path d="M9.9 5.2A10.8 10.8 0 0112 5c5 0 9 4.5 10 7-0.4 1-1.3 2.2-2.6 3.3" />
                      <path d="M6.2 6.2C3.8 7.7 2.4 10 2 12c1 2.5 5 7 10 7 1.1 0 2.1-.2 3-.6" />
                    </svg>
                  ) : (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-5 w-5"
                      aria-hidden="true"
                    >
                      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={creating}
                className="rounded-lg bg-blue-600 px-6 py-3 font-semibold transition hover:bg-blue-500 disabled:opacity-60"
              >
                {creating ? "Creating..." : "Create Examiner"}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-10 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">
                Examiner Accounts
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                {examiners.length} examiner account(s)
              </p>
            </div>

            <button
              type="button"
              onClick={loadExaminers}
              disabled={loading}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="py-10 text-center text-slate-400">
              Loading examiner accounts...
            </p>
          ) : examiners.length === 0 ? (
            <p className="py-10 text-center text-slate-400">
              No examiner accounts found.
            </p>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[750px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Examiner</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {examiners.map((examiner) => (
                    <tr
                      key={examiner.id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="px-4 py-4">
                        <p className="font-semibold">
                          {examiner.full_name}
                        </p>

                        <p className="mt-1 text-xs text-slate-400">
                          {examiner.email}
                        </p>
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {examiner.department || "—"}
                      </td>

                      <td className="px-4 py-4">
                        <span
                          className={
                            examiner.is_active === true
                              ? "rounded-full bg-green-500/10 px-3 py-1 text-xs text-green-300"
                              : "rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-300"
                          }
                        >
                          {examiner.is_active === true
                            ? "Active"
                            : "Inactive"}
                        </span>
                      </td>

                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => updateStatus(examiner)}
                            disabled={actionId === examiner.id}
                            className="rounded-lg border border-blue-400/30 px-3 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:opacity-50"
                          >
                            {examiner.is_active === true
                              ? "Deactivate"
                              : "Activate"}
                          </button>

                          <button
                            type="button"
                            onClick={() => deleteExaminer(examiner)}
                            disabled={actionId === examiner.id}
                            className="rounded-lg border border-red-400/30 px-3 py-2 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
