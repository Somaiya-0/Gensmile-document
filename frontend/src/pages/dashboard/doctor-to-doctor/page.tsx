import { PatientDocumentsAccessGuard, PatientDocumentsPage } from "@/components/dashboard/patient-document-pages"
import { AdminDoctorToDoctorPage } from "@/components/dashboard/admin-documents-pages"
import { isAdmin } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

export default function DoctorToDoctorRoute() {
  const role = useAuthStore((state) => state.user?.role)

  if (isAdmin(role)) return <AdminDoctorToDoctorPage />

  return (
    <PatientDocumentsAccessGuard>
      <PatientDocumentsPage mode="doctor-to-doctor" />
    </PatientDocumentsAccessGuard>
  )
}
