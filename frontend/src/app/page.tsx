import Link from "next/link";

const capabilities = [
  {
    number: "01",
    title: "Examination management",
    description:
      "Create and schedule assessments, organize question papers, and manage examination access from one place.",
    roles: "Administrators · Examiners",
  },
  {
    number: "02",
    title: "Examination monitoring",
    description:
      "Record relevant browser and proctoring events during an attempt so authorized staff can review flagged activity.",
    roles: "Examiners · Administrators",
  },
  {
    number: "03",
    title: "Assessment and grading",
    description:
      "Evaluate objective responses automatically and provide examiner-led review for descriptive answers.",
    roles: "Examiners",
  },
  {
    number: "04",
    title: "Results and performance",
    description:
      "Publish examination results and give students a clear view of their assessment outcomes.",
    roles: "Students · Examiners",
  },
];

const workflow = [
  ["01", "Prepare", "Create the examination and organize its questions."],
  ["02", "Schedule", "Set the examination window and permitted access."],
  ["03", "Conduct", "Students sign in and complete their timed attempts."],
  ["04", "Review", "Authorized staff review responses and recorded events."],
  ["05", "Publish", "Finalize assessment and release results to students."],
];

const audiences = [
  {
    title: "Students",
    description:
      "Access scheduled examinations, complete timed attempts, and view published results.",
    action: "Create student account",
    href: "/register",
  },
  {
    title: "Examiners",
    description:
      "Manage question banks, conduct assessments, review flagged activity, and grade responses.",
    action: "Examiner sign in",
    href: "/login",
  },
  {
    title: "Administrators",
    description:
      "Manage platform users, examination schedules, and institution-level activity.",
    action: "Administrator sign in",
    href: "/login",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[#f5f7fa] text-slate-800">
      <header className="border-b border-slate-200 bg-white">
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-3" aria-label="ExamGuard AI home">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#17365d] text-sm font-bold tracking-wide text-white">
              EG
            </span>
            <span className="leading-tight">
              <span className="block text-lg font-bold tracking-tight text-[#17365d]">
                ExamGuard <span className="font-medium text-[#4776a8]">AI</span>
              </span>
              <span className="block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Examination management
              </span>
            </span>
          </Link>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-md px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-[#17365d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#244b78]"
            >
              Student registration
            </Link>
          </div>
        </nav>
      </header>

      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[1.08fr_0.92fr] lg:items-center lg:gap-16 lg:py-24">
          <div>
            <p className="mb-5 text-xs font-bold uppercase tracking-[0.18em] text-[#4776a8]">
              Digital assessment · Secure examination workflow
            </p>
            <h1 className="max-w-2xl text-4xl font-bold leading-[1.12] tracking-tight text-[#17365d] sm:text-5xl lg:text-[3.55rem]">
              A structured platform for conducting and managing examinations.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-8 text-slate-600 sm:text-lg">
              ExamGuard AI brings examination scheduling, timed student
              attempts, proctoring-event review, assessment, and result
              publication into a single role-based system.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/register"
                className="rounded-md bg-[#17365d] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#244b78]"
              >
                Register as a student
              </Link>
              <Link
                href="/login"
                className="rounded-md border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
              >
                Sign in to your portal
              </Link>
            </div>
            <p className="mt-5 text-xs leading-6 text-slate-500">
              Student accounts can be registered publicly. Examiner and
              administrator access is provided through authorized accounts.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-[#f8fafc] p-5 shadow-[0_12px_35px_rgba(15,35,60,0.08)] sm:p-7">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Platform workflow
                </p>
                <h2 className="mt-1 text-xl font-bold text-[#17365d]">
                  From exam setup to results
                </h2>
              </div>
              <span className="rounded-md border border-[#cbd8e6] bg-white px-3 py-1.5 text-xs font-semibold text-[#315d88]">
                Role-based access
              </span>
            </div>
            <div className="mt-5 space-y-4">
              {workflow.map(([number, title, description], index) => (
                <div key={number} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#cbd8e6] bg-white text-xs font-bold text-[#315d88]">
                      {number}
                    </span>
                    {index !== workflow.length - 1 && (
                      <span className="mt-1 h-6 w-px bg-slate-300" />
                    )}
                  </div>
                  <div className="pb-2">
                    <h3 className="text-sm font-bold text-slate-800">{title}</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-lg border border-[#d7e2ed] bg-white px-4 py-3">
              <p className="text-xs leading-5 text-slate-600">
                Examination access and management options depend on the
                account&apos;s assigned role and permissions.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#4776a8]">
            Core capabilities
          </p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-[#17365d] sm:text-4xl">
            Tools for each stage of an examination
          </h2>
          <p className="mt-4 leading-7 text-slate-600">
            The platform separates responsibilities by role while keeping
            examination activity and assessment information connected.
          </p>
        </div>

        <div className="mt-9 grid gap-4 sm:grid-cols-2">
          {capabilities.map((item) => (
            <article
              key={item.number}
              className="rounded-lg border border-slate-200 bg-white p-6 transition hover:border-[#b8c9da] hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <span className="text-xs font-bold tracking-[0.14em] text-[#4776a8]">
                  {item.number}
                </span>
                <span className="rounded bg-[#eef3f8] px-2.5 py-1 text-[11px] font-semibold text-[#426486]">
                  {item.roles}
                </span>
              </div>
              <h3 className="mt-5 text-lg font-bold text-[#17365d]">
                {item.title}
              </h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">
                {item.description}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20">
          <div className="max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#4776a8]">
              Access by role
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-[#17365d] sm:text-4xl">
              The right workspace for every participant
            </h2>
          </div>

          <div className="mt-9 grid gap-4 md:grid-cols-3">
            {audiences.map((audience) => (
              <article
                key={audience.title}
                className="flex flex-col rounded-lg border border-slate-200 bg-[#fbfcfd] p-6"
              >
                <h3 className="text-lg font-bold text-[#17365d]">
                  {audience.title}
                </h3>
                <p className="mt-3 flex-1 text-sm leading-7 text-slate-600">
                  {audience.description}
                </p>
                <Link
                  href={audience.href}
                  className="mt-6 inline-flex items-center text-sm font-semibold text-[#315d88] hover:text-[#17365d]"
                >
                  {audience.action}
                  <span className="ml-2" aria-hidden="true">→</span>
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8">
        <div className="rounded-lg border border-[#d7e2ed] bg-[#edf3f8] px-6 py-7 sm:px-9 sm:py-8">
          <h2 className="text-xl font-bold text-[#17365d]">
            Privacy-conscious examination monitoring
          </h2>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-700">
            Proctoring is designed around examination events and derived
            monitoring signals for authorized review. Webcam frames are
            processed in the browser and are not uploaded or stored by the
            platform.
          </p>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-7 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p>© {new Date().getFullYear()} ExamGuard AI. All rights reserved.</p>
          <p>Digital examination and assessment platform</p>
        </div>
      </footer>
    </main>
  );
}
