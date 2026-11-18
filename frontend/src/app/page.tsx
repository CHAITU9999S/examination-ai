
import Link from "next/link";

const features = [
  {
    number: "01",
    title: "Secure Online Exams",
    description:
      "Conduct structured online examinations with scheduled sessions and controlled examination access.",
  },
  {
    number: "02",
    title: "AI-Assisted Proctoring",
    description:
      "Monitor examination activity through face detection, gaze tracking, and browser activity events.",
  },
  {
    number: "03",
    title: "Automated Evaluation",
    description:
      "Automatically evaluate objective answers and support examiner review of subjective responses.",
  },
  {
    number: "04",
    title: "Performance Analysis",
    description:
      "Calculate examination results and provide structured assessment information.",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-white/10">
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="text-2xl font-bold tracking-tight text-white"
          >
            ExamGuard <span className="text-blue-400">AI</span>
          </Link>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/10"
            >
              Login
            </Link>

            <Link
              href="/register"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
            >
              Register
            </Link>
          </div>
        </nav>
      </header>

      <section className="mx-auto grid max-w-7xl gap-12 px-6 py-24 md:grid-cols-2 md:items-center md:py-32">
        <div>
          <p className="mb-5 inline-flex rounded-full border border-blue-400/30 bg-blue-400/10 px-4 py-2 text-sm font-medium text-blue-300">
            Intelligent Examination Platform
          </p>

          <h1 className="max-w-2xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            A smarter and more secure way to conduct examinations.
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-8 text-slate-300">
            ExamGuard AI combines secure online examinations,
            automated proctoring, objective evaluation, and
            examiner-assisted assessment in one platform.
          </p>

          <div className="mt-9 flex flex-wrap gap-4">
            <Link
              href="/register"
              className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg shadow-blue-950/40 transition hover:bg-blue-500"
            >
              Get Started
            </Link>

            <Link
              href="/login"
              className="rounded-xl border border-white/20 px-6 py-3 font-semibold text-white transition hover:bg-white/10"
            >
              Sign In
            </Link>
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-slate-900 p-8 shadow-2xl shadow-black/30">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">
                Examination Platform
              </p>
              <h2 className="mt-1 text-2xl font-bold">
                ExamGuard AI
              </h2>
            </div>

            <div className="rounded-xl bg-blue-500/15 p-3 text-2xl">
              <span role="img" aria-label="Security shield">
                🛡️
              </span>
            </div>
          </div>

          <div className="space-y-4">
            {[
              ["Secure access", "Controlled examination sessions"],
              ["Smart monitoring", "Proctoring event tracking"],
              ["Quick evaluation", "Objective answer assessment"],
              ["Examiner review", "Subjective answer grading"],
            ].map(([title, description]) => (
              <div
                key={title}
                className="rounded-xl border border-white/10 bg-slate-800/70 p-4"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-1 text-blue-400">✓</span>
                  <div>
                    <h3 className="font-semibold text-white">
                      {title}
                    </h3>
                    <p className="mt-1 text-sm text-slate-400">
                      {description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-white/10 bg-slate-900/60">
        <div className="mx-auto max-w-7xl px-6 py-20">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-widest text-blue-400">
              Platform capabilities
            </p>

            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              Everything needed for a modern examination workflow.
            </h2>
          </div>

          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => (
              <article
                key={feature.number}
                className="rounded-2xl border border-white/10 bg-slate-900 p-6 transition hover:border-blue-400/50"
              >
                <p className="text-sm font-bold text-blue-400">
                  {feature.number}
                </p>

                <h3 className="mt-5 text-xl font-bold">
                  {feature.title}
                </h3>

                <p className="mt-3 text-sm leading-7 text-slate-400">
                  {feature.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="rounded-3xl border border-blue-400/20 bg-blue-500/10 px-8 py-12 text-center">
          <h2 className="text-3xl font-bold">
            Ready to use ExamGuard AI?
          </h2>

          <p className="mx-auto mt-4 max-w-2xl leading-7 text-slate-300">
            Students can create an account and access their
            examinations. Examiners and administrators can
            sign in using their authorized accounts.
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link
              href="/register"
              className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-500"
            >
              Student Registration
            </Link>

            <Link
              href="/login"
              className="rounded-xl border border-white/20 px-6 py-3 font-semibold text-white transition hover:bg-white/10"
            >
              Login to Platform
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10 px-6 py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 text-sm text-slate-400 sm:flex-row">
          <p>
            © {new Date().getFullYear()} ExamGuard AI. All rights reserved.
          </p>

          <p>Intelligent Examination Platform</p>
        </div>
      </footer>
    </main>
  );
}
