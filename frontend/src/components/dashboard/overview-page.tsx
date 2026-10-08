import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowRight, FileText, Loader2, Send, Stethoscope, Users } from "lucide-react"

import { getDocStatus } from "@/components/dashboard/patient-document-pages"
import { listPatientDocuments } from "@/lib/api-client"
import type { PatientDocumentRead } from "@/lib/api-types"
import { useAuthStore } from "@/stores/auth-store"
import { useAutoRefresh } from "@/hooks/use-auto-refresh"
import { useDocumentsLiveUpdates } from "@/hooks/use-documents-live-updates"

function useToken(): string {
  const token = useAuthStore((state) => state.accessToken)
  return token ?? ""
}

function StatCard({ label, value, icon: Icon, tint }: { label: string; value: number; icon: typeof Users; tint: string }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tint}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
        <p className="text-xs text-gray-500">{label}</p>
      </div>
    </div>
  )
}

function QuickLink({ to, title, description, icon: Icon }: { to: string; title: string; description: string; icon: typeof Users }) {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(to)}
      className="flex w-full items-center gap-4 rounded-2xl border border-gray-200 bg-white p-5 text-left shadow-sm transition-colors hover:bg-gray-50"
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-gray-900">{title}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <ArrowRight className="h-4 w-4 shrink-0 text-gray-300" />
    </button>
  )
}

export function OverviewPage() {
  const token = useToken()
  const navigate = useNavigate()
  const [documents, setDocuments] = useState<PatientDocumentRead[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setDocuments(await listPatientDocuments(token))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])
  useAutoRefresh(load, { intervalMs: 30_000 })
  useDocumentsLiveUpdates("document_updated", load)

  const sharedCount = documents.filter((d) => d.is_shared).length
  const patientCount = documents.filter((d) => d.fill_enabled).length
  const submittedCount = documents.filter((d) => d.patient_submitted_at).length

  const byNewest = [...documents].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
  // Recent activity: the newest 5 per workflow, with "See more" for the rest.
  const recentSections = [
    { title: "Doctor to Doctor", path: "doctor-to-doctor", docs: byNewest.filter((d) => d.is_shared), empty: "No documents shared with doctors yet" },
    { title: "Doctor to Patient", path: "doctor-to-patient", docs: byNewest.filter((d) => d.fill_enabled), empty: "No documents sent to patients yet" },
  ]

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-gray-900">Overview</h1>
        <p className="text-sm text-gray-500">A snapshot of your documents across both workflows.</p>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total Documents" value={documents.length} icon={FileText} tint="bg-gray-100 text-gray-600" />
        <StatCard label="Shared with Doctors" value={sharedCount} icon={Stethoscope} tint="bg-amber-50 text-amber-600" />
        <StatCard label="Sent to Patients" value={patientCount} icon={Send} tint="bg-blue-50 text-blue-600" />
        <StatCard label="Submitted" value={submittedCount} icon={Users} tint="bg-green-50 text-green-600" />
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <QuickLink
          to="/dashboard/doctor-to-doctor"
          title="Doctor to Doctor"
          description="Share a patient document with another doctor -- they sign in to view and edit it."
          icon={Stethoscope}
        />
        <QuickLink
          to="/dashboard/doctor-to-patient"
          title="Doctor to Patient"
          description="Send a patient a link to fill in or review their own document."
          icon={Send}
        />
      </div>

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-100 px-5 py-4">
          <h3 className="text-sm font-semibold text-gray-900">Recent activity</h3>
        </div>
        {loading ? (
          <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : documents.length === 0 ? (
          <div className="p-10 text-center">
            <FileText className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            <p className="text-sm text-gray-500">No documents yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {recentSections.map((section) => (
              <div key={section.path} className="py-2">
                <p className="px-5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{section.title}</p>
                {section.docs.length === 0 ? (
                  <p className="px-5 pb-2 text-xs text-gray-400">{section.empty}</p>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {section.docs.slice(0, 5).map((doc) => {
                      const status = getDocStatus(doc)
                      return (
                        <div key={doc.id} className="flex cursor-pointer items-center gap-3 px-5 py-3 transition-colors hover:bg-gray-50" onClick={() => navigate(`/dashboard/${section.path}?doc=${doc.id}`)}>
                          {doc.logo_url ? (
                            <img src={doc.logo_url} alt="" className="h-9 w-9 shrink-0 rounded-lg border border-gray-200 object-cover" />
                          ) : (
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-600">
                              {doc.patient_name?.[0]?.toUpperCase()}
                            </div>
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900">{doc.patient_name}</p>
                            <p className="text-[11px] text-gray-500">{new Date(doc.updated_at).toLocaleDateString()}</p>
                          </div>
                          <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${status.color}`}>
                            <span className="h-1.5 w-1.5 rounded-full bg-current" />{status.label}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )}
                {section.docs.length > 5 && (
                  <Link to={`/dashboard/${section.path}`} className="block px-5 pb-1 pt-2 text-xs font-medium text-blue-600 hover:text-blue-700">
                    See more ({section.docs.length}) →
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
