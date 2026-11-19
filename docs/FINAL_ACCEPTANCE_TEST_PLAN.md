# ExamGuard AI – Final Acceptance Test Plan

This checklist is for the post-merge, deployed application. Automated GitHub Actions checks do not replace these live browser and production-database checks.

## Before testing

- [ ] Confirm the latest Render backend deployment succeeded.
- [ ] Confirm the frontend deployment succeeded and uses the correct HTTPS backend URL.
- [ ] Confirm the PostgreSQL migration head is `0016_answer_rubric_scores`.
- [ ] Confirm the Render CORS allowed-origin list contains the deployed frontend origin.
- [ ] Keep `AI_GRADING_ENABLED=false` unless an authorized API key has been configured by the project owner.
- [ ] Do not share Admin passwords, bootstrap tokens, or API keys in chat.

## Admin bootstrap and account permissions

1. Open the backend Swagger page over HTTPS.
2. Call `POST /auth/bootstrap-admin` using the configured `X-Admin-Bootstrap-Token` header. Enter the first Admin's name, email, and password directly in Swagger.
3. Confirm the response role is `admin`.
4. Log in through the frontend and confirm the Admin dashboard opens.
5. Create an Examiner with name, email, department, and password.
6. Confirm the Examiner appears in Examiner Management with the same department.
7. Deactivate and reactivate the Examiner; confirm login is denied while inactive and allowed after reactivation.
8. Create a second Admin through Admin Management.
9. Log in as the second Admin and confirm Admin access.
10. Log in as a Student and as an Examiner; confirm both are denied access to Admin APIs and cannot create Admin accounts.
11. Open Admin Activity Logs and confirm account-creation and status-change events appear.

## Examination lifecycle

1. As an Examiner, create objective and subjective questions in the question bank.
2. Create an examination and assign the questions.
3. Confirm the configured duration, start/end window, marks, negative marking, and proctoring settings.
4. As a Student, open the available examination and read the instructions.
5. Start the examination and confirm a unique session is created.
6. Record the displayed start time and verify the countdown is based on server time.
7. Answer one question, navigate away, return, and confirm the answer was saved.
8. Submit MCQ and multi-select answers and confirm objective marks are calculated correctly.
9. Leave a question unanswered and confirm it receives zero marks.
10. Confirm the examination auto-submits when the server-side timer expires.

## Subjective grading and publication

1. Submit short-answer, long-answer, and handwritten image answers.
2. Confirm the image preview appears before upload and the server stores the uploaded answer image and generated thumbnail.
3. Confirm OCR text is available when Tesseract is installed; otherwise the answer remains available for manual review.
4. Open Examiner Grading and confirm submitted subjective answers are grouped by question.
5. Enter rubric criteria whose maximum marks add up to the question maximum.
6. Enter criterion-level awarded marks whose total equals the final marks.
7. Add examiner feedback and, for image answers, add a highlight and a text-comment annotation.
8. Test bulk grading with answers from one session.
9. If AI grading is authorized and enabled, request a suggestion and verify the examiner can override it. Otherwise confirm AI grading remains disabled.
10. Publish the completed result.
11. Log in as the Student and confirm only published results appear.
12. Open result details and verify overall marks, question-wise outcomes, feedback, rubric breakdown, annotations, and cohort percentile.
13. Confirm published marks cannot be edited afterward.

## Proctoring and privacy

1. Start a proctored exam over HTTPS and grant camera permission.
2. Confirm the webcam preview is visible and face-presence verification completes.
3. Test prolonged face absence, multiple faces, and looking away.
4. Switch tabs and move focus away from the examination window.
5. Confirm warning messages and server-recorded proctoring events appear.
6. Confirm heartbeat messages are sent every 10 seconds.
7. Open Staff Proctoring Review as the Examiner and Admin; confirm flagged sessions, event details, suspicion scores, and timestamps are visible.
8. Confirm Student accounts cannot access flagged-session review.
9. Confirm no webcam frame or snapshot is uploaded or stored. Only derived signals and event metadata should be sent to the backend.

## Browser and responsive checks

Run the same critical flow in each browser where available:

- [ ] Chrome
- [ ] Firefox
- [ ] Microsoft Edge

Check the application at these viewport sizes:

- [ ] Mobile phone
- [ ] Tablet
- [ ] Desktop

Also verify camera permission prompts, reconnect behavior, image file selection, drag-and-drop on desktop, and camera capture on supported mobile browsers.

## Database verification

After the flow, inspect PostgreSQL and confirm records exist in:

- `users` – Admin, Examiner, and Student roles and account status.
- `exams`, `question_bank`, and `exam_questions` – configured examinations and questions.
- `exam_sessions` – student session, start/submission times, status, and suspicion score.
- `answers` – objective/text/image answers, awarded marks, feedback, annotations, and rubric scores.
- `results` – question-wise scores, publication status, and publication timestamp.
- `proctor_events` – derived proctoring event types, timestamps, and suspicion points.
- `admin_activity_logs` – Admin account-management actions.

Do not reset the production database. Use read-only queries for verification.
