
# ExamGuard AI

## AI-Based Intelligent Examination Platform with Automated Proctoring and Candidate Performance Analysis

ExamGuard AI is a web-based examination platform designed to conduct secure online examinations using automated examination management, timed exam sessions, AI-assisted evaluation, and browser-based proctoring.

The platform provides separate access and functionality for Students, Examiners, and Administrators.

---

## 1. Project Objectives

- Conduct secure online examinations.
- Manage questions and examination configurations.
- Generate randomized examination papers.
- Enforce server-side examination timing.
- Support multiple question and answer types.
- Automatically evaluate objective answers.
- Assist examiners with subjective answer evaluation.
- Monitor examination activity using browser-based proctoring.
- Analyze candidate examination performance.

---

## 2. Main Features

### Authentication and Account Management
- Student self-registration.
- Login for Students, Examiners, and Admins.
- JWT-based authentication.
- Role-based authorization.
- Secure password hashing.
- Admin-controlled account creation and management.

### Question Bank
- MCQ questions.
- Multiple-select questions.
- Short-answer questions.
- Long-answer questions.
- Image-upload questions.
- Subject and difficulty classification.
- Separate examination-specific question banks.
- Add, remove, and delete a complete examination question bank.
- Copy questions from earlier authorized banks as independent snapshots.
- Source-question tracking so reuse does not modify the original.
- Type/difficulty filters and per-question timer configuration.
- Marks and negative-marking configuration.

### Examination Management
- Examination creation and configuration.
- Subject-based question selection.
- Difficulty-based question distribution.
- Exact question counts for every question-type/difficulty combination.
- Randomized question selection with distinct papers when combinations are available.
- Persisted individual student papers.
- Student-specific exam assignment and access enforcement.
- Examination scheduling and configurable examination duration.
- Three-revision configuration history before a student session starts.

### Timed Examination Engine
- Unique examination sessions.
- Secure examination access tokens.
- Server-side time validation.
- Remaining-time calculation and server-enforced per-question timers.
- Saved question progress, answers, and timer state across refresh/reconnection.
- Pause/resume controls that do not extend the official deadline.
- Automatic submission after expiry.
- Protection against duplicate active sessions.

### Answer Management
- Objective answer submission.
- Text-answer submission.
- Image-answer uploads.
- Answer validation.
- Secure answer storage.

### Evaluation
- Automatic MCQ evaluation.
- Multiple-select evaluation.
- Negative marking.
- AI-assisted subjective evaluation.
- Suggested marks and evaluation explanations.
- Examiner review and final grading.
- AI suggestions kept separate from approved marks.
- Human mark revision history with a three-revision limit per answer.
- OCR and AI vision evaluation support for image-based answers.
- Published student results with question-wise marks, percentages, and grades.

### Automated Proctoring
- Browser tab visibility and window-focus event monitoring.
- Webcam permission and live preview.
- Browser-side MediaPipe Face Landmarker for face-presence and multiple-face detection.
- Approximate horizontal iris-position gaze estimation.
- Authenticated reporting of browser and computer-vision events.
- Server-side event validation and suspicion-score calculation.
- WebSocket heartbeat and server-side session-expiry checks.

Face and gaze inference runs locally in the candidate's browser. Camera frames are not uploaded by the detector. Gaze estimation is a coarse attention indicator and can be affected by lighting, glasses, camera placement, and device differences; it is not proof of misconduct or a replacement for examiner review. The MediaPipe WASM runtime and model are loaded from public CDNs, so the browser needs network access as well as camera permission over HTTPS.

---

## 3. Technology Stack

### Backend
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Psycopg 3
- Alembic
- Pydantic

### Frontend
- Next.js
- React
- TypeScript

### Authentication and Security
- JWT
- Passlib
- Bcrypt
- Role-based access control

### AI and Image Processing
- OpenAI API
- MediaPipe Tasks Vision (browser-side face landmarks)
- Pillow
- Tesseract OCR

### Testing
- Pytest
- HTTPX

---

## 4. User Roles and Permissions

### Admin
- Create additional Admin and Examiner accounts.
- View all accounts and activate, deactivate, or reactivate accounts.
- Create and manage examinations that the Admin personally owns.
- View Examiner-created examinations and question banks in read-only mode.
- Assign students to Admin-owned examinations.
- Review submissions, AI suggestions, final marks, proctoring events, and results.
- View student lists, Examiner lists, schedules, and historical performance.

### Examiner
- Create and manage only examinations they own.
- Add/remove questions and manage their examination-specific question banks.
- Reuse questions from their own previous examination banks as independent copies.
- Configure type/difficulty counts, question timers, schedules, and student assignments.
- Review submissions, AI suggestions, and proctoring information for their own exams.
- Approve AI suggestions, revise marks within the revision limit, and publish results.

### Student
- Register through public registration.
- Log in securely.
- View available examinations.
- Attend examinations.
- Submit answers.
- View permitted examination results.

Public registration is restricted to Students.

The first Admin account must be created through a secure backend bootstrap process.

---

## AI Provider Configuration

AI grading is optional and disabled by default. The backend accepts an AI key only through server-side environment variables:

