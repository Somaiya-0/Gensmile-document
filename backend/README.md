# GenSmile Documents — API

FastAPI backend for the standalone GenSmile Documents app: sign-in, and the
doctor's patient documents (create/edit, send a fill-in link to the patient,
share a view-only copy with another doctor). Carved out of the full GenSmile
API, but fully independent from it — its own database, its own doctor and
staff accounts, no shared auth or data. Doctor accounts are created by an
admin via `/api/v1/admin/doctors`, not inherited from the legacy app.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # or provide the variables below
uvicorn app.main:app --reload
```

## Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (asyncpg) — this app's own dedicated database, separate from the legacy GenSmile database |
| `ACCESS_TOKEN_SECRET` | Signs login tokens. **Set a long random value in production** |
| `FRONTEND_BASE_URL` | This app's public URL — used in patient fill-in and doctor-share links |
| `ALLOWED_ORIGINS` | JSON list of allowed browser origins — include the new domain |
| `S3_*`, `AWS_*` | Where document attachments and logos are stored |
| `SMTP_*` | Password-reset / verification emails |

## API surface

- `/api/v1/auth/*` — login, refresh, logout, forgot/reset password, accept staff invitation, `/me`, email verification
- `/api/v1/admin/doctors` — list/create doctor accounts (admin only)
- `/api/v1/patient-documents/*` — the doctor's documents (auth required)
- `/api/v1/form-config` — default document form layout and logo
- `/api/v1/doctors/patients` — the doctor's patient list (for the "Existing patient" picker)
- `/api/v1/staff/me` — a staff user's own record and permissions
- `/api/v1/patient-document/{fill_token}` — patient fill-in form (no login; the link is the key)
- `/api/v1/doctor-to-doctor/documents/{share_token}` — view-only shared copy (no login)
- `/api/v1/health`
