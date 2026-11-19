import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gray-100 text-gray-800">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <Link href="/" className="text-xl font-semibold text-blue-900">
            ExamGuard AI
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            <Link
              href="/login"
              className="rounded border border-blue-200 bg-blue-50 px-4 py-2 font-medium text-blue-900 hover:bg-blue-100"
            >
              Login
            </Link>
            <Link
              href="/register"
              className="rounded border border-blue-200 bg-blue-50 px-4 py-2 font-medium text-blue-900 hover:bg-blue-100"
            >
              Student Register
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-5 py-10">
        <section className="rounded border bg-white p-6 sm:p-8">
          <h1 className="text-2xl font-semibold text-blue-900 sm:text-3xl">
            Online Examination Management System
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-gray-600">
            ExamGuard AI is a web-based project for conducting online
            examinations. Students can attend exams and view their results.
            Examiners can prepare questions and evaluate answers. Admins can
            manage users and examinations.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/login"
              className="rounded border border-blue-200 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-900 hover:bg-blue-100"
            >
              Login
            </Link>
            <Link
              href="/register"
              className="rounded border border-blue-200 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-900 hover:bg-blue-100"
            >
              Register as Student
            </Link>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">
            Main Features
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <article className="rounded border bg-white p-5">
              <h3 className="font-semibold text-blue-900">Online Exams</h3>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                Students can view available examinations and attend them
                within the given time.
              </p>
            </article>
            <article className="rounded border bg-white p-5">
              <h3 className="font-semibold text-blue-900">Question Management</h3>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                Examiners can create questions and prepare examination papers.
              </p>
            </article>
            <article className="rounded border bg-white p-5">
              <h3 className="font-semibold text-blue-900">Exam Monitoring</h3>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                The system records examination-related events for authorized
                staff to review.
              </p>
            </article>
            <article className="rounded border bg-white p-5">
              <h3 className="font-semibold text-blue-900">Evaluation and Results</h3>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                Answers can be evaluated and published results can be viewed
                by students.
              </p>
            </article>
          </div>
        </section>

        <section className="mt-8 rounded border bg-white p-5 sm:p-6">
          <h2 className="text-xl font-semibold text-gray-800">
            Account Registration and Management
          </h2>
          <ul className="mt-4 list-disc space-y-3 pl-5 text-sm leading-6 text-gray-600">
            <li>
              <span className="font-semibold text-gray-800">Student accounts:</span>{" "}
              Students can create their own accounts only through the Student
              Register option on this homepage. Public registration is for
              students only.
            </li>
            <li>
              <span className="font-semibold text-gray-800">Examiner accounts:</span>{" "}
              Any Admin can create Examiner accounts from the Admin dashboard.
            </li>
            <li>
              <span className="font-semibold text-gray-800">Admin accounts:</span>{" "}
              The first Admin account is created through the secure bootstrap
              setup. After that, an existing Admin can create additional Admin
              accounts.
            </li>
            <li>
              <span className="font-semibold text-gray-800">Account deactivation:</span>{" "}
              Any Admin can deactivate another account when required. An Admin
              cannot deactivate their own account, and the last active Admin
              account cannot be deactivated.
            </li>
          </ul>
        </section>

        <section className="mt-8 rounded border bg-white p-5">
          <h2 className="text-xl font-semibold text-gray-800">
            User Login
          </h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            Students, Examiners and Admins use the login page. New student
            accounts can be created using the registration page. Examiner and
            additional Admin accounts are created by an existing Admin.
          </p>
          <Link
            href="/login"
            className="mt-4 inline-block text-sm font-medium text-blue-800 underline"
          >
            Go to Login
          </Link>
        </section>

        <footer className="py-8 text-center text-xs text-gray-500">
          ExamGuard AI - Online Examination Management System
        </footer>
      </div>
    </main>
  );
}
