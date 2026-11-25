import Link from "next/link";

type AdminSectionNavigationProps = {
  previousHref: string;
  previousLabel?: string;
};

/**
 * Consistent navigation for Admin pages. The previous link returns to the
 * section that contains the current management page.
 */
export default function AdminSectionNavigation({
  previousHref,
  previousLabel = "Previous Section",
}: AdminSectionNavigationProps) {
  return (
    <nav aria-label="Admin page navigation" className="flex flex-wrap items-center justify-end gap-2">
      <Link
        href={previousHref}
        className="rounded-lg border border-white/20 px-4 py-2 text-sm font-medium transition hover:bg-white/10"
      >
        ← {previousLabel}
      </Link>
      <Link
        href="/admin/dashboard"
        className="rounded-lg border border-blue-400/40 px-4 py-2 text-sm font-semibold text-blue-300 transition hover:bg-blue-500/10"
      >
        Dashboard
      </Link>
    </nav>
  );
}
