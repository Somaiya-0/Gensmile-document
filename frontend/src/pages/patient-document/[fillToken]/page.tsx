import { useCallback, useEffect, useRef, useState, type FormEvent } from "react"
import { useParams } from "react-router-dom"
import { CheckCircle2, Download, FileText, Loader2, AlertCircle, Printer, Upload, X } from "lucide-react"
import { deletePatientFillFile, downloadPatientFillZip, getPatientFillForm, submitPatientFillForm, uploadPatientFillFile } from "@/lib/api-client"
import { usePublicDocumentLiveUpdates } from "@/hooks/use-public-document-live-updates"
import { useAutoRefresh } from "@/hooks/use-auto-refresh"
import { saveBlobAsFile } from "@/lib/utils"
import type { PatientDocumentFileRead, PatientFillFormRead } from "@/lib/api-types"
import { YesNoBoxes, yesNoLabel } from "@/components/ui/yes-no"

const SECTION_ORDER_FALLBACK = 999

export default function PatientFillFormPage() {
  const params = useParams()
  const fillToken = params?.fillToken as string

  const [form, setForm] = useState<PatientFillFormRead | null>(null)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [contact, setContact] = useState({ patient_name: "", patient_email: "", patient_phone: "" })
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [files, setFiles] = useState<PatientDocumentFileRead[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!fillToken) return
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fillToken])

  const load = async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const data = await getPatientFillForm(fillToken)
      setForm(data)
      setValues(data.values || {})
      setContact({
        patient_name: data.patient_name || "",
        patient_email: (data.values?.patient_email as string) || data.patient_email || "",
        patient_phone: (data.values?.patient_phone as string) || data.patient_phone || "",
      })
      setSubmitted(!!data.submitted)
      setFiles(data.files || [])
    } catch (error: unknown) {
      const err = error as { status?: number; message?: string }
      setLoadError(err.status === 404 ? "This link is invalid or no longer active." : err.message || "Failed to load the form.")
    } finally {
      setLoading(false)
    }
  }

  // Live updates while this form is open: the doctor's edits and files show
  // up right away, except in fields the patient has already changed here --
  // what they typed is never overwritten. Also catches a submit from another
  // tab and the doctor turning the link off.
  const touchedRef = useRef(new Set<string>())
  const refreshFillStatus = useCallback(() => {
    getPatientFillForm(fillToken)
      .then((data) => {
        if (data.submitted && !submitted) {
          setForm(data)
          setSubmitted(true)
          return
        }
        const keepTouched = <T extends Record<string, unknown>>(prev: T, fresh: T): T => {
          const merged = { ...fresh }
          for (const key of touchedRef.current) if (key in prev) (merged as Record<string, unknown>)[key] = prev[key]
          return merged
        }
        setValues((prev) => keepTouched(prev, data.values || {}))
        setContact((prev) => keepTouched(prev, {
          patient_name: data.patient_name || "",
          patient_email: (data.values?.patient_email as string) || data.patient_email || "",
          patient_phone: (data.values?.patient_phone as string) || data.patient_phone || "",
        }))
        setFiles(data.files || [])
      })
      .catch((error: unknown) => {
        const err = error as { status?: number }
        if (err.status === 404 && !submitted) {
          setLoadError("This link is no longer active.")
          setForm(null)
        }
      })
  }, [fillToken, submitted])

  usePublicDocumentLiveUpdates(fillToken ? `/patient-document/${fillToken}/ws` : null, refreshFillStatus)
  // Safety net if the live connection is down: re-check periodically and on tab focus.
  useAutoRefresh(refreshFillStatus, { intervalMs: 30_000 })

  const handleChange = (key: string, value: unknown) => {
    touchedRef.current.add(key)
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  const handleFileSelect = async (selected: FileList | null) => {
    const fileArray = Array.from(selected ?? [])
    if (fileArray.length === 0) return
    setUploadError(null)
    setUploading(true)
    try {
      for (const file of fileArray) {
        const uploaded = await uploadPatientFillFile(fillToken, file)
        setFiles((prev) => [...prev.filter((f) => f.id !== uploaded.id), uploaded])
      }
    } catch (error: unknown) {
      const err = error as { message?: string }
      setUploadError(err.message || "Failed to upload file.")
    } finally {
      setUploading(false)
    }
  }

  const handleRemoveFile = async (fileId: string) => {
    try {
      await deletePatientFillFile(fillToken, fileId)
      setFiles((prev) => prev.filter((f) => f.id !== fileId))
    } catch {
      // leave the file in the list -- the delete just didn't take
    }
  }

  const handleContactChange = (key: keyof typeof contact, value: string) => {
    touchedRef.current.add(key)
    setContact((prev) => ({ ...prev, [key]: value }))
  }

  const handleDownloadZip = async () => {
    setDownloading(true)
    try {
      // No attached files -> the backend sends just the form PDF, not a zip.
      const blob = await downloadPatientFillZip(fillToken)
      const isPdf = blob.type === "application/pdf"
      await saveBlobAsFile(blob, `${contact.patient_name || "patient"}${isPdf ? "_form.pdf" : "_documents.zip"}`)
    } catch {
      // ignore -- user can just click again
    } finally {
      setDownloading(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setLoadError(null)
    try {
      const data = await submitPatientFillForm(fillToken, {
        patient_name: contact.patient_name,
        patient_email: contact.patient_email,
        patient_phone: contact.patient_phone,
        values,
      })
      setForm(data)
      setSubmitted(true)
      window.scrollTo({ top: 0, behavior: "smooth" })
    } catch (error: unknown) {
      const err = error as { message?: string }
      setLoadError(err.message || "Failed to submit the form.")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
          <p className="mt-3 text-sm text-gray-600">Loading form...</p>
        </div>
      </div>
    )
  }

  if (loadError && !form) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-2xl border border-gray-200 p-8 max-w-md w-full text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-lg font-semibold text-gray-900 mb-2">Unavailable</h1>
          <p className="text-sm text-gray-600">{loadError}</p>
        </div>
      </div>
    )
  }

  if (!form) return null

  const sections: Record<string, PatientFillFormRead["fields"]> = {}
  for (const field of form.fields || []) {
    const section = field.section || "Details"
    if (!sections[section]) sections[section] = []
    sections[section].push(field)
  }
  const sortedSections = Object.entries(sections).sort(
    (a, b) => (a[1][0]?.order ?? SECTION_ORDER_FALLBACK) - (b[1][0]?.order ?? SECTION_ORDER_FALLBACK)
  )

  const printFieldValue = (field: PatientFillFormRead["fields"][number]): string => {
    const v = values[field.key]
    if (field.type === "checkbox") return yesNoLabel(v)
    return (v as string) || "—"
  }

  return (
    <div className="min-h-screen bg-gray-50 py-6 px-4">
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
          {form.logo_url && <img src={form.logo_url} alt="Clinic logo" />}
          <div>
            <p className="print-title">Patient Intake Form</p>
            <p className="print-sub">{form.doctor_name ? `Dr. ${form.doctor_name}` : "Your Doctor"} · Printed {new Date().toLocaleDateString()}</p>
          </div>
        </div>

        <div className="patient-meta">
          <div>
            <span>Full Name</span>
            {contact.patient_name || "—"}
          </div>
          <div>
            <span>Email</span>
            {contact.patient_email || "—"}
          </div>
          <div>
            <span>Phone</span>
            {contact.patient_phone || "—"}
          </div>
        </div>

        {sortedSections.map(([section, fields]) => (
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

        {files.length > 0 && (
          <div className="section">
            <h3>Documents</h3>
            {files.map((file) => (
              <div className="field-row" key={file.id}>
                <div className="label">File</div>
                <div className="value">{file.file_name}</div>
              </div>
            ))}
          </div>
        )}

        <div className="print-footer">Generated by Patient Documents.</div>
      </div>

      <div className="screen-only max-w-lg mx-auto space-y-5">
        <div className="bg-white rounded-2xl border border-gray-200 p-5 flex items-center gap-3">
          {form.logo_url ? (
            <img src={form.logo_url} alt="Clinic logo" className="w-14 h-14 rounded-xl object-cover border border-gray-200" />
          ) : (
            <div className="w-14 h-14 rounded-xl bg-blue-50 flex items-center justify-center">
              <span className="text-xl font-semibold text-blue-600">{(form.doctor_name || "D")[0]?.toUpperCase()}</span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-gray-900">Patient Intake Form</h1>
            <p className="text-sm text-gray-600">{form.doctor_name ? `Dr. ${form.doctor_name}` : "Your Doctor"}</p>
          </div>
          <div className="shrink-0 flex items-center gap-2">
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
          </div>
        </div>

        {submitted ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center space-y-3">
            <CheckCircle2 className="w-12 h-12 text-green-600 mx-auto" />
            <h2 className="text-base font-semibold text-gray-900">Thanks, you're all set</h2>
            <p className="text-sm text-gray-600">
              Your responses have been sent to {form.doctor_name ? `Dr. ${form.doctor_name}` : "your doctor"}. You can close this page.
            </p>
            <button type="button" onClick={() => setSubmitted(false)} className="text-sm text-blue-600 font-medium hover:text-blue-700">
              Edit my answers
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
              <h2 className="text-sm font-semibold text-gray-900">Your Information</h2>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Full Name<span className="text-red-500"> *</span>
                </label>
                <input
                  type="text"
                  value={contact.patient_name}
                  onChange={(e) => handleContactChange("patient_name", e.target.value)}
                  required
                  placeholder="Enter your full name"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
                <input
                  type="email"
                  value={contact.patient_email}
                  onChange={(e) => handleContactChange("patient_email", e.target.value)}
                  placeholder="your@email.com"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Phone</label>
                <input
                  type="tel"
                  value={contact.patient_phone}
                  onChange={(e) => handleContactChange("patient_phone", e.target.value)}
                  placeholder="(555) 123-4567"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                />
              </div>
            </div>

            {sortedSections.map(([section, fields]) => (
              <div key={section} className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
                <h2 className="text-sm font-semibold text-gray-900">{section}</h2>
                {fields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      {field.label}
                      {field.required && <span className="text-red-500"> *</span>}
                    </label>

                    {field.type === "checkbox" ? (
                      <YesNoBoxes value={values[field.key]} onChange={(v) => handleChange(field.key, v)} required={field.required} size="w-5 h-5" />
                    ) : field.type === "textarea" ? (
                      <textarea
                        value={(values[field.key] as string) || ""}
                        onChange={(e) => handleChange(field.key, e.target.value)}
                        required={field.required}
                        rows={3}
                        placeholder={`Enter ${field.label.toLowerCase()}...`}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none resize-none"
                      />
                    ) : field.type === "date" ? (
                      <input
                        type="date"
                        value={(values[field.key] as string) || ""}
                        onChange={(e) => handleChange(field.key, e.target.value)}
                        required={field.required}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                      />
                    ) : field.type === "select" ? (
                      <select
                        value={(values[field.key] as string) || ""}
                        onChange={(e) => handleChange(field.key, e.target.value)}
                        required={field.required}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                      >
                        <option value="">Select...</option>
                        {(field.options || []).map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={(values[field.key] as string) || ""}
                        onChange={(e) => handleChange(field.key, e.target.value)}
                        required={field.required}
                        placeholder={`Enter ${field.label.toLowerCase()}...`}
                        className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                      />
                    )}
                  </div>
                ))}
              </div>
            ))}

            <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-3">
              <h2 className="text-sm font-semibold text-gray-900">Documents ({files.length})</h2>
              <p className="text-xs text-gray-500 -mt-2">
                Upload any relevant files (ID, insurance card, photos, etc.). Any file format works except zip.
              </p>
              {files.length > 0 && (
                <div className="space-y-1.5">
                  {files.map((file) => (
                    <div key={file.id} className="flex items-center gap-2 rounded-lg border border-gray-100 px-3 py-2">
                      <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                      <span className="text-xs text-gray-700 truncate flex-1">{file.file_name}</span>
                      <span className="text-[10px] text-gray-400 shrink-0">{(file.file_size / 1024).toFixed(1)} KB</span>
                      {/* Patients can only remove their own uploads, not the doctor's. */}
                      {file.uploaded_by_patient && (
                        <button
                          type="button"
                          onClick={() => handleRemoveFile(file.id)}
                          className="p-0.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-600 shrink-0"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {uploadError && <p className="text-xs text-red-600">{uploadError}</p>}
              <input
                ref={fileInputRef}
                type="file"
                accept="*/*"
                multiple
                className="hidden"
                onChange={(e) => { handleFileSelect(e.target.files); e.target.value = "" }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2.5 border border-dashed border-gray-300 rounded-lg text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-60"
              >
                {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                {uploading ? "Uploading…" : "Upload Documents"}
              </button>
            </div>

            {loadError && <p className="text-sm text-red-600 text-center bg-red-50 rounded-xl p-3">{loadError}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Submitting...
                </span>
              ) : (
                "Submit"
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
