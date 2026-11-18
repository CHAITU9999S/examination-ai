
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
- Marks and negative-marking configuration.

### Examination Management
- Examination creation and configuration.
- Subject-based question selection.
- Difficulty-based question distribution.
- Question-type distribution.
- Randomized question selection.
- Individual student paper generation.
- Examination scheduling.
- Configurable examination duration.

### Timed Examination Engine
- Unique examination sessions.
- Secure examination access tokens.
- Server-side time validation.
- Remaining-time calculation.
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
- OCR support for image-based answers.

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
- Pillow
- Tesseract OCR

### Testing
- Pytest
- HTTPX

---

## 4. User Roles and Permissions

### Admin
- Create Admin accounts.
- Delete Admin accounts, subject to platform safety checks.
- Create and delete Examiner accounts.
- View and manage Student accounts.
- Activate and deactivate user accounts.
- Manage platform configuration.

### Examiner
- Create and manage questions.
- Configure examinations.
- Generate examination papers.
- Review submitted answers.
- Review and finalize subjective grades.

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
