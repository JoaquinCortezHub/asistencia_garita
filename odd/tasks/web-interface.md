# Web interface for facial attendance

Objective: add a local Flask web interface for facial attendance and employee-image management without introducing a database.
Branch: `feat/web-interface` · Delivery: `ask-on-risk` · Test runner: `uv run pytest` (use an external temporary cache when the sandbox requires it)

## Specs

### S1 — Web interaction

User request: "necesito que implementes la interfaz web para que se pueda interactuar con el sistema."

Acceptance: a browser can authenticate, open the attendance screen, use the browser camera, submit a capture, and receive a visible recognition/registration result.

Applicable checks: web test client flow plus local browser smoke test.

### S2 — Persistence boundary

User request: "No me interesa persistir los datos."

User request: "Quiero seguir escribiendo los logs de entrada/salida en el csv"

Acceptance: no database or new persistent data store is introduced; attendance events continue through `registrar_evento` into the existing CSV, while employee images remain in the existing filesystem directory because the requested employee-management panel needs them.

Applicable checks: existing attendance tests, web attendance tests, and inspection that no database dependency or migration is added.

### S3 — Protected employee image access

User request: "quiero poder ver las imágenes de mis empleados desde la web ingresando con una contraseña hardcodeada en el código"

Acceptance: the web UI requires a shared hardcoded password before exposing attendance and employee-management screens; the password is never rendered or logged.

Assumption: this is a local prototype constraint, not production-grade authentication; the implementation will keep the password in one isolated constant so it can later migrate to an environment secret.

Applicable checks: login success/failure, unauthenticated redirect, logout, and protected image access.

### S4 — Employee management

User request: "este panel me permita cargar o eliminar empleados."

Acceptance: an authenticated user can list employee images, upload a supported image with exactly one face, reject invalid/duplicate employees, and delete an employee image without deleting historical CSV rows.

Applicable checks: valid upload, no-face/multiple-face rejection, duplicate ID rejection, deletion, path-safety validation, and historical CSV preservation.

### S5 — Existing behavior preservation (assumption)

Assumption: the existing CLI comparison and webcam entry points remain available and their current behavior remains covered by the existing tests.

Applicable checks: existing full test suite and CLI smoke checks.

### S6 — Web attendance log view

User request: "Quiero poder ver en la web el csv con los logs de entrada/salida de cada empleado por favor"

Acceptance: an authenticated user can open a protected web view that reads the existing attendance CSV, displays entry and exit records in a table, and filters records by employee and event type without introducing a database or changing the CSV writer.

Applicable checks: authenticated route access, CSV rendering, employee/event filters, empty or missing CSV handling, and the full test suite.

## Tasks

- T1 · S1-S4 · inline · backend, authentication, recognition adapter, CSV integration, employee management, tests, and documentation · completed; 67b9701
- T2 · S1/S3/S4 · delegated writer · templates, JavaScript camera flow, and CSS with the route contract defined in the task handoff · completed; 67b9701
- T3 · S1-S5 · inline · integration validation, differential checks, README updates, and work-unit commit · completed; d69161a
- T4 · S6 · inline · protected CSV log view, filters, tests, and README update · completed; uncommitted working tree

## Log

### L1 — Original user request

"Bien, necesito que implementes la interfaz web para que se pueda interactuar con el sistema. No me interesa persistir los datos. Quiero seguir escribiendo los logs de entrada/salida en el csv y quiero poder ver las imágenes de mis empleados desde la web ingresando con una contraseña hardcodeada en el código y que este panel me permita cargar o eliminar empleados. Armá un plan de implementación /plan"

### L2 — Implementation authorization

"Bien, arrancá con el plan, delega a otros agentes si lo ves necesario"

### L3 — Evidence before implementation

- The existing project is a local Python CLI with `asistencia_facial/recognition.py`, `asistencia_facial/asistencia_cli.py`, and `asistencia_facial/attendance.py`.
- Existing verification before this feature: 10 tests passed; no web/API/auth/database implementation was present.
- The implementation will reuse `cargar_empleados`, `reconocer_frame`, and `registrar_evento` instead of duplicating their logic.

### L4 — Implementation evidence

- T1 added `asistencia_facial/web.py`, Flask configuration, the `asistencia-web` entry point, and `tests/test_web.py`; the focused web suite passed with 8 tests.
- T2 added `templates/login.html`, `templates/dashboard.html`, `templates/employees.html`, `static/app.js`, and `static/styles.css`; the delegated writer reported `node --check static/app.js`, Jinja parsing, and structural checks passing.
- Parent spot checks passed: `node --check static/app.js` and Jinja parsing of all three templates.
- Full suite passed: `18 passed, 1 warning`; the warning is the pre-existing `pkg_resources` deprecation from `face_recognition_models`.
- README now documents local startup, the hardcoded prototype password location, CSV/filesystem persistence, and browser camera constraints.
- Native review assessment was attempted after the delegated writer returned, but the review status operation failed safely because the repository metadata filesystem is read-only for the negotiated review operation; no review authority or approval was created.

### L5 — Independent verification

- The independent verifier returned PASS for S2-S5 and ADVISORY for S1 only because a physical-camera browser smoke test was unavailable; no blocker was found.
- Candidate `67b9701` passed 18 tests versus 10 tests on baseline `main`; the existing CLI behavior remained covered.
- Additional checks passed for authentication, password non-disclosure, valid upload, invalid/multiple-face rejection, safe deletion, CSV preservation, and duplicate prevention.
- `uv run` in the verifier scratch attempted network resolution and was blocked by unavailable network; `.venv/bin/python -m pytest` passed 18 tests locally.
- Scratch verification used a fresh system temporary directory; workspace source files were not modified by the verifier.

### L6 — Follow-up request

"Quiero poder ver en la web el csv con los logs de entrada/salida de cada empleado por favor"

### L7 — T4 implementation and verification

- Added the protected `GET /attendance` view. It reads the existing CSV using the established header, sorts newest records first, and filters by employee and event type without writing data or adding a database.
- Added the `Registros` navigation link, responsive table, empty state, and filter controls. README documents the new screen.
- Focused web suite passed: `11 passed, 1 warning`.
- Static checks passed: `git diff --check`, `node --check static/app.js`, and Jinja parsing for all templates.
- The full suite reached `20 passed, 1 failed`; the remaining failure is pre-existing workspace data drift because the user deleted the seven original employee images while `tests/test_recognition.py` still expects seven. The web fixture was made independent of that directory by using `assets/pruebas/FotoA.jpg`.

### L8 — Independent verification

- Independent read-only verification returned PASS for S2, S3, S4, and S6. S1 remains ADVISORY because no physical-camera browser smoke was available; S5 is ADVISORY only because the full suite still reports the unrelated deleted-employee-assets failure.
- The verifier confirmed the CSV is not modified by the view, employee and event filters isolate rows correctly, the missing-CSV empty state renders, and the configured password is absent from templates and rendered pages.
- The verifier created and removed its scratch copy under `/tmp` and made no workspace edits, installs, commits, or remote operations.

### Risk

Risk: item 2 (shared hardcoded authentication, session protection, uploaded/deleted biometric images); item 3 (new protected web routes, JSON contract, query-filter behavior, and rendered CSV table); item 5 (new Flask dependency and web entry point).
