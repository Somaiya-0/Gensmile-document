import { PatientDocumentsAccessGuard } from "@/components/dashboard/patient-document-pages"
import { OverviewPage } from "@/components/dashboard/overview-page"
import { AdminOverviewPage } from "@/components/dashboard/admin-documents-pages"
import { isAdmin } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

export default function OverviewRoute() {
  const role = useAuthStore((state) => state.user?.role)

  if (isAdmin(role)) return <AdminOverviewPage />

  return (
    <PatientDocumentsAccessGuard>
      <OverviewPage />
    </PatientDocumentsAccessGuard>
  )
}
