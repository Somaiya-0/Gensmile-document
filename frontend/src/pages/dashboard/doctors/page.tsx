import { AdminAccessGuard, DoctorsPage } from "@/components/dashboard/admin-doctors-pages"

export default function DoctorsRoute() {
  return (
    <AdminAccessGuard>
      <DoctorsPage />
    </AdminAccessGuard>
  )
}
