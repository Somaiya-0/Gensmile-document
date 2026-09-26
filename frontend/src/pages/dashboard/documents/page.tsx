import { PatientDocumentsAccessGuard, PatientDocumentsPage } from "@/components/dashboard/patient-document-pages"
import { AdminDoctorToDoctorPage } from "@/components/dashboard/admin-documents-pages"
import { isAdmin } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

// The combined Document page: create/share form on the left, Doctor to
// Doctor / Doctor to Patient lists on the right. Admins get the read-only
// cross-doctor view instead, same as the dedicated Doctor to Doctor page --
// creating a document is a per-doctor action, not an admin one.
export default function DashboardDocumentsRoute() {
  const role = useAuthStore((state) => state.user?.role)

  if (isAdmin(role)) return <AdminDoctorToDoctorPage />

  return (
    <PatientDocumentsAccessGuard>
      <PatientDocumentsPage mode="all" />
    </PatientDocumentsAccessGuard>
  )
}
