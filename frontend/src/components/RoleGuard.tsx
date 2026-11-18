
"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

type UserRole = "student" | "examiner" | "admin";

interface RoleGuardProps {
  children: ReactNode;
  allowedRoles: UserRole[];
  fallback?: ReactNode;
}

interface StoredUser {
  id?: number;
  role?: UserRole;
}

const DASHBOARD_ROUTES: Record<UserRole, string> = {
  student: "/student/dashboard",
  examiner: "/examiner/dashboard",
  admin: "/admin/dashboard",
};

export default function RoleGuard({
  children,
  allowedRoles,
  fallback,
}: RoleGuardProps) {
  const router = useRouter();

  const [authorized, setAuthorized] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;

    setAuthorized(false);
    setChecking(true);

    const token = localStorage.getItem("examguard_access_token");
    const storedUser = localStorage.getItem("examguard_user");

    if (!token || !storedUser) {
      localStorage.removeItem("examguard_access_token");
      localStorage.removeItem("examguard_user");

      router.replace("/login");
      return;
    }

    try {
      const user = JSON.parse(storedUser) as StoredUser;

      if (
        !user ||
        !Number.isInteger(user.id) ||
        !user.role ||
        !Object.prototype.hasOwnProperty.call(
          DASHBOARD_ROUTES,
          user.role
        )
      ) {
        throw new Error("Invalid user information");
      }

      if (allowedRoles.includes(user.role)) {
        if (active) {
          setAuthorized(true);
          setChecking(false);
        }
      } else {
        router.replace(DASHBOARD_ROUTES[user.role]);
      }
    } catch {
      localStorage.removeItem("examguard_access_token");
      localStorage.removeItem("examguard_user");

      router.replace("/login");
    }

    return () => {
      active = false;
    };
  }, [allowedRoles, router]);

  if (checking) {
    return (
      <div className="flex min-h-[250px] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-9 w-9 animate-spin rounded-full border-4 border-slate-300 border-t-blue-600" />

          <p className="mt-3 text-sm text-slate-500">
            Checking permissions...
          </p>
        </div>
      </div>
    );
  }

  if (!authorized) {
    return (
      fallback ?? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <h2 className="text-lg font-semibold text-red-700">
            Access Denied
          </h2>

          <p className="mt-2 text-sm text-red-600">
            You do not have permission to view this section.
          </p>
        </div>
      )
    );
  }

  return <>{children}</>;
}
