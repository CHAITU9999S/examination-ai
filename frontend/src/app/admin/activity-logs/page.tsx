"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AdminSectionNavigation from "../components/AdminSectionNavigation";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ActivityLog {
  id: number;
  actor_user_id: number;
  actor_name: string;
  target_user_id: number | null;
  target_name: string | null;
  action: string;
  details: Record<string, unknown>;
  created_at: string | null;
}

function formatAction(action: string) {
  return action
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string | null) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown time"
    : date.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "medium",
      });
}

export default function AdminActivityLogsPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError("");

    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/admin/activity-logs`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });

      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to load administrator activity logs.");
      }

      const data = await response.json();
      if (!Array.isArray(data)) {
        throw new Error("The server returned an invalid activity log list.");
      }
      setLogs(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load activity logs."
      );
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10 bg-slate-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <Link href="/admin/dashboard" className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">
              Administrator / Activity Logs
            </p>
          </div>
          <AdminSectionNavigation previousHref="/admin/sections/admins" previousLabel="Admins" />
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Admin Activity Logs</h1>
            <p className="mt-2 text-slate-400">
              Latest 100 recorded administrator actions.
            </p>
          </div>
          <button
            type="button"
            onClick={loadLogs}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
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

        <section className="mt-8 rounded-xl border border-white/10 bg-slate-900 p-5">
          {loading ? (
            <p className="py-12 text-center text-slate-400">
              Loading activity logs...
            </p>
          ) : logs.length === 0 ? (
            <p className="py-12 text-center text-slate-400">
              No administrator activity has been recorded yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="px-4 py-3 font-medium">Date and time</th>
                    <th className="px-4 py-3 font-medium">Administrator</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Target</th>
                    <th className="px-4 py-3 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr
                      key={log.id}
                      className="border-b border-white/5 align-top last:border-0"
                    >
                      <td className="whitespace-nowrap px-4 py-4 text-slate-300">
                        {formatDate(log.created_at)}
                      </td>
                      <td className="px-4 py-4 font-medium">
                        {log.actor_name}
                      </td>
                      <td className="px-4 py-4">
                        {formatAction(log.action)}
                      </td>
                      <td className="px-4 py-4 text-slate-300">
                        {log.target_name || (
                          typeof log.details?.full_name === "string"
                            ? log.details.full_name
                            : "—"
                        )}
                      </td>
                      <td className="max-w-md px-4 py-4 text-xs text-slate-400">
                        <pre className="whitespace-pre-wrap break-words">
                          {JSON.stringify(log.details || {}, null, 2)}
                        </pre>
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
