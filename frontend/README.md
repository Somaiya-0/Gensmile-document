# GenSmile Documents

A standalone web app for the GenSmile **Documents** section, carved out of the
full GenSmile frontend for its own domain. Doctors and their staff sign in and
land straight on their patient documents: no sidebar, credits, or other
GenSmile sections, just a top bar with the logo and a profile menu (sign out).

## Pages

| Path | What it is |
|---|---|
| `/signin`, `/forgot-password`, `/reset-password` | Sign-in and password reset |
| `/set-password` | Staff invitation: set a first password |
| `/documents` | The Documents page (signed in, doctor or staff) |
| `/documents/settings` | Default document form layout |
| `/documents/print/:id` | Print view of a document |
| `/patient-document/:fillToken` | Patient fills in their document (no login; the link is the key) |
| `/doctor-to-doctor/documents/:token` | View-only copy shared with another doctor (no login) |

`/` sends signed-in users to `/documents` and everyone else to `/signin`.
Patient, affiliate and admin accounts are signed straight back out: this app
is only for doctors and their staff.

## Running

```bash
npm install
cp .env.example .env   # point VITE_API_BASE_URL at the Documents API
npm run dev            # http://localhost:3000
npm run build          # production build in dist/
```

Pairs with the backend in `../backend`. On the backend, set
`FRONTEND_BASE_URL` to this app's URL (patient and doctor-share links are
built from it) and add this app's origin to `ALLOWED_ORIGINS`.
