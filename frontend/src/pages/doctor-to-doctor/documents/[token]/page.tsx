import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, useNavigate, useLocation, Link } from "react-router-dom"
import Swal from "sweetalert2"
import {
  FileText,
  Image as ImageIcon,
  Loader2,
  AlertCircle,
  Download,
  Printer,
  Shield,
  Eye,
  Calendar,
  Stethoscope,
  ArrowLeft,
  Pencil,
  Settings,
  History,
  LogOut,
  Upload,
  X,
} from "lucide-react"
import {
  downloadDoctorToDoctorZip, getDoctorToDoctorDocument, updateDoctorToDoctorDocument,
  uploadDoctorToDoctorFile, deleteDoctorToDoctorFile,
} from "@/lib/api-client"
import { FormSettingsModal } from "@/components/dashboard/patient-document-pages"
import { ChangeHistoryModal } from "@/components/dashboard/change-history-modal"
import { usePublicDocumentLiveUpdates } from "@/hooks/use-public-document-live-updates"
import { saveBlobAsFile } from "@/lib/utils"
import { useAuthStore } from "@/stores/auth-store"
import { PageLoader } from "@/components/ui/spinner"
import type { FieldConfig, PatientDocumentFileRead, PatientDocumentPublicRead } from "@/lib/api-types"
import { YesNoBoxes, yesNoLabel } from "@/components/ui/yes-no"

const SECTION_ORDER_FALLBACK = 999

// Value keys that live at the top level of the document (not in
// document.fields) -- always shown in the "Patient Information" block.
const PATIENT_META_KEYS = new Set(["patient_name", "patient_email", "patient_phone", "visit_date"])

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong."
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i]
}

function formatDate(dateString: string | null | undefined) {
  if (!dateString) return "N/A"
  const date = new Date(dateString)
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
}

function isImageFile(file: PatientDocumentFileRead) {
  return file.file_type === "image" || !!file.file_name?.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)
}

function isPdfFile(file: PatientDocumentFileRead) {
  return file.file_type === "pdf" || !!file.file_name?.match(/\.pdf$/i)
}

