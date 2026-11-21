"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AccountSecurityPage() {
  const router = useRouter();
  const [role, setRole] = useState("student");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    fetch(`${API_URL}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }).then(async (response) => {
      if (!response.ok) throw new Error("Unable to load your account.");
      const profile = await response.json();
      setRole(profile.role || "student");
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load account."));
  }, [router]);

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setMessage("");
    if (newPassword !== confirmPassword) {
      setError("The new password and confirmation do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      setError("The new password must be different from the current password.");
      return;
    }
    if (newPassword.length < 8) {
      setError("The new password must contain at least 8 characters.");
      return;
    }
    const token = localStorage.getItem("examguard_access_token");
    if (!token) { router.replace("/login"); return; }
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/users/me/password`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to change password.");
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setMessage(data.message || "Password changed successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to change password.");
    } finally { setBusy(false); }
  }

  const dashboard = role === "admin" ? "/admin/dashboard" : role === "examiner" ? "/examiner/dashboard" : "/student/dashboard";

  function PasswordVisibilityButton({ visible, onClick, label }: { visible: boolean; onClick: () => void; label: string }) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={visible ? `Hide ${label}` : `Show ${label}`}
        aria-pressed={visible}
        className="absolute inset-y-0 right-0 flex items-center px-4 text-slate-400 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
      >
        {visible ? (
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 3l18 18" />
            <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
            <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5 0 8.5 4.5 9.5 7-.4 1-1.2 2.2-2.3 3.3" />
            <path d="M6.2 6.2C3.9 7.7 2.8 10 2.5 12c1 2.5 4.5 7 9.5 7 1.3 0 2.5-.3 3.6-.8" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-10 text-white">
      <div className="mx-auto max-w-xl">
        <header className="mb-8 flex items-center justify-between gap-3">
          <div>
            <Link href={dashboard} className="text-2xl font-bold">ExamGuard <span className="text-blue-400">AI</span></Link>
            <p className="mt-1 text-sm text-slate-400">Account security</p>
          </div>
          <Link href={dashboard} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">← Dashboard</Link>
        </header>
        <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h1 className="text-2xl font-bold">Change Password</h1>
          <p className="mt-2 text-sm text-slate-400">Enter your current password to authorize the change. Your new password is stored as a secure hash.</p>
          {error && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}
          {message && <div role="status" className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">{message}</div>}
          <form onSubmit={changePassword} className="mt-6 space-y-4">
            <label className="block text-sm text-slate-300">Current password
              <div className="relative mt-2">
                <input required type={showCurrentPassword ? "text" : "password"} autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white" />
                <PasswordVisibilityButton visible={showCurrentPassword} onClick={() => setShowCurrentPassword((visible) => !visible)} label="current password" />
              </div>
            </label>
            <label className="block text-sm text-slate-300">New password
              <div className="relative mt-2">
                <input required type={showNewPassword ? "text" : "password"} minLength={8} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white" />
                <PasswordVisibilityButton visible={showNewPassword} onClick={() => setShowNewPassword((visible) => !visible)} label="new password" />
              </div>
            </label>
            <label className="block text-sm text-slate-300">Confirm new password
              <div className="relative mt-2">
                <input required type={showConfirmPassword ? "text" : "password"} minLength={8} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white" />
                <PasswordVisibilityButton visible={showConfirmPassword} onClick={() => setShowConfirmPassword((visible) => !visible)} label="confirm new password" />
              </div>
            </label>
            <button type="submit" disabled={busy} className="w-full rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50">{busy ? "Changing Password..." : "Change Password"}</button>
          </form>
        </section>
      </div>
    </main>
  );
}
