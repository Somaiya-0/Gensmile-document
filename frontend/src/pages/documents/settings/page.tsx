import { PatientDocumentSettingsPage, PatientDocumentsAccessGuard } from "@/components/dashboard/patient-document-pages"

export default function DocumentSettingsRoute() {
  return (
    <PatientDocumentsAccessGuard>
      <PatientDocumentSettingsPage />
    </PatientDocumentsAccessGuard>
  )
}
