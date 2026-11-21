
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface User {
  id: number;
  full_name: string;
  email: string;
  department?: string | null;
  role: "student" | "examiner" | "admin";
  is_active: boolean | null;
}

type RoleFilter = "all" | User["role"];

export default function AdminUsersPage() {
  const router = useRouter();

  const [users, setUsers] = useState<User[]>([]);
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<number | null>(null);
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

  const loadUsers = useCallback(async () => {
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
        throw new Error("Unable to load user accounts.");
      }

      const data = await response.json();

      const userList = Array.isArray(data)
        ? data
        : Array.isArray(data.users)
          ? data.users
          : null;

      if (!userList) {
        throw new Error("The server returned an unexpected user list.");
      }

      setUsers(userList);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An unexpected error occurred."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  async function updateUserStatus(user: User) {
    const nextStatus = user.is_active !== true;

    const confirmed = window.confirm(
      `Are you sure you want to ${
        nextStatus ? "activate" : "deactivate"
      } ${user.full_name}'s account?`
    );

    if (!confirmed) return;

    setActionId(user.id);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(
        `${API_URL}/admin/users/${user.id}/status`,
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
          data.detail || "Unable to update this account."
        );
      }

      setMessage(
        `${user.full_name}'s account has been ${
          nextStatus ? "activated" : "deactivated"
        }.`
      );

      await loadUsers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to update account status."
      );
    } finally {
      setActionId(null);
    }
  }

  async function deleteUser(user: User) {
    const confirmed = window.confirm(
      user.role === "student"
        ? `Permanently delete Student ${user.full_name} (${user.email}) and all of their examination assignments, sessions, answers, marks, results, and proctoring records? This cannot be undone.`
        : `Delete the account belonging to ${user.full_name} (${user.email})?`
    );

    if (!confirmed) return;

    setActionId(user.id);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();

      if (!headers) return;

      const response = await fetch(
        `${API_URL}/admin/users/${user.id}`,
        {
          method: "DELETE",
          headers,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to delete this account."
        );
      }

      setMessage(`${user.full_name}'s account was deleted.`);
      await loadUsers();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete account."
      );
    } finally {
      setActionId(null);
    }
  }

  const filteredUsers =
    roleFilter === "all"
      ? users
      : users.filter((user) => user.role === roleFilter);

  function statusLabel(isActive: boolean | null) {
    return isActive === true ? "Active" : "Inactive";
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/admin/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">
              Administrator / User Management
            </p>
          </div>

          <Link
            href="/admin/dashboard"
            className="rounded-lg border border-white/20 px-4 py-2 text-sm font-medium transition hover:bg-white/10"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">User Management</h1>
            <p className="mt-2 text-slate-400">
              Manage student, examiner, and administrator accounts.
            </p>
          </div>

          <button
            type="button"
            onClick={loadUsers}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold transition hover:bg-blue-500 disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh Users"}
          </button>
        </div>

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

        <section className="mt-8 rounded-xl border border-white/10 bg-slate-900 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="font-semibold">Registered Accounts</h2>
              <p className="mt-1 text-sm text-slate-400">
                {filteredUsers.length} account(s) displayed
              </p>
            </div>

            <label className="flex items-center gap-3 text-sm text-slate-300">
              Filter by role

              <select
                value={roleFilter}
                onChange={(event) =>
                  setRoleFilter(event.target.value as RoleFilter)
                }
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white outline-none focus:border-blue-500"
              >
                <option value="all">All roles</option>
                <option value="student">Students</option>
                <option value="examiner">Examiners</option>
                <option value="admin">Administrators</option>
              </select>
            </label>
          </div>

          {loading ? (
            <p className="py-12 text-center text-slate-400">
              Loading user accounts...
            </p>
          ) : filteredUsers.length === 0 ? (
            <p className="py-12 text-center text-slate-400">
              No user accounts found.
            </p>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3 font-medium">User</th>
                    <th className="px-4 py-3 font-medium">Department</th>
                    <th className="px-4 py-3 font-medium">Role</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredUsers.map((user) => (
                    <tr
                      key={user.id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="px-4 py-4">
                        <p className="font-semibold">{user.full_name}</p>
                        <p className="mt-1 text-xs text-slate-400">
                          {user.email}
                        </p>
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {user.department || "—"}
                      </td>

                      <td className="px-4 py-4 capitalize text-slate-300">
                        {user.role}
                      </td>

                      <td className="px-4 py-4">
                        <span
                          className={
                            user.is_active === true
                              ? "rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-300"
                              : "rounded-full bg-slate-700 px-3 py-1 text-xs font-medium text-slate-300"
                          }
                        >
                          {statusLabel(user.is_active)}
                        </span>
                      </td>

                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => updateUserStatus(user)}
                            disabled={actionId === user.id}
                            className="rounded-lg border border-blue-400/30 px-3 py-2 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:opacity-50"
                          >
                            {user.is_active === true
                              ? "Deactivate"
                              : "Activate"}
                          </button>

                          <button
                            type="button"
                            onClick={() => deleteUser(user)}
                            disabled={actionId === user.id}
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
