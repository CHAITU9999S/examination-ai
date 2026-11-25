"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Profile {
  id: number;
  full_name: string;
  email: string;
  department: string | null;
  date_of_birth: string | null;
  full_name_edit_count: number;
  email_edit_count: number;
  department_edit_count: number;
  date_of_birth_edit_count: number;
  role: string;
}

interface LoginRecord {
  id: number;
  logged_in_at: string;
  ip_address: string | null;
  user_agent: string | null;
}

function formatDate(value: string | null) {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }) + " IST";
}

function remainingEdits(count: number) {
  return Math.max(0, 3 - count);
}

export default function AccountManagementPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loginHistory, setLoginHistory] = useState<LoginRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const dashboard = profile?.role === "admin"
    ? "/admin/dashboard"
    : profile?.role === "examiner"
      ? "/examiner/dashboard"
      : "/student/dashboard";

  const loadAccount = useCallback(async () => {
    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    const headers = { Authorization: `Bearer ${token}` };
    try {
      const response = await fetch(`${API_URL}/users/me`, {
        headers,
        cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) {
        router.replace("/login");
        return;
      }
      if (!response.ok) throw new Error("Unable to load your account details.");

      const data: Profile = await response.json();
      setProfile(data);
      setFullName(data.full_name || "");
      setEmail(data.email || "");
      setDepartment(data.department || "");
      setDateOfBirth(data.date_of_birth || "");

      const historyResponse = await fetch(`${API_URL}/users/me/login-history`, {
        headers,
        cache: "no-store",
      });
      if (historyResponse.ok) {
        const historyData: LoginRecord[] = await historyResponse.json();
        setLoginHistory(historyData);
        setHistoryError("");
      } else {
        setHistoryError("Unable to load recent login history.");
      }
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to load your account.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadAccount();
  }, [loadAccount]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileError("");
    setProfileMessage("");

    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    setSavingProfile(true);
    try {
      const response = await fetch(`${API_URL}/users/me/profile`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          department: department.trim() || null,
          date_of_birth: dateOfBirth || null,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to update your details.");

      setProfile(data as Profile);
      setFullName(data.full_name || "");
      setEmail(data.email || "");
      setDepartment(data.department || "");
      setDateOfBirth(data.date_of_birth || "");
      setEditing(false);
      setProfileMessage("Personal details updated successfully.");
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to update your details.");
    } finally {
      setSavingProfile(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError("");
    setPasswordMessage("");

    if (newPassword !== confirmPassword) {
      setPasswordError("The new password and confirmation do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      setPasswordError("The new password must be different from the current password.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("The new password must contain at least 8 characters.");
      return;
    }

    const token = localStorage.getItem("examguard_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    setChangingPassword(true);
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

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage(data.message || "Password changed successfully.");
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : "Unable to change password.");
    } finally {
      setChangingPassword(false);
    }
  }

  function cancelProfileEdit() {
    if (!profile) return;
    setFullName(profile.full_name || "");
    setEmail(profile.email || "");
    setDepartment(profile.department || "");
    setDateOfBirth(profile.date_of_birth || "");
    setEditing(false);
    setProfileError("");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <p className="text-slate-300">Loading account management...</p>
      </main>
    );
  }

  const editFields = [
    { label: "Name", count: profile?.full_name_edit_count || 0 },
    { label: "Email ID", count: profile?.email_edit_count || 0 },
    { label: "Department", count: profile?.department_edit_count || 0 },
    { label: "Date of Birth", count: profile?.date_of_birth_edit_count || 0 },
  ];

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-10 text-white">
      <div className="mx-auto max-w-4xl space-y-7">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link href={dashboard} className="text-2xl font-bold">
              ExamGuard <span className="text-blue-400">AI</span>
            </Link>
            <p className="mt-1 text-sm text-slate-400">Account Management</p>
          </div>
          <Link href={dashboard} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">
            ← Dashboard
          </Link>
        </header>

        <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">Personal Details</h1>
              <p className="mt-2 text-sm text-slate-400">
                Each detail has its own maximum of 3 successful edits.
              </p>
            </div>
            {!editing && (
              <button
                type="button"
                onClick={() => { setEditing(true); setProfileError(""); setProfileMessage(""); }}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-500"
              >
                Edit Details
              </button>
            )}
          </div>

          {profileError && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{profileError}</div>}
          {profileMessage && <div role="status" className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">{profileMessage}</div>}

          {editing ? (
            <form onSubmit={saveProfile} className="mt-6 space-y-4">
              <label className="block text-sm text-slate-300">
                Name
                <span className="ml-2 text-xs text-slate-500">{remainingEdits(profile?.full_name_edit_count || 0)} edits remaining</span>
                <input required minLength={2} maxLength={150} disabled={remainingEdits(profile?.full_name_edit_count || 0) === 0} value={fullName} onChange={(event) => setFullName(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white disabled:opacity-50" />
              </label>
              <label className="block text-sm text-slate-300">
                Email ID
                <span className="ml-2 text-xs text-slate-500">{remainingEdits(profile?.email_edit_count || 0)} edits remaining</span>
                <input required type="email" maxLength={255} disabled={remainingEdits(profile?.email_edit_count || 0) === 0} value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white disabled:opacity-50" />
              </label>
              <label className="block text-sm text-slate-300">
                Department <span className="text-xs text-slate-500">(Optional)</span>
                <span className="ml-2 text-xs text-slate-500">{remainingEdits(profile?.department_edit_count || 0)} edits remaining</span>
                <input maxLength={100} disabled={remainingEdits(profile?.department_edit_count || 0) === 0} value={department} onChange={(event) => setDepartment(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white disabled:opacity-50" />
              </label>
              <label className="block text-sm text-slate-300">
                Date of Birth <span className="text-xs text-slate-500">(Optional)</span>
                <span className="ml-2 text-xs text-slate-500">{remainingEdits(profile?.date_of_birth_edit_count || 0)} edits remaining</span>
                <input type="date" disabled={remainingEdits(profile?.date_of_birth_edit_count || 0) === 0} value={dateOfBirth} onChange={(event) => setDateOfBirth(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white disabled:opacity-50" />
              </label>
              <div className="flex flex-wrap justify-end gap-3 pt-2">
                <button type="button" onClick={cancelProfileEdit} className="rounded-lg border border-white/20 px-4 py-2 text-sm hover:bg-white/10">Cancel</button>
                <button type="submit" disabled={savingProfile} className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50">{savingProfile ? "Saving..." : "Save Details"}</button>
              </div>
            </form>
          ) : (
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-slate-800/70 p-4">
                <p className="text-xs text-slate-400">Name</p>
                <p className="mt-1 font-semibold">{profile?.full_name || "—"}</p>
                <p className="mt-2 text-xs text-slate-500">{remainingEdits(profile?.full_name_edit_count || 0)} of 3 edits remaining</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-800/70 p-4">
                <p className="text-xs text-slate-400">Email ID</p>
                <p className="mt-1 break-all font-semibold">{profile?.email || "—"}</p>
                <p className="mt-2 text-xs text-slate-500">{remainingEdits(profile?.email_edit_count || 0)} of 3 edits remaining</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-800/70 p-4">
                <p className="text-xs text-slate-400">Department</p>
                <p className="mt-1 font-semibold">{profile?.department || "Not provided"}</p>
                <p className="mt-2 text-xs text-slate-500">{remainingEdits(profile?.department_edit_count || 0)} of 3 edits remaining</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-800/70 p-4">
                <p className="text-xs text-slate-400">Date of Birth</p>
                <p className="mt-1 font-semibold">{profile?.date_of_birth || "Not provided"}</p>
                <p className="mt-2 text-xs text-slate-500">{remainingEdits(profile?.date_of_birth_edit_count || 0)} of 3 edits remaining</p>
              </div>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-2xl font-bold">Change Password</h2>
          <p className="mt-2 text-sm text-slate-400">
            You can change your password any number of times. Enter your current password to authorize each change.
          </p>
          {passwordError && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{passwordError}</div>}
          {passwordMessage && <div role="status" className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">{passwordMessage}</div>}
          <form onSubmit={changePassword} className="mt-6 space-y-4">
            <label className="block text-sm text-slate-300">Current password
              <input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white" />
            </label>
            <label className="block text-sm text-slate-300">New password
              <input required type="password" minLength={8} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white" />
            </label>
            <label className="block text-sm text-slate-300">Confirm new password
              <input required type="password" minLength={8} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white" />
            </label>
            <button type="submit" disabled={changingPassword} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50">{changingPassword ? "Changing Password..." : "Change Password"}</button>
          </form>
        </section>

        <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
          <h2 className="text-2xl font-bold">Recent Login History</h2>
          <p className="mt-2 text-sm text-slate-400">Your latest 10 successful logins, with the newest record first.</p>
          {historyError && <div role="alert" className="mt-5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-300">{historyError}</div>}
          {loginHistory.length === 0 && !historyError ? (
            <p className="mt-6 rounded-xl border border-white/10 bg-slate-800/60 p-5 text-sm text-slate-400">No login history is available yet. New successful logins will appear here.</p>
          ) : (
            <div className="mt-5 space-y-3">
              {loginHistory.map((record, index) => (
                <article key={record.id} className="rounded-xl border border-white/10 bg-slate-800/60 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold">Login {index + 1}</p>
                    <p className="text-sm text-slate-300">{formatDate(record.logged_in_at)}</p>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    <p className="text-slate-400">IP address: <span className="text-slate-200">{record.ip_address || "Unavailable"}</span></p>
                    <p className="break-all text-slate-400 sm:col-span-2">Device / Browser: <span className="text-slate-200">{record.user_agent || "Unavailable"}</span></p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
