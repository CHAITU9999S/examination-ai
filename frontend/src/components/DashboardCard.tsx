
import Link from "next/link";
import type { ReactNode } from "react";

interface DashboardCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: ReactNode;
  href?: string;
  className?: string;
  accent?: "blue" | "green" | "purple" | "orange" | "red";
}

const accentStyles = {
  blue: "bg-blue-500/10 text-blue-600",
  green: "bg-green-500/10 text-green-600",
  purple: "bg-purple-500/10 text-purple-600",
  orange: "bg-orange-500/10 text-orange-600",
  red: "bg-red-500/10 text-red-600",
};

export default function DashboardCard({
  title,
  value,
  description,
  icon,
  href,
  className = "",
  accent = "blue",
}: DashboardCardProps) {
  const cardContent = (
    <div
      className={`h-full rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition ${
        href ? "hover:-translate-y-1 hover:shadow-md" : ""
      } ${className}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-500">
            {title}
          </p>

          <p className="mt-3 break-words text-3xl font-bold text-slate-900">
            {value}
          </p>

          {description && (
            <p className="mt-2 text-sm text-slate-500">
              {description}
            </p>
          )}
        </div>

        {icon && (
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-xl ${accentStyles[accent]}`}
            aria-hidden="true"
          >
            {icon}
          </div>
        )}
      </div>

      {href && (
        <p className="mt-4 text-sm font-semibold text-blue-600">
          View details →
        </p>
      )}
    </div>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="block h-full rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      >
        {cardContent}
      </Link>
    );
  }

  return cardContent;
}
