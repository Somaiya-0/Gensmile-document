import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ChevronRight, Loader2, Share2 } from "lucide-react"

import { PatientDocumentsAccessGuard } from "@/components/dashboard/patient-document-pages"
import { useAutoRefresh } from "@/hooks/use-auto-refresh"
import { listSharedWithMe } from "@/lib/api-client"
import type { SharedWithMeDocument } from "@/lib/api-types"
import { useAuthStore } from "@/stores/auth-store"

// Documents other doctors have shared with this doctor -- every
// doctor-to-doctor link they've opened that's still shared with them.
function SharedDocumentsPage() {
  const token = useAuthStore((s) => s.accessToken) ?? ""
  const navigate = useNavigate()
  const [docs, setDocs] = useState<SharedWithMeDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setDocs(await listSharedWithMe(token))
      setError(null)
    } catch (e) {
      setError((e as Error).message || "Couldn't load shared documents.")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void load() }, [load])
  useAutoRefresh(load, { intervalMs: 60_000 })

  return (
    <div className="w-full min-w-0">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-gray-900">Shared Documents</h1>
        <p className="text-sm text-gray-500">Documents other doctors have shared with you</p>
      </div>
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : error ? (
          <p className="p-10 text-center text-sm text-red-600">{error}</p>
        ) : docs.length === 0 ? (
          <div className="p-10 text-center">
            <Share2 className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            <p className="text-sm text-gray-500">No documents shared with you yet</p>
            <p className="mt-1 text-xs text-gray-400">When a doctor sends you a share link, it shows up here once you open it.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                  <th className="px-5 py-3">Patient</th>
                  <th className="px-5 py-3">Shared by</th>
                  <th className="px-5 py-3">Updated</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {docs.map((doc) => (
                  <tr key={doc.share_token} onClick={() => navigate(`/doctor-to-doctor/documents/${doc.share_token}`)} className="cursor-pointer transition-colors hover:bg-gray-50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-600">
                          {doc.patient_name?.[0]?.toUpperCase()}
                        </div>
                        <span className="font-medium text-gray-900">{doc.patient_name || "—"}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-700">Dr. {doc.owner_name}</td>
                    <td className="px-5 py-3 text-gray-500">{new Date(doc.updated_at).toLocaleDateString()}</td>
                    <td className="px-5 py-3 text-right"><ChevronRight className="inline-block h-4 w-4 text-gray-300" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default function SharedDocumentsRoute() {
  return (
    <PatientDocumentsAccessGuard>
      <SharedDocumentsPage />
    </PatientDocumentsAccessGuard>
  )
}
