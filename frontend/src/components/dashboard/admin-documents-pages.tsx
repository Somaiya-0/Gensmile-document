import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowRight, FileText, Loader2, Search, Send, Stethoscope, UserRound } from "lucide-react"

import { listAllDocuments, listDoctors } from "@/lib/api-client"
import type { AdminDocument } from "@/lib/api-types"
import { useAuthStore } from "@/stores/auth-store"

function useToken(): string {
  const token = useAuthStore((state) => state.accessToken)
  return token ?? ""
}

function docStatus(doc: AdminDocument): { label: string; color: string } {
  if (doc.patient_submitted_at) return { label: "Submitted", color: "bg-green-50 text-green-700 border-green-200" }
  if (doc.fill_enabled) return { label: "Sent to Patient", color: "bg-blue-50 text-blue-700 border-blue-200" }
  if (doc.is_shared) return { label: "Sent to Doctor", color: "bg-amber-50 text-amber-700 border-amber-200" }
  return { label: "Draft", color: "bg-gray-50 text-gray-500 border-gray-200" }
}

function useAllDocuments() {
  const token = useToken()
  const [documents, setDocuments] = useState<AdminDocument[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setDocuments(await listAllDocuments(token))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  return { documents, loading }
}

function AdminDocumentTable({
  documents,
  loading,
  emptyText,
  searchTerm,
}: {
  documents: AdminDocument[]
  loading: boolean
  emptyText: string
  searchTerm: string
}) {
  const filtered = documents.filter(
    (d) =>
      d.patient_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.doctor_name?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      {loading ? (
        <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
      ) : filtered.length === 0 ? (
        <div className="p-10 text-center">
          <FileText className="mx-auto mb-2 h-8 w-8 text-gray-300" />
          <p className="text-sm text-gray-500">{emptyText}</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
              <th className="px-5 py-3">Patient</th>
              <th className="px-5 py-3">Doctor</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map((doc) => {
              const status = docStatus(doc)
              return (
                <tr key={doc.id}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      {doc.logo_url ? (
                        <img src={doc.logo_url} alt="" className="h-9 w-9 shrink-0 rounded-lg border border-gray-200 object-cover" />
                      ) : (
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-600">
                          {doc.patient_name?.[0]?.toUpperCase()}
                        </div>
                      )}
                      <span className="font-medium text-gray-900">{doc.patient_name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-600">{doc.doctor_name}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${status.color}`}>
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />{status.label}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500">{new Date(doc.updated_at).toLocaleDateString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        </div>
      )}
    </div>
  )
}

function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search patient or doctor..."
        className="w-full rounded-full border border-gray-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-blue-500 sm:w-72"
      />
    </div>
  )
}

export function AdminDoctorToDoctorPage() {
  const { documents, loading } = useAllDocuments()
  const [searchTerm, setSearchTerm] = useState("")
  const shared = documents.filter((d) => d.is_shared)

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Doctor to Doctor</h1>
          <p className="text-sm text-gray-500">{shared.length} document{shared.length === 1 ? "" : "s"} shared across all doctors</p>
        </div>
        <SearchBox value={searchTerm} onChange={setSearchTerm} />
      </div>
      <AdminDocumentTable documents={shared} loading={loading} emptyText="No documents have been shared with other doctors yet." searchTerm={searchTerm} />
    </div>
  )
}

export function AdminDoctorToPatientPage() {
  const { documents, loading } = useAllDocuments()
  const [searchTerm, setSearchTerm] = useState("")
  const sent = documents.filter((d) => d.fill_enabled)

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Doctor to Patient</h1>
          <p className="text-sm text-gray-500">{sent.length} document{sent.length === 1 ? "" : "s"} sent to patients across all doctors</p>
        </div>
        <SearchBox value={searchTerm} onChange={setSearchTerm} />
      </div>
      <AdminDocumentTable documents={sent} loading={loading} emptyText="No documents have been sent to patients yet." searchTerm={searchTerm} />
    </div>
  )
}

function StatCard({ label, value, icon: Icon, tint }: { label: string; value: number; icon: typeof Send; tint: string }) {
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

function QuickLink({ to, title, description, icon: Icon }: { to: string; title: string; description: string; icon: typeof Send }) {
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

export function AdminOverviewPage() {
  const token = useToken()
  const { documents, loading } = useAllDocuments()
  const [doctorCount, setDoctorCount] = useState<number | null>(null)

  useEffect(() => {
    listDoctors(token).then((docs) => setDoctorCount(docs.length)).catch(() => setDoctorCount(null))
  }, [token])

  const sharedCount = documents.filter((d) => d.is_shared).length
  const patientCount = documents.filter((d) => d.fill_enabled).length
  const submittedCount = documents.filter((d) => d.patient_submitted_at).length

  const recent = [...documents]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 8)

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-gray-900">Overview</h1>
        <p className="text-sm text-gray-500">A snapshot of documents across every doctor.</p>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
        <StatCard label="Doctors" value={doctorCount ?? 0} icon={UserRound} tint="bg-purple-50 text-purple-600" />
        <StatCard label="Total Documents" value={documents.length} icon={FileText} tint="bg-gray-100 text-gray-600" />
        <StatCard label="Shared with Doctors" value={sharedCount} icon={Stethoscope} tint="bg-amber-50 text-amber-600" />
        <StatCard label="Sent to Patients" value={patientCount} icon={Send} tint="bg-blue-50 text-blue-600" />
        <StatCard label="Submitted" value={submittedCount} icon={UserRound} tint="bg-green-50 text-green-600" />
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <QuickLink to="/dashboard/doctor-to-doctor" title="Doctor to Doctor" description="Every document shared between doctors." icon={Stethoscope} />
        <QuickLink to="/dashboard/doctor-to-patient" title="Doctor to Patient" description="Every document sent to a patient." icon={Send} />
        <QuickLink to="/dashboard/doctors" title="Doctors" description="Manage doctor accounts and credentials." icon={UserRound} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-100 px-5 py-4">
          <h3 className="text-sm font-semibold text-gray-900">Recent activity</h3>
        </div>
        {loading ? (
          <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : recent.length === 0 ? (
          <div className="p-10 text-center">
            <FileText className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            <p className="text-sm text-gray-500">No documents yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {recent.map((doc) => {
              const status = docStatus(doc)
              return (
                <div key={doc.id} className="flex items-center gap-3 px-5 py-3">
                  {doc.logo_url ? (
                    <img src={doc.logo_url} alt="" className="h-9 w-9 shrink-0 rounded-lg border border-gray-200 object-cover" />
                  ) : (
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-600">
                      {doc.patient_name?.[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-gray-900">{doc.patient_name}</p>
                    <p className="text-[11px] text-gray-500">{doc.doctor_name} · {new Date(doc.updated_at).toLocaleDateString()}</p>
                  </div>
                  <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${status.color}`}>
                    <span className="h-1.5 w-1.5 rounded-full bg-current" />{status.label}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
