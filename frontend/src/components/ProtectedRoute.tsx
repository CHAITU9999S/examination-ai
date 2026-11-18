
"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

interface ProtectedRouteProps {
  children: ReactNode;
}

export default function ProtectedRoute({
  children,
}: ProtectedRouteProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [authorized, setAuthorized] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let isActive = true;

    function checkAuthentication() {
      const token = localStorage.getItem("examguard_access_token");
      const storedUser = localStorage.getItem("examguard_user");

      if (!token || !storedUser) {
        localStorage.removeItem("examguard_access_token");
        localStorage.removeItem("examguard_user");

        router.replace("/login");
        return;
      }

      try {
        const user = JSON.parse(storedUser);

        const validRole = [
          "student",
          "examiner",
          "admin",
        ].includes(user?.role);

        if (!validRole || !user?.id) {
          throw new Error("Invalid user information");
        }

        const role = user.role as string;

        const allowedPath =
          role === "admin"
            ? pathname.startsWith("/admin/")
            : role === "examiner"
              ? pathname.startsWith("/examiner/")
              : pathname.startsWith("/student/");

        if (!allowedPath) {
          const dashboard =
            role === "admin"
              ? "/admin/dashboard"
              : role === "examiner"
                ? "/examiner/dashboard"
                : "/student/dashboard";

          router.replace(dashboard);
          return;
        }

        if (isActive) {
          setAuthorized(true);
          setChecking(false);
        }
      } catch {
        localStorage.removeItem("examguard_access_token");
        localStorage.removeItem("examguard_user");

        router.replace("/login");
      }
    }

    setAuthorized(false);
    setChecking(true);

    checkAuthentication();

    return () => {
      isActive = false;
    };
  }, [pathname, router]);

  if (checking || !authorized) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-white">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-slate-600 border-t-blue-500" />

          <p className="mt-4 text-sm text-slate-300">
            Verifying your access...
          </p>
        </div>
      </main>
    );
  }

  return <>{children}</>;
}
