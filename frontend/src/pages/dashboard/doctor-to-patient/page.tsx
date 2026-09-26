import { PatientDocumentsAccessGuard, PatientDocumentsPage } from "@/components/dashboard/patient-document-pages"
import { AdminDoctorToPatientPage } from "@/components/dashboard/admin-documents-pages"
import { isAdmin } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

export default function DoctorToPatientRoute() {
  const role = useAuthStore((state) => state.user?.role)

  if (isAdmin(role)) return <AdminDoctorToPatientPage />

  return (
    <PatientDocumentsAccessGuard>
      <PatientDocumentsPage mode="doctor-to-patient" />
    </PatientDocumentsAccessGuard>
  )
}
