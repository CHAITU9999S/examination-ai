
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import SectionBreadcrumbNavigation from "./shared/SectionBreadcrumbNavigation";

export const metadata: Metadata = {
  title: {
    default: "ExamGuard AI",
    template: "%s | ExamGuard AI",
  },
  description:
    "An intelligent examination platform with secure online exams, automated proctoring, and candidate performance analysis.",
  applicationName: "ExamGuard AI",
  keywords: [
    "ExamGuard AI",
    "Online Examination",
    "AI Proctoring",
    "Examination Management",
    "Student Assessment",
  ],
  robots: {
    index: false,
    follow: false,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f172a",
};

interface RootLayoutProps {
  children: ReactNode;
}

export default function RootLayout({
  children,
}: Readonly<RootLayoutProps>) {
  return (
    <html lang="en">
      <body><SectionBreadcrumbNavigation />{children}</body>
    </html>
  );
}
