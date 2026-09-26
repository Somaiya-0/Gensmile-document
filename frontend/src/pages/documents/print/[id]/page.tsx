import { useParams, Navigate } from "react-router-dom"
import { PageLoader } from "@/components/ui/spinner"
import { PatientDocumentPrintPage } from "@/components/dashboard/patient-document-pages"
import { useAuthStore } from "@/stores/auth-store"

// Deliberately a top-level route (not nested under DocumentsLayout) so the print
// view renders full-page without the top bar — the
// print stylesheet in PatientDocumentPrintPage only controls @page output,
// not the on-screen layout, so avoiding the layout entirely is simpler than
// fighting it with print CSS.
export default function DocumentPrintRoute() {
  const params = useParams()
  const id = params?.id as string
  const token = useAuthStore((state) => state.accessToken)
  const hydrated = useAuthStore((state) => state.hydrated)

  if (!hydrated) return <PageLoader fullscreen />
  if (!token) return <Navigate to="/signin" replace />

  return <PatientDocumentPrintPage documentId={id} />
}
