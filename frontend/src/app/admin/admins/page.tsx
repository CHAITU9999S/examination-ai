
"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AdminUser {
  id: number;
  full_name: string;
  email: string;
  department?: string | null;
  role: "admin";
  is_active: boolean | null;
}

export default function AdminManagementPage() {
  const router = useRouter();

  const [admins, setAdmins] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("");
  const [password, setPassword] = useState("");

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

  const loadAdmins = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(`${API_URL}/admin/users`, {
        headers,
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load administrator accounts.");
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

      setAdmins(
        userList.filter((user: AdminUser) => user.role === "admin")
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load administrator accounts."
      );
    } finally {
      setLoading(false);
    }
  }, [getHeaders, router]);

  useEffect(() => {
    loadAdmins();
  }, [loadAdmins]);

  async function createAdmin(event: FormEvent<HTMLFormElement>) {
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
          role: "admin",
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to create administrator account."
        );
      }

      setMessage("Administrator account created successfully.");

      setFullName("");
      setEmail("");
      setDepartment("");
      setPassword("");

      await loadAdmins();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create administrator account."
      );
    } finally {
      setCreating(false);
    }
  }

  async function updateStatus(admin: AdminUser) {
    const nextStatus = admin.is_active !== true;

    if (
      !window.confirm(
        `Are you sure you want to ${
          nextStatus ? "activate" : "deactivate"
        } ${admin.full_name}'s account?`
      )
    ) {
      return;
    }

    setActionId(admin.id);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(
        `${API_URL}/admin/users/${admin.id}/status`,
        {
          method: "PATCH",
          headers,
          body: JSON.stringify({ is_active: nextStatus }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to update administrator status."
        );
      }

      setMessage("Administrator account status updated.");
      await loadAdmins();
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

  async function deleteAdmin(admin: AdminUser) {
    if (
      !window.confirm(
        `Delete administrator ${admin.full_name}? The backend may block deletion if this account is the last active administrator or has dependent records.`
      )
    ) {
      return;
    }

    setActionId(admin.id);
    setError("");
    setMessage("");

    try {
      const headers = getHeaders();
      if (!headers) return;

      const response = await fetch(
        `${API_URL}/admin/users/${admin.id}`,
        {
          method: "DELETE",
          headers,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to delete administrator account."
        );
      }

      setMessage("Administrator account deleted.");
      await loadAdmins();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete administrator account."
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
            <Link href="/admin/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">
              Administrator / Admin Management
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
        <h1 className="text-3xl font-bold">Admin Management</h1>

        <p className="mt-2 text-slate-400">
          Create and manage administrator accounts.
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
            Create Administrator
          </h2>

          <p className="mt-2 text-sm text-slate-400">
            Only an existing administrator can create another administrator.
          </p>

          <form
            onSubmit={createAdmin}
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
                required
                maxLength={150}
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Enter full name"
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
                placeholder="Enter email address"
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

              <input
                id="password"
                type="password"
                required
                minLength={8}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Create a temporary password"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 outline-none focus:border-blue-500"
              />
            </div>

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={creating}
                className="rounded-lg bg-blue-600 px-6 py-3 font-semibold transition hover:bg-blue-500 disabled:opacity-60"
              >
                {creating ? "Creating..." : "Create Administrator"}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-10 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">
                Administrator Accounts
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                {admins.length} administrator account(s)
              </p>
            </div>

            <button
              type="button"
              onClick={loadAdmins}
              disabled={loading}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm transition hover:bg-white/10 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <p className="py-10 text-center text-slate-400">
              Loading administrator accounts...
            </p>
          ) : admins.length === 0 ? (
            <p className="py-10 text-center text-slate-400">
              No administrator accounts found.
            </p>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3">Administrator</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {admins.map((admin) => (
                    <tr
                      key={admin.id}
                      className="border-b border-white/5 last:border-0"
                    >
                      <td className="px-4 py-4">
                        <p className="font-semibold">{admin.full_name}</p>
                        <p className="mt-1 text-xs text-slate-400">
                          {admin.email}
                        </p>
                      </td>

                      <td className="px-4 py-4 text-slate-300">
                        {admin.department || "—"}
                      </td>

                      <td className="px-4 py-4">
                        {admin.is_active === true ? "Active" : "Inactive"}
                      </td>

                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => updateStatus(admin)}
                            disabled={actionId === admin.id}
                            className="rounded-lg border border-blue-400/30 px-3 py-2 text-xs font-semibold text-blue-300 hover:bg-blue-500/10 disabled:opacity-50"
                          >
                            {admin.is_active === true
                              ? "Deactivate"
                              : "Activate"}
                          </button>

                          <button
                            type="button"
                            onClick={() => deleteAdmin(admin)}
                            disabled={actionId === admin.id}
                            className="rounded-lg border border-red-400/30 px-3 py-2 text-xs font-semibold text-red-300 hover:bg-red-500/10 disabled:opacity-50"
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