// One editable field, matching the input layout the patient sees on their
// own self-fill link -- but live (not disabled), since a doctor who signed
// in through this link can now change these values, same as the document's
// owner can from their own dashboard.
function EditableField({
  field, value, editing, onChange,
}: {
  field: FieldConfig
  value: unknown
  editing: boolean
  onChange: (value: unknown) => void
}) {
  const displayValue = field.type === "checkbox" ? yesNoLabel(value) : (value as string) || "—"

  if (!editing) {
    return (
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">{field.label}</label>
        <div className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50 text-gray-700 min-h-[46px] whitespace-pre-wrap flex items-center">
          {displayValue}
        </div>
      </div>
    )
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{field.label}</label>
      {field.type === "checkbox" ? (
        <YesNoBoxes value={value} onChange={onChange} size="w-5 h-5" />
      ) : field.type === "textarea" ? (
        <textarea
          value={(value as string) || ""}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 outline-none resize-none"
        />
      ) : field.type === "select" ? (
        <select
          value={(value as string) || ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 outline-none"
        >
          <option value="">—</option>
          {(field.options || []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={field.type === "date" ? "date" : "text"}
          value={(value as string) || ""}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 outline-none"
        />
      )}
    </div>
  )
}

function PatientInfoField({
  label, type = "text", value, editing, onChange,
}: {
  label: string
  type?: string
  value: string
  editing: boolean
  onChange: (value: string) => void
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      {editing ? (
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 outline-none"
        />
      ) : (
        <div className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50 text-gray-700 min-h-[46px] flex items-center">
          {value || "—"}
        </div>
      )}
    </div>
  )
}

export default function DoctorToDoctorSharePage() {
  const params = useParams()
  const token = params?.token as string
  const navigate = useNavigate()
  const location = useLocation()

  const hydrated = useAuthStore((s) => s.hydrated)
  const accessToken = useAuthStore((s) => s.accessToken)
  const logout = useAuthStore((s) => s.logout)
  const userId = useAuthStore((s) => s.user?.id)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const [document, setDocument] = useState<PatientDocumentPublicRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadErrorStatus, setLoadErrorStatus] = useState<number | null>(null)
  const [previewFile, setPreviewFile] = useState<PatientDocumentFileRead | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [values, setValues] = useState<Record<string, unknown>>({})
  // Which value keys THIS doctor has actually typed into during the current
  // edit session. Save only sends these -- with several doctors possibly
  // editing the same shared document at once, sending back every field
  // (including ones this doctor never touched, just loaded at edit-start)
  // would silently overwrite whatever another doctor saved to those fields
  // in the meantime. It also lets a live update fill in fields this doctor
  // hasn't touched without disturbing what they're mid-typing.
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const [showFormSettings, setShowFormSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  // Not signed in -- send them to sign in first, then straight back here.
  useEffect(() => {
    if (!hydrated) return
    if (!accessToken) {
      navigate(`/signin?redirect=${encodeURIComponent(location.pathname)}`, { replace: true })
    }
  }, [hydrated, accessToken, navigate, location.pathname])

  const loadValuesFromDocument = useCallback((doc: PatientDocumentPublicRead) => {
    setValues({ ...doc.values, visit_date: doc.visit_date ? doc.visit_date.split("T")[0] : "" })
  }, [])

  const handleValueChange = (key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    setDirtyKeys((prev) => (prev.has(key) ? prev : new Set(prev).add(key)))
  }

  useEffect(() => {
    if (!hydrated || !accessToken || !token) return
    setLoading(true)
    setLoadError(null)
    setLoadErrorStatus(null)
    getDoctorToDoctorDocument(accessToken, token)
      .then((data) => {
        setDocument(data)
        loadValuesFromDocument(data)
      })
      .catch((error) => {
        setLoadErrorStatus(error?.status ?? null)
        setLoadError(
          error?.status === 404
            ? "This shared link is no longer available."
            : error?.status === 403
              ? "This link is for doctor or staff accounts only."
              : error?.message || "Failed to load document."
        )
      })
      .finally(() => setLoading(false))
  }, [hydrated, accessToken, token, loadValuesFromDocument])

  // Silent counterpart used for the live-update refetch below -- no loading
  // spinner. Always pulls the latest document (fields, files, change
  // history) so live updates show up even while this doctor is mid-edit --
  // it just never overwrites a value this doctor has actually typed into
  // this session (tracked in dirtyKeys), so another doctor's concurrent save
  // becomes visible without clobbering what's being typed here.
  const refreshDocument = useCallback(() => {
    if (!accessToken || !token) return
    getDoctorToDoctorDocument(accessToken, token)
      .then((data) => {
        setDocument(data)
        const fresh: Record<string, unknown> = { ...data.values, visit_date: data.visit_date ? data.visit_date.split("T")[0] : "" }
        setValues((prev) => {
          if (!editing) return fresh
          const merged = { ...prev }
          for (const key of Object.keys(fresh)) {
            if (!dirtyKeys.has(key)) merged[key] = fresh[key]
          }
          return merged
        })
      })
      .catch(() => {})
  }, [accessToken, token, editing, dirtyKeys])

  // Instant: updates the moment any doctor (including this one, from another
  // tab) changes the document, no reload needed.
  usePublicDocumentLiveUpdates(token ? `/doctor-to-doctor/documents/${token}/ws` : null, refreshDocument)

  const handleDownloadZip = async () => {
    if (!token || !accessToken) return
    setDownloading(true)
    try {
      const blob = await downloadDoctorToDoctorZip(accessToken, token)
      const isPdf = blob.type === "application/pdf"
      await saveBlobAsFile(blob, `${document?.patient_name || "patient"}${isPdf ? "_form.pdf" : "_documents.zip"}`)
    } catch {
      // ignore -- user can just click again
    } finally {
      setDownloading(false)
    }
  }

  const handleFileUpload = async (files: File[]) => {
    if (!accessToken || !token) return
    setUploading(true)
    try {
      for (const file of files) await uploadDoctorToDoctorFile(accessToken, token, file)
    } catch (error) {
      Swal.fire({ icon: "error", title: "Upload failed", text: (error as Error).message })
    } finally {
      setUploading(false)
      refreshDocument()
    }
  }

  const handleDeleteFile = async (fileId: string) => {
    if (!accessToken || !token) return
    const confirmed = await Swal.fire({ icon: "warning", title: "Remove this file?", showCancelButton: true, confirmButtonText: "Remove", confirmButtonColor: "#dc2626" })
    if (!confirmed.isConfirmed) return
    try {
      await deleteDoctorToDoctorFile(accessToken, token, fileId)
      refreshDocument()
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't remove", text: (error as Error).message })
    }
  }

  const handleStartEdit = () => {
    if (document) loadValuesFromDocument(document)
    setDirtyKeys(new Set())
    setEditing(true)
  }

  const handleCancelEdit = () => {
    if (document) loadValuesFromDocument(document)
    setDirtyKeys(new Set())
    setEditing(false)
  }

  const handleSave = async () => {
    if (!document || !accessToken || !token) return
    if (dirtyKeys.size === 0) {
      // Nothing this doctor actually touched -- just close edit mode rather
      // than sending an empty no-op PATCH.
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      const customFields: Record<string, unknown> = {}
      const payload: Record<string, unknown> = {}
      let touchedCustom = false

      for (const key of dirtyKeys) {
        if (PATIENT_META_KEYS.has(key)) {
          // patient_name is a required column (empty string is fine, null
          // is not) -- only email/phone/visit_date fall back to null when
          // cleared.
          payload[key] = key === "patient_name" ? values[key] : values[key] || null
          continue
        }
        const field = document.fields.find((f) => f.key === key)
        if (!field) continue
        if (field.core) {
          payload[key] = values[key]
        } else {
          customFields[key] = values[key]
          touchedCustom = true
        }
      }
      if (touchedCustom) payload.custom_fields = customFields

      const updated = await updateDoctorToDoctorDocument(accessToken, token, payload)
      setDocument(updated)
      loadValuesFromDocument(updated)
      setDirtyKeys(new Set())
      setEditing(false)
      Swal.fire({ icon: "success", title: "Saved", timer: 1000, showConfirmButton: false })
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't save", text: errMsg(error) })
    } finally {
      setSaving(false)
    }
  }

  const handleSignOut = async () => {
    await logout()
    navigate(`/signin?redirect=${encodeURIComponent(location.pathname)}`, { replace: true })
  }

  if (!hydrated || !accessToken) {
    return <PageLoader fullscreen />
  }

  if (loading) {
    return (
      <div className="flex flex-col py-16">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto" />
            <p className="mt-4 text-sm text-gray-600">Loading shared document...</p>
          </div>
        </div>
      </div>
    )
  }

  if (loadError || !document) {
    return (
      <div className="flex flex-col py-16">
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-gray-200 p-8 max-w-md w-full text-center">
            <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-8 h-8 text-red-500" />
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">Document Unavailable</h1>
            <p className="text-sm text-gray-600 mb-6">{loadError || "This document could not be found."}</p>
            {loadErrorStatus === 403 && (
              <button
                type="button"
                onClick={() => void handleSignOut()}
                className="mb-3 inline-flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50"
              >
                <LogOut className="w-4 h-4" /> Sign in with a different account
              </button>
            )}
            <Link to="/" className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700">
              <ArrowLeft className="w-4 h-4" />
              Go to Home
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const printFieldValue = (field: FieldConfig): string => {
    const v = document.values?.[field.key]
    if (field.type === "checkbox") return yesNoLabel(v)
    return (v as string) || "—"
  }

  const printSections: [string, FieldConfig[]][] = (() => {
    const sections: Record<string, FieldConfig[]> = {}
    for (const field of document.fields || []) {
      const section = field.section || "Details"
      if (!sections[section]) sections[section] = []
      sections[section].push(field)
    }
    return Object.entries(sections).sort(
      (a, b) => (a[1][0]?.order ?? SECTION_ORDER_FALLBACK) - (b[1][0]?.order ?? SECTION_ORDER_FALLBACK)
    )
  })()

  const groupedFields: Record<string, FieldConfig[]> = {}
  for (const field of document.fields || []) {
    const section = field.section || "Details"
    if (!groupedFields[section]) groupedFields[section] = []
    groupedFields[section].push(field)
  }
  const sortedGroupedFields = Object.entries(groupedFields).sort(
    (a, b) => (a[1][0]?.order ?? SECTION_ORDER_FALLBACK) - (b[1][0]?.order ?? SECTION_ORDER_FALLBACK)
  )

  return (
    <div>
      <style>{`
        .print-sheet { display: none; }
        @media print {
          .screen-only { display: none !important; }
          .print-sheet { display: block; }
          @page { size: A4; margin: 16mm; }
          body { background: white; }
        }
        .print-sheet { font-family: 'Segoe UI', system-ui, sans-serif; color: #111827; max-width: 800px; margin: 0 auto; padding: 24px; }
        .print-sheet .print-header { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #1d4ed8; padding-bottom: 16px; margin-bottom: 24px; }
        .print-sheet .print-header img { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; }
        .print-sheet .print-title { font-size: 20px; font-weight: 700; margin: 0; }
        .print-sheet .print-sub { font-size: 13px; color: #6b7280; margin: 2px 0 0; }
        .print-sheet .patient-meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; font-size: 13px; }
        .print-sheet .patient-meta div span { display: block; color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
        .print-sheet .section { break-inside: avoid; margin-bottom: 18px; }
        .print-sheet .section h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: #1d4ed8; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; margin: 0 0 8px; }
        .print-sheet .field-row { display: grid; grid-template-columns: 160px 1fr; gap: 8px; padding: 4px 0; font-size: 13px; }
        .print-sheet .field-row .label { color: #6b7280; }
        .print-sheet .field-row .value { white-space: pre-wrap; }
        .print-sheet .print-footer { margin-top: 32px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 8px; }
      `}</style>

      <div className="print-sheet">
        <div className="print-header">
          {document.logo_url && <img src={document.logo_url} alt="Clinic logo" />}
          <div>
            <p className="print-title">Patient Clinical Document</p>
            <p className="print-sub">
              {document.doctor_name ? `Dr. ${document.doctor_name}` : "Doctor"} · Printed {new Date().toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="patient-meta">
          <div>
            <span>Full Name</span>
            {document.patient_name || "—"}
          </div>
          <div>
            <span>Email</span>
            {document.patient_email || "—"}
          </div>
          <div>
            <span>Phone</span>
            {document.patient_phone || "—"}
          </div>
        </div>

        {printSections.map(([section, fields]) => (
          <div className="section" key={section}>
            <h3>{section}</h3>
            {fields.map((field) => (
              <div className="field-row" key={field.key}>
                <div className="label">{field.label}</div>
                <div className="value">{printFieldValue(field)}</div>
              </div>
            ))}
          </div>
        ))}

        {document.files && document.files.length > 0 && (
          <div className="section">
            <h3>Documents</h3>
            {document.files.map((file) => (
              <div className="field-row" key={file.id}>
                <div className="label">File</div>
                <div className="value">{file.file_name}</div>
              </div>
            ))}
          </div>
        )}

        <div className="print-footer">Generated by Documents.</div>
      </div>

      <div className="screen-only">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-start gap-4">
            {document.logo_url ? (
              <img src={document.logo_url} alt="Clinic Logo" className="w-14 h-14 rounded-xl border border-gray-200 object-cover shrink-0" />
            ) : (
              <div className="flex w-14 h-14 items-center justify-center rounded-xl border border-gray-200 bg-gray-50 shrink-0">
                <FileText className="w-6 h-6 text-gray-400" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-semibold text-gray-900">Shared Patient Document</h1>
              <p className="text-sm text-gray-600 mt-1">{document.patient_name || "Patient"}</p>

              <div className="flex flex-wrap items-center gap-4 mt-3">
                <div className="flex items-center gap-2">
                  <Stethoscope className="w-4 h-4 text-gray-400" />
                  <p className="text-xs text-gray-500">Shared by Dr. {document.doctor_name || "Doctor"}</p>
                </div>
                {document.visit_date && (
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <p className="text-xs text-gray-500">Visit: {formatDate(document.visit_date)}</p>
                  </div>
                )}
              </div>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowHistory(true)}
                title="View change history"
                className="p-2.5 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50"
              >
                <History className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setShowFormSettings(true)}
                title="Edit form settings"
                className="p-2.5 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50"
              >
                <Settings className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleDownloadZip}
                disabled={downloading}
                title="Download form PDF + attached files (zip)"
                className="p-2.5 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-60"
              >
                {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                title="Print this form"
                className="p-2.5 rounded-xl border border-gray-200 text-gray-600 hover:bg-gray-50"
              >
                <Printer className="w-4 h-4" />
              </button>
              {!editing && (
                <button
                  type="button"
                  onClick={handleStartEdit}
                  title="Edit this form"
                  className="p-2.5 rounded-xl border border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100"
                >
                  <Pencil className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 flex items-start gap-3">
          <Shield className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <p className="text-sm text-blue-800">
            This link is for healthcare professionals only. Every change you make here is recorded with your
            name so other doctors with this link can see who changed what.
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-900">Patient Information</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <PatientInfoField label="Full Name" value={(values.patient_name as string) || ""} editing={editing} onChange={(v) => handleValueChange("patient_name", v)} />
            <PatientInfoField label="Email" type="email" value={(values.patient_email as string) || ""} editing={editing} onChange={(v) => handleValueChange("patient_email", v)} />
            <PatientInfoField label="Phone" type="tel" value={(values.patient_phone as string) || ""} editing={editing} onChange={(v) => handleValueChange("patient_phone", v)} />
          </div>
        </div>

        {sortedGroupedFields.map(([section, fields]) => (
          <div key={section} className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900">{section}</h2>
            {fields.map((field) => (
              <EditableField
                key={field.key}
                field={field}
                value={values[field.key]}
                editing={editing}
                onChange={(v) => handleValueChange(field.key, v)}
              />
            ))}
          </div>
        ))}

        {editing && (
          <div className="flex gap-2">
            <button onClick={handleSave} disabled={saving} className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-60">
              {saving ? "Saving..." : "Save Changes"}
            </button>
            <button onClick={handleCancelEdit} disabled={saving} className="flex-1 py-2.5 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
          </div>
        )}

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">Attached Files ({document.files?.length || 0})</h2>
            {editing && (
              <>
                <input ref={fileInputRef} type="file" accept="*/*" multiple className="hidden" onChange={(e) => { const files = Array.from(e.target.files || []); if (files.length) void handleFileUpload(files); e.target.value = "" }} />
                <button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60">
                  {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                  {uploading ? "Uploading…" : "Add Files"}
                </button>
              </>
            )}
          </div>

          {!document.files || document.files.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No files have been attached yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {document.files.map((file) => (
                <div key={file.id} className="flex items-center gap-4 rounded-xl border border-gray-200 px-4 py-3 hover:bg-gray-50 transition-colors">
                  <div className="shrink-0">
                    {isImageFile(file) ? (
                      <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center">
                        <ImageIcon className="w-6 h-6 text-blue-600" />
                      </div>
                    ) : isPdfFile(file) ? (
                      <div className="w-12 h-12 bg-red-50 rounded-lg flex items-center justify-center">
                        <FileText className="w-6 h-6 text-red-600" />
                      </div>
                    ) : (
                      <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
                        <FileText className="w-6 h-6 text-gray-500" />
                      </div>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{file.file_name}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatFileSize(file.file_size)} · Added {formatDate(file.created_at)}
                    </p>
                  </div>

                  {file.file_url && (
                    <div className="flex items-center gap-2 shrink-0">
                      {isImageFile(file) && (
                        <button onClick={() => setPreviewFile(file)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-100">
                          <Eye className="w-3.5 h-3.5" />
                          Preview
                        </button>
                      )}
                      <a href={file.file_url} target="_blank" rel="noreferrer" download={file.file_name} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-xs font-medium text-white hover:bg-blue-700">
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </a>
                    </div>
                  )}
                  {editing && userId && file.uploaded_by === userId && (
                    <button onClick={() => void handleDeleteFile(file.id)} title="Remove file" className="p-1.5 rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600 shrink-0">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="text-center">
          <p className="text-xs text-gray-400">This secure link is intended for healthcare professionals only.</p>
        </div>
      </div>
      </div>

      {previewFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setPreviewFile(null)}>
          <div className="relative bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="text-sm font-medium text-gray-900 truncate">{previewFile.file_name}</h3>
              <button onClick={() => setPreviewFile(null)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-80px)]">
              {previewFile.file_url && <img src={previewFile.file_url} alt={previewFile.file_name} className="w-full h-auto rounded-lg" />}
            </div>
          </div>
        </div>
      )}

      {showHistory && <ChangeHistoryModal changes={document.changes} onClose={() => setShowHistory(false)} />}

      <FormSettingsModal
        isOpen={showFormSettings}
        onClose={() => setShowFormSettings(false)}
        documentId={null}
        shareToken={token}
        onSaved={refreshDocument}
      />
    </div>
  )
}