- `AI_API_KEY`: preferred provider credential.
- `AI_API_BASE_URL`: optional base URL for an OpenAI-compatible provider.
- `AI_GRADING_MODEL`: provider model name.
- `AI_GRADING_ENABLED`: set to `True` only when the backend provider is configured.
- `OPENAI_API_KEY`: backward-compatible fallback for existing setups.

Never place an AI key in `frontend/.env`, browser code, GitHub source, or a student's exam token. The frontend does not receive the provider credential. If a mentor supplies a provider key, configure it only as a backend secret and use only the provider quota/terms authorized for the project. No live environment variables are changed by this source-code update.

## 5. Project Architecture

The project follows a modular architecture with separate backend, frontend, database, testing, and configuration layers.

```text
examination-ai/
│
├── app/
│   ├── routers/
│   ├── services/
│   ├── utils/
│   ├── models.py
│   ├── schemas.py
│   ├── dependencies.py
│   ├── auth.py
│   ├── database.py
│   └── main.py
│
├── alembic/
│   └── versions/
│
├── tests/
│
├── frontend/
│   └── src/
│       ├── app/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── lib/
│       └── types/
│
├── requirements.txt
├── .env.example
├── .gitignore
├── alembic.ini
└── README.md
```

The target implementation contains a 102-file planned architecture. Additional generated migration files may be created when required.

---

## 6. Database

PostgreSQL is used as the primary database.

The existing database includes:

- users
- question_bank
- options
- exams
- exam_questions
- exam_sessions
- answers
- results
- proctor_events
- admin_activity_logs

SQLAlchemy manages database models and queries.

Alembic manages database schema migrations.

### Database Safety

Existing migrations that have already been applied must be preserved.

Future database changes must use reviewed, additive migrations.

Existing tables, records, and columns must not be deleted or reset during routine development.

---

## 7. Development Scope

### Milestone 1
- Database and backend foundation.
- Authentication and role permissions.
- Question bank management.
- Examination configuration.
- Randomized examination paper generation.
- Database migrations.
- Initial automated tests.

### Milestone 2
- Timed examination sessions.
- Secure exam access.
- Answer submission.
- Automatic objective evaluation.
- AI-assisted subjective evaluation.
- Image answer processing and OCR.
- Automated browser-based proctoring.
- Basic frontend interface.
- Web access and integration.

The current implementation is limited to Milestones 1 and 2 and the agreed UI and web-access requirements.

---

## Milestone 2 Runtime Requirements and Known Integration Work

- AI-assisted grading is disabled by default. It requires an explicitly enabled setting and a valid server-side OpenAI API key. The examiner must review and approve marks; AI suggestions do not directly finalize grades.
- The supplied Dockerfile installs the Tesseract executable and English language pack. Non-Docker deployments must install Tesseract separately and set TESSERACT_CMD.
- The supplied docker-compose.yml mounts a named Docker volume at the configured answer upload directory. Cloud deployments must configure an equivalent persistent disk/volume; container-local ephemeral storage is not durable.
- The student exam flow now uses the backend's exam-start, paper, remaining-time, answer-save, image-upload, and submit routes. Students can list available exams; exam paper responses include the IDs and metadata expected by the frontend.
- AI grading remains disabled by default. It requires an administrator-configured server-side API key and explicit enablement; the examiner must review and approve marks.

### Backend Container Deployment

The repository includes a backend Dockerfile and Docker Compose configuration. The image installs Tesseract OCR and stores uploaded answer images in the named `examguard_uploads` volume.

1. Copy `.env.example` to `.env`.
2. Set a valid PostgreSQL `DATABASE_URL` and a strong `JWT_SECRET_KEY` in `.env`.
3. Start the backend with `docker compose up --build -d`.
4. Keep the `examguard_uploads` volume attached to the backend when redeploying.

Running `docker compose down` preserves the named volume. Do not use `docker compose down -v` unless you intentionally want to delete uploaded answer files. Never commit `.env` or API keys.

## 8. Security

- JWT-based authentication.
- Secure password hashing.
- Role-based access control.
- Student-specific examination sessions.
- Exam-specific access tokens.
- Server-side examination timing.
- Input validation.
- Secure file upload handling.
- Protection against duplicate submissions.
- Proctoring event records.

API keys, database credentials, and other secrets must be stored in environment variables and must never be committed to GitHub.

---

## 9. Testing

The project uses Pytest for automated testing.

Testing areas include:

- Authentication.
- User permissions.
- Admin account management.
- Question validation.
- Examination configuration.
- Randomized paper generation.
- Timed examination sessions.
- Answer submission.
- Objective evaluation.
- Proctoring events.

---

## 10. Project Status

Development is organized around the agreed 102-file target architecture.

Files are reviewed and integrated incrementally.

A feature is considered complete only after its implementation and relevant tests have been checked.


## Final acceptance testing

The deployment and manual verification checklist is available in [docs/FINAL_ACCEPTANCE_TEST_PLAN.md](docs/FINAL_ACCEPTANCE_TEST_PLAN.md). It covers Admin bootstrap, role permissions, examination lifecycle, grading, result publication, proctoring privacy, and browser/device checks.
