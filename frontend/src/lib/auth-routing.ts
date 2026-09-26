// Default landing spot after sign-in for a doctor/staff account.
export const DOCUMENTS_PATH = "/dashboard/overview"
// Default landing spot after sign-in for an admin account.
export const ADMIN_PATH = "/dashboard/doctors"

// Doctors and their staff use the documents workflow (Doctor-to-Doctor /
// Doctor-to-Patient). Admins manage doctor accounts. Any other account
// (patient, affiliate) can sign in to the main GenSmile app, but not this one.
export function canUseDocuments(role: string | undefined): boolean {
  const normalized = role?.toLowerCase()
  return normalized === "doctor" || normalized === "staff"
}

export function isAdmin(role: string | undefined): boolean {
  return role?.toLowerCase() === "admin"
}

// Whether this account is allowed into the dashboard shell at all.
export function canUseDashboard(role: string | undefined): boolean {
  return canUseDocuments(role) || isAdmin(role)
}

export const NOT_A_DOCTOR_MESSAGE = "This app is only for doctors, their staff, and admins."

export function destinationForRole(role: string | undefined): string {
  return isAdmin(role) ? ADMIN_PATH : DOCUMENTS_PATH
}
