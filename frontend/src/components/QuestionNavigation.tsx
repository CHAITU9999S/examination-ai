
"use client";

interface QuestionNavigationProps {
  totalQuestions: number;
  currentQuestionIndex: number;
  answeredQuestionIds: number[];
  questionIds: number[];
  onNavigate: (index: number) => void;
  disabled?: boolean;
}

export default function QuestionNavigation({
  totalQuestions,
  currentQuestionIndex,
  answeredQuestionIds,
  questionIds,
  onNavigate,
  disabled = false,
}: QuestionNavigationProps) {
  const answeredSet = new Set(answeredQuestionIds);

  const answeredCount = questionIds.filter((id) =>
    answeredSet.has(id)
  ).length;

  const unansweredCount = Math.max(
    0,
    totalQuestions - answeredCount
  );

  return (
    <section
      aria-label="Question navigation"
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">
          Question Navigation
        </h2>

        <span className="text-sm text-slate-500">
          {answeredCount} / {totalQuestions} answered
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded bg-green-500" />
          Answered
        </div>

        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded border border-slate-300 bg-white" />
          Not answered
        </div>

        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded bg-blue-600" />
          Current
        </div>
      </div>

      <div className="mt-4 grid grid-cols-5 gap-2 sm:grid-cols-6 md:grid-cols-5 lg:grid-cols-6">
        {Array.from(
          { length: totalQuestions },
          (_, index) => {
            const questionId = questionIds[index];
            const isAnswered =
              questionId !== undefined &&
              answeredSet.has(questionId);

            const isCurrent =
              currentQuestionIndex === index;

            let buttonStyle =
              "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100";

            if (isAnswered) {
              buttonStyle =
                "border border-green-600 bg-green-500 text-white hover:bg-green-600";
            }

            if (isCurrent) {
              buttonStyle =
                "border border-blue-700 bg-blue-600 text-white ring-2 ring-blue-200";
            }

            return (
              <button
                key={questionId ?? index}
                type="button"
                onClick={() => onNavigate(index)}
                disabled={disabled}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`Go to question ${index + 1}${
                  isAnswered ? ", answered" : ", not answered"
                }${isCurrent ? ", current question" : ""}`}
                className={`flex aspect-square min-h-10 items-center justify-center rounded-lg text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${buttonStyle}`}
              >
                {index + 1}
              </button>
            );
          }
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 text-sm">
        <span className="text-slate-600">
          Remaining: {unansweredCount}
        </span>

        <span className="text-slate-500">
          Select a number to navigate
        </span>
      </div>
    </section>
  );
}
