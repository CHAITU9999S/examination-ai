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
  is_active: boolean | null;
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

function PasswordVisibilityButton({
  visible,
  onClick,
  label,
}: {
  visible: boolean;
  onClick: () => void;
  label: string;
}) {
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

export default function AccountManagementPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loginHistory, setLoginHistory] = useState<LoginRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [activeSection, setActiveSection] = useState<"home" | "edit" | "password" | "login-activity">("home");
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
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

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
      setActiveSection("home");
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
    setActiveSection("home");
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

        {activeSection === "home" ? (
          <div className="space-y-6">
            <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-bold">Personal Details</h1>
                  <p className="mt-2 text-sm text-slate-400">Your saved account information.</p>
                </div>
                {editFields.some((field) => remainingEdits(field.count) > 0) && (
                  <button
                    type="button"
                    onClick={() => { setEditing(true); setActiveSection("edit"); setProfileError(""); setProfileMessage(""); }}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-500"
                  >
                    Edit Details
                  </button>
                )}
              </div>
              {profileError && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{profileError}</div>}
              {profileMessage && <div role="status" className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">{profileMessage}</div>}
              <dl className="mt-6 divide-y divide-white/10">
                {[
                  ["Account ID", profile?.id ?? "Not available"],
                  ["Name", profile?.full_name || "Not provided"],
                  ["Email ID", profile?.email || "Not provided"],
                  ["Department", profile?.department || "Not provided"],
                  ["Date of Birth", profile?.date_of_birth || "Not provided"],
                  ["Account Type", profile?.role || "Not available"],
                  ["Account Status", profile?.is_active === undefined || profile?.is_active === null ? "Not available" : profile.is_active ? "Active" : "Inactive"],
                ].map(([label, value]) => (
                  <div key={label} className="grid gap-1 py-4 sm:grid-cols-[minmax(10rem,0.8fr)_2fr] sm:gap-5">
                    <dt className="text-sm text-slate-400">{label}</dt>
                    <dd className="break-words text-sm font-semibold capitalize text-white">{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs text-slate-500">
                Remaining profile edits — Name: {remainingEdits(profile?.full_name_edit_count || 0)}, Email: {remainingEdits(profile?.email_edit_count || 0)}, Department: {remainingEdits(profile?.department_edit_count || 0)}, Date of Birth: {remainingEdits(profile?.date_of_birth_edit_count || 0)} (each limited to 3 successful edits).
              </p>
            </section>

            <section className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
              <button
                type="button"
                onClick={() => { setActiveSection("password"); setPasswordError(""); setPasswordMessage(""); }}
                className="flex min-h-16 w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-cyan-400"
              >
                <span>
                  <span className="block font-semibold">Change Password</span>
                  <span className="mt-1 block text-sm text-slate-400">Verify your current password and set a new password.</span>
                </span>
                <span aria-hidden="true" className="text-xl text-cyan-300">→</span>
              </button>
            </section>

            <section className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900">
              <button
                type="button"
                onClick={() => setActiveSection("login-activity")}
                className="flex min-h-16 w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-cyan-400"
              >
                <span>
                  <span className="block font-semibold">Login Activity</span>
                  <span className="mt-1 block text-sm text-slate-400">Review your latest successful sign-ins and device details.</span>
                </span>
                <span aria-hidden="true" className="text-xl text-cyan-300">→</span>
              </button>
            </section>
          </div>
        ) : (
          <div className="space-y-5">
            <button
              type="button"
              onClick={() => { setActiveSection("home"); setEditing(false); }}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10"
            >
              ← Account Management
            </button>

            {activeSection === "edit" && (
              <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <h1 className="text-2xl font-bold">Edit Personal Details</h1>
                <p className="mt-2 text-sm text-slate-400">Each detail has its own maximum of 3 successful edits.</p>
                {profileError && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{profileError}</div>}
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
              </section>
            )}

            {activeSection === "password" && (
              <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <h1 className="text-2xl font-bold">Password</h1>
                <p className="mt-2 text-sm text-slate-400">Enter your current password to authorize each change. You can change your password any number of times.</p>
                {passwordError && <div role="alert" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{passwordError}</div>}
                {passwordMessage && <div role="status" className="mt-5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">{passwordMessage}</div>}
                <form onSubmit={changePassword} className="mt-6 space-y-4">
                  <label className="block text-sm text-slate-300">Current password
                    <div className="relative mt-2">
                      <input required type={showCurrentPassword ? "text" : "password"} autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white" />
                      <PasswordVisibilityButton visible={showCurrentPassword} onClick={() => setShowCurrentPassword((visible) => !visible)} label="current password" />
                    </div>
                  </label>
                  <label className="block text-sm text-slate-300">New password
                    <div className="relative mt-2">
                      <input required type={showNewPassword ? "text" : "password"} minLength={8} maxLength={128} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white" />
                      <PasswordVisibilityButton visible={showNewPassword} onClick={() => setShowNewPassword((visible) => !visible)} label="new password" />
                    </div>
                  </label>
                  <label className="block text-sm text-slate-300">Confirm new password
                    <div className="relative mt-2">
                      <input required type={showConfirmPassword ? "text" : "password"} minLength={8} maxLength={128} autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-white" />
                      <PasswordVisibilityButton visible={showConfirmPassword} onClick={() => setShowConfirmPassword((visible) => !visible)} label="confirm password" />
                    </div>
                  </label>
                  <button type="submit" disabled={changingPassword} className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50">{changingPassword ? "Changing Password..." : "Change Password"}</button>
                </form>
              </section>
            )}

            {activeSection === "login-activity" && (
              <section className="rounded-2xl border border-white/10 bg-slate-900 p-6">
                <h1 className="text-2xl font-bold">Login Activity</h1>
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
            )}
          </div>
        )}
      </div>
    </main>
  );
}