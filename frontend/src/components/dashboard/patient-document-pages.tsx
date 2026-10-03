import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react"
import { Link, useSearchParams } from "react-router-dom"
import Swal from "sweetalert2"
import {
  Plus, Search, Save, Share2, Upload, FileText, Image as ImageIcon, X,
  Loader2, Check, Printer, Pencil, Trash2,
  Settings, ChevronRight, FileArchive, FileSpreadsheet, ChevronDown,
  Download, GripVertical, Users, Stethoscope, MoreVertical, LogOut, History,
} from "lucide-react"

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import {
  listPatientDocuments, createPatientDocument, getPatientDocument, getPatientDocumentChanges,
  updatePatientDocument, deletePatientDocument, uploadPatientDocumentLogo,
  uploadPatientDocumentAttachment, deletePatientDocumentFile, toggleDocumentSharing,
  toggleFillLink, getDocumentFormConfig, updateDocumentFormConfig,
  getFormConfig, updateFormConfig, getPatients,
  downloadPatientDocumentZip,
  getDoctorToDoctorFormConfig, updateDoctorToDoctorFormConfig,
} from "@/lib/api-client"
import type {
  DoctorPatient, FieldConfig, PatientDocumentChangeLog, PatientDocumentCreate, PatientDocumentFileRead, PatientDocumentRead,
} from "@/lib/api-types"
import { useAuthStore } from "@/stores/auth-store"
import { useAutoRefresh } from "@/hooks/use-auto-refresh"
import { useDocumentsLiveUpdates } from "@/hooks/use-documents-live-updates"
import { saveBlobAsFile } from "@/lib/utils"
import { ChangeHistoryModal } from "@/components/dashboard/change-history-modal"
import { YesNoBoxes, yesNoLabel } from "@/components/ui/yes-no"

// "select" (Dropdown) is intentionally left out -- no longer offered as a
// type for new fields. FIELD_TYPE_LABELS below still needs a "select" entry
// so existing dropdown fields (created before this change) still show a
// proper label instead of falling through to raw "select" text.
const FIELD_TYPES: FieldConfig["type"][] = ["text", "textarea", "checkbox", "date"]

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong."
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function getDocStatus(doc: PatientDocumentRead): { label: string; color: string } {
  if (doc.patient_submitted_at) return { label: "Submitted", color: "bg-green-50 text-green-700 border-green-200" }
  if (doc.fill_enabled && doc.fill_url) return { label: "Sent to Patient", color: "bg-blue-50 text-blue-700 border-blue-200" }
  if (doc.is_shared) return { label: "Sent to Doctor", color: "bg-amber-50 text-amber-700 border-amber-200" }
  return { label: "Draft", color: "bg-gray-50 text-gray-500 border-gray-200" }
}

// What a background refresh compares to decide whether a document really
// changed. Not the whole object: logo/file URLs are presigned and differ on
// every fetch. updated_at alone isn't enough either -- a patient uploading a
// file through the fill link adds a file row without touching the document.
function docSignature(doc: PatientDocumentRead): string {
  return [doc.updated_at, doc.patient_submitted_at, doc.fill_enabled, doc.is_shared, doc.files?.map((f) => f.id).join(",")].join("|")
}

// Staff whose doctor turned off their Documents permission can still sign
// in, but get this instead of the page (the API enforces it as well).
export function PatientDocumentsAccessGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((state) => state.user)
  const staffPermissions = useAuthStore((state) => state.staffPermissions)
  const logout = useAuthStore((state) => state.logout)
  const isStaff = (user?.role as string)?.toUpperCase() === "STAFF"

  if (isStaff && staffPermissions?.patient_documents === false) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-gray-200 bg-white p-8 text-center shadow-sm">
        <FileText className="mx-auto mb-3 h-8 w-8 text-gray-300" />
        <h1 className="text-base font-semibold text-gray-900">No access to Documents</h1>
        <p className="mt-1 text-sm text-gray-500">Ask your doctor to turn on the Documents permission for your account.</p>
        <button
          type="button"
          onClick={() => { void logout() }}
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>
    )
  }
  return <>{children}</>
}

type NewFieldDraft = { label: string; section: string; type: FieldConfig["type"] }

const FIELD_TYPE_LABELS: Record<FieldConfig["type"], string> = {
  text: "Short Text",
  textarea: "Long Text",
  checkbox: "Yes/No",
  date: "Date",
  select: "Dropdown",
}

// Shared by both field-builder implementations (the modal and the standalone
// page version) -- shows what the field will actually look like, and which
// section it lands in, before the doctor commits to adding it.
// Asked before closing a form that has unsaved input or a file still uploading.
// Closing doesn't cancel an upload -- it finishes in the background.
async function confirmDiscard({ uploading = false, unsaved = true } = {}): Promise<boolean> {
  const r = await Swal.fire({
    icon: "warning",
    title: "Do you want to close?",
    text: [
      uploading && "A file is still uploading.",
      unsaved && "Your unsaved changes will be lost.",
    ].filter(Boolean).join(" "),
    showCancelButton: true,
    confirmButtonText: uploading ? "Continue upload in background" : "Discard",
    cancelButtonText: "Keep open",
    // Red only when closing actually throws something away.
    confirmButtonColor: unsaved ? "#dc2626" : "#2563eb",
  })
  return r.isConfirmed
}

function AddFieldModal({
  isOpen,
  onClose,
  onAdd,
  existingSections,
}: {
  isOpen: boolean
  onClose: () => void
  onAdd: (draft: NewFieldDraft) => void
  existingSections: string[]
}) {
  const [label, setLabel] = useState("")
  const [section, setSection] = useState("")
  const [customSection, setCustomSection] = useState(false)
  const [type, setType] = useState<FieldConfig["type"]>("text")

  useEffect(() => {
    if (!isOpen) return
    setLabel("")
    setType("text")
    setCustomSection(false)
    setSection(existingSections[0] || "Other")
  }, [isOpen, existingSections])

  if (!isOpen) return null

  const resolvedSection = section.trim() || "Other"
  const isNewSection = customSection || !existingSections.includes(resolvedSection)

  function handleSubmit() {
    if (!label.trim()) return
    onAdd({ label: label.trim(), section: resolvedSection, type })
  }

  return (
    <div className="modal-in fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white max-h-[90dvh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="overflow-y-auto overscroll-none p-5 space-y-4">
        <h3 className="text-base font-semibold text-gray-900">Add New Field</h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Field Label</label>
            <input
              autoFocus
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Allergies"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Section</label>
            {!customSection ? (
              <div className="flex gap-2">
                <select
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm"
                >
                  {existingSections.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <button
                  type="button"
                  onClick={() => { setCustomSection(true); setSection("") }}
                  className="shrink-0 text-xs font-medium text-blue-600 hover:underline"
                >
                  + New section
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                  placeholder="New section name"
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm"
                />
                <button
                  type="button"
                  onClick={() => { setCustomSection(false); setSection(existingSections[0] || "Other") }}
                  className="shrink-0 text-xs font-medium text-gray-500 hover:underline"
                >
                  Use existing
                </button>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Field Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as FieldConfig["type"])}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
            >
              {FIELD_TYPES.map((t) => <option key={t} value={t}>{FIELD_TYPE_LABELS[t]}</option>)}
            </select>
          </div>
        </div>

        {/* Live preview of where/how this field will appear */}
        <div className="rounded-xl border border-dashed border-blue-200 bg-blue-50/60 p-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-blue-700">
            {isNewSection ? `Preview — new section "${resolvedSection}"` : `Preview — added to "${resolvedSection}"`}
          </p>
          <div className="rounded-lg bg-white border border-gray-200 p-3 pointer-events-none">
            <label className="block text-sm font-medium text-gray-700 mb-1">{label || "Field label"}</label>
            {type === "textarea" ? (
              <textarea disabled rows={2} placeholder="Answer goes here" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50" />
            ) : type === "checkbox" ? (
              <YesNoBoxes value={null} disabled />
            ) : type === "date" ? (
              <input disabled type="date" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50" />
            ) : type === "select" ? (
              <select disabled className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50"><option>Choose an option</option></select>
            ) : (
              <input disabled placeholder="Answer goes here" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50" />
            )}
          </div>
          <p className="text-[11px] text-blue-700">
            Appears at the end of the {isNewSection ? "new" : ""} "{resolvedSection}" section on this form.
          </p>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!label.trim()}
            className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            Add Field
          </button>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
        </div>
        </div>
      </div>
    </div>
  )
}

function useToken(): string {
  const token = useAuthStore((state) => state.accessToken)
  return token ?? ""
}

function getFileIcon(fileType: string | undefined, fileName: string | undefined) {
  if (fileType === "image" || fileName?.match(/\.(jpg|jpeg|png|gif|webp|bmp|svg)$/i)) {
    return <ImageIcon className="w-4 h-4 text-blue-500" />
  } else if (fileType === "pdf" || fileName?.match(/\.pdf$/i)) {
    return <FileText className="w-4 h-4 text-red-500" />
  } else if (fileType === "doc" || fileName?.match(/\.(doc|docx)$/i)) {
    return <FileText className="w-4 h-4 text-blue-700" />
  } else if (fileType === "excel" || fileName?.match(/\.(xls|xlsx|csv)$/i)) {
    return <FileSpreadsheet className="w-4 h-4 text-green-600" />
  } else if (fileType === "archive" || fileName?.match(/\.(zip|rar|7z|tar|gz)$/i)) {
    return <FileArchive className="w-4 h-4 text-yellow-600" />
  }
  return <FileText className="w-4 h-4 text-gray-500" />
}

async function downloadAllAsZip(documentId: string, token: string, _files: PatientDocumentFileRead[] | undefined, patientName: string | undefined) {
  // The backend sends just the form PDF (no zip) when the document has no
  // attached files, else a zip of the attachments plus that PDF -- see
  // build_patient_document_zip. The blob's type reflects whichever it sent.
  Swal.fire({
    title: "Preparing download...",
    html: "Packaging files & form PDF...",
    allowOutsideClick: false,
    didOpen: () => { Swal.showLoading() },
  })

  try {
    // Built server-side (not via client-side JSZip fetching each presigned
    // S3 URL) -- the browser can't fetch() a presigned S3 URL cross-origin
    // unless the bucket's CORS policy allows it, which silently produced
    // empty zips before.
    const blob = await downloadPatientDocumentZip(token, documentId)
    const isPdf = blob.type === "application/pdf"
    await saveBlobAsFile(blob, `${patientName || "patient"}${isPdf ? "_form.pdf" : "_documents.zip"}`)

    Swal.close()
    Swal.fire({ icon: "success", title: "Download started!", timer: 1000, showConfirmButton: false })
  } catch (error) {
    Swal.close()
    Swal.fire({ icon: "error", title: "Download failed", text: errMsg(error) })
  }
}

// ─── Share Link Modal ───────────────────────────────────────────────────────

// ─── Form Settings Modal (per-document or doctor default) ─────────────────

export function FormSettingsModal({
  isOpen, onClose, documentId, onSaved, isDefault = false, shareToken = null,
}: {
  isOpen: boolean
  onClose: () => void
  documentId: string | null
  onSaved?: () => void
  isDefault?: boolean
  // Set when this modal is opened from the doctor-to-doctor share page
  // instead of the owner's own dashboard: reads/writes go through the
  // share-token-scoped routes (any signed-in doctor, not just the owner),
  // and never touch the owner's doctor-wide default template -- a visiting
  // doctor has no default template of their own to update.
  shareToken?: string | null
}) {
  const token = useToken()
  const [fields, setFields] = useState<FieldConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [expandedSection, setExpandedSection] = useState<string | null>(null)
  const [showAddField, setShowAddField] = useState(false)

  const fetchFields = useCallback(async () => {
    const data = shareToken
      ? await getDoctorToDoctorFormConfig(token, shareToken)
      : isDefault
        ? await getFormConfig(token)
        : await getDocumentFormConfig(token, documentId as string)
    return [...data.fields].sort((a, b) => a.order - b.order)
  }, [documentId, isDefault, shareToken, token])

  const loadFields = useCallback(async () => {
    setLoading(true)
    try {
      const sorted = await fetchFields()
      setFields(sorted)
      if (sorted.length > 0) setExpandedSection(sorted[0].section || "Overview")
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't load fields", text: errMsg(error) })
    } finally {
      setLoading(false)
    }
  }, [fetchFields])

  useEffect(() => {
    if (isOpen) loadFields()
  }, [isOpen, loadFields])

  // Every mutation below saves immediately -- there's no separate "Save
  // Changes" step, and each one re-fetches the current field list right
  // before applying itself rather than mutating the copy this modal loaded
  // when it first opened. With several doctors able to have this modal open
  // on the same shared document at once, mutating (and then replacing the
  // whole array from) a snapshot that's been sitting in memory since open
  // would silently discard whatever another doctor already saved in the
  // meantime -- fetching fresh right before each write shrinks that race
  // window to just this one request instead of "however long the modal's
  // been open". Silent on success (matching normal autosave UX); only
  // failures interrupt with a dialog, and on failure the local view is
  // rolled back to what the server actually has so the UI never claims a
  // change stuck that didn't.
  const applyAndPersist = async (mutate: (current: FieldConfig[]) => FieldConfig[]) => {
    setSaving(true)
    try {
      const fresh = await fetchFields()
      const ordered = mutate(fresh).map((f, i) => ({ ...f, order: i + 1 }))
      setFields(ordered)
      if (shareToken) {
        await updateDoctorToDoctorFormConfig(token, shareToken, { fields: ordered })
      } else if (isDefault) {
        await updateFormConfig(token, { fields: ordered })
      } else {
        await updateDocumentFormConfig(token, documentId as string, { fields: ordered })
        // Also update the doctor's default template so new (blank) patient
        // documents pick up the same field structure going forward.
        await updateFormConfig(token, { fields: ordered })
      }
      onSaved?.()
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't save", text: errMsg(error) })
      loadFields()
    } finally {
      setSaving(false)
    }
  }

  // Used for checkboxes -- a discrete toggle, fine to save right away.
  const updateField = (key: string, patch: Partial<FieldConfig>) => {
    void applyAndPersist((current) => current.map((f) => (f.key === key ? { ...f, ...patch } : f)))
  }

  // Used for the label text input -- saving on every keystroke would fire a
  // request per character, so this only updates local state; the input's
  // onBlur below is what actually persists it (via updateField, reading the
  // latest-typed label out of local `fields`).
  const updateFieldLocal = (key: string, patch: Partial<FieldConfig>) => {
    setFields((prev) => prev.map((f) => (f.key === key ? { ...f, ...patch } : f)))
  }

  const deleteField = async (field: FieldConfig) => {
    const confirmed = await Swal.fire({
      icon: "warning",
      title: `Delete "${field.label}"?`,
      text: "This removes it from the form. Already-entered values for it on existing documents are kept, just no longer shown.",
      showCancelButton: true,
      confirmButtonText: "Delete",
      confirmButtonColor: "#dc2626",
    })
    if (!confirmed.isConfirmed) return
    void applyAndPersist((current) => current.filter((f) => f.key !== field.key))
  }

  const addField = (draft: NewFieldDraft) => {
    const slug = draft.label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40)
    const key = `custom_${slug || "field"}_${Date.now().toString(36)}`
    void applyAndPersist((current) => [...current, {
      key, label: draft.label, type: draft.type, section: draft.section,
      order: (current[current.length - 1]?.order || 0) + 1, active: true, required: false,
      patient_editable: false, core: false,
    }])
    setShowAddField(false)
  }

  // Identifies the field by key rather than by its position in the possibly
  //-stale local list -- moved by key against whatever the fresh fetch
  // returns, so a concurrent add/delete by someone else doesn't shift the
  // meaning of "index N" out from under this move.
  const moveField = (key: string, direction: number) => {
    void applyAndPersist((current) => {
      const index = current.findIndex((f) => f.key === key)
      const target = index + direction
      if (index === -1 || target < 0 || target >= current.length) return current
      const next = [...current]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  if (!isOpen) return null

  const sections: Record<string, FieldConfig[]> = {}
  fields.forEach((field) => {
    const section = field.section || "Overview"
    if (!sections[section]) sections[section] = []
    sections[section].push(field)
  })

  return (
    <>
    <div className="modal-in fixed inset-0 z-[65] flex items-center justify-center bg-black/50 p-4">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90dvh] overflow-hidden flex flex-col">
        <div className="shrink-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900">{isDefault ? "Form Settings" : "Edit Form"}</h3>
            <p className="text-xs text-gray-500">Customize what fields appear on your form</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100"><X className="w-4 h-4" /></button>
        </div>
        <div className="overflow-y-auto overscroll-none px-6 py-4 space-y-4">
          {loading ? (
            <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
          ) : (
            <>
              <div className="flex justify-between items-center">
                <button onClick={() => setShowAddField(true)} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-medium hover:bg-blue-700">
                  <Plus className="w-4 h-4" /> Add New Field
                </button>
                {saving && (
                  <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving…
                  </span>
                )}
              </div>
              <div className="space-y-3">
                {Object.entries(sections).map(([sectionName, sectionFields]) => (
                  <div key={sectionName} className="border border-gray-200 rounded-xl overflow-hidden">
                    <button onClick={() => setExpandedSection(expandedSection === sectionName ? null : sectionName)} className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100">
                      <span className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                        {sectionName}
                        <span className="ml-2 text-gray-400 font-normal normal-case">({sectionFields.filter((f) => f.active).length} visible)</span>
                      </span>
                      <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expandedSection === sectionName ? "rotate-180" : ""}`} />
                    </button>
                    {expandedSection === sectionName && (
                      <div className="divide-y divide-gray-100">
                        {sectionFields.map((field) => {
                          const globalIndex = fields.findIndex((f) => f.key === field.key)
                          return (
                            <div key={field.key} className={`px-4 py-3 ${!field.active ? "opacity-40 bg-gray-50" : ""}`}>
                              <div className="flex items-center gap-3">
                                <div className="flex flex-col gap-0.5 shrink-0">
                                  <button onClick={() => moveField(field.key, -1)} disabled={globalIndex === 0} className="text-gray-300 hover:text-gray-500 disabled:opacity-30"><ChevronDown className="w-3.5 h-3.5 rotate-180" /></button>
                                  <button onClick={() => moveField(field.key, 1)} disabled={globalIndex === fields.length - 1} className="text-gray-300 hover:text-gray-500 disabled:opacity-30"><ChevronDown className="w-3.5 h-3.5" /></button>
                                </div>
                                <input type="text" value={field.label} onChange={(e) => updateFieldLocal(field.key, { label: e.target.value })} onBlur={() => updateField(field.key, { label: field.label })} className="flex-1 px-3 py-1.5 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
                                <span className="text-[10px] font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-600 shrink-0">
                                  {field.type === "text" ? "Text" : field.type === "textarea" ? "Notes" : field.type === "checkbox" ? "Yes/No" : field.type === "date" ? "Date" : field.type}
                                </span>
                              </div>
                              <div className="flex items-center gap-4 mt-2 pl-6">
                                <label className="flex items-center gap-1.5 text-[11px] text-gray-600 cursor-pointer">
                                  <input type="checkbox" checked={field.active} onChange={(e) => updateField(field.key, { active: e.target.checked })} className="w-3.5 h-3.5 text-blue-600 rounded" />
                                  Show on form
                                </label>
                                <label className="flex items-center gap-1.5 text-[11px] text-gray-600 cursor-pointer">
                                  <input type="checkbox" checked={field.patient_editable} onChange={(e) => updateField(field.key, { patient_editable: e.target.checked })} className="w-3.5 h-3.5 text-blue-600 rounded" />
                                  Patient can fill
                                </label>
                                <button onClick={() => deleteField(field)} className="ml-auto text-[11px] text-red-500 hover:text-red-700 font-medium">
                                  Delete
                                </button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
    <AddFieldModal
      isOpen={showAddField}
      onClose={() => setShowAddField(false)}
      onAdd={addField}
      existingSections={Object.keys(sections)}
    />
    </>
  )
}

// ─── Document Detail Modal ──────────────────────────────────────────────────

type ClinicalFormData = Partial<PatientDocumentRead> & { patient_name?: string }

// Defined at module scope, not inside DocumentDetailModal -- a component
// redefined on every parent render gets a new identity each time, so React
// treats it as a different component type and remounts its subtree (the
// <input> inside it) on every keystroke, which drops focus mid-typing.
function FieldShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  )
}

// The edit form's values for a document -- also used as the modal's initial
// state, so it opens already filled in instead of rendering empty and then
// growing (which made the centered modal jump on open).
function docToFormData(document: PatientDocumentRead): ClinicalFormData {
  return {
    patient_name: document.patient_name || "",
    patient_email: document.patient_email || "",
    patient_phone: document.patient_phone || "",
    visit_date: document.visit_date ? document.visit_date.split("T")[0] : todayISO(),
    chief_concern: document.chief_concern || "",
    last_dds_visit: document.last_dds_visit || "",
    cbct_taken: document.cbct_taken ?? null,
    req_radiologist: document.req_radiologist || "",
    exam_salivary_ph: document.exam_salivary_ph || "",
    recommend_salivary_test: document.recommend_salivary_test ?? null,
    cbct_notes: document.cbct_notes || "",
    third_molar_ll: document.third_molar_ll || "",
    third_molar_lr: document.third_molar_lr || "",
    third_molar_ul: document.third_molar_ul || "",
    third_molar_ur: document.third_molar_ur || "",
    cavitations: document.cavitations || "",
    third_molar_recommendations: document.third_molar_recommendations || "",
    sinus_ul: document.sinus_ul || "",
    sinus_ur: document.sinus_ur || "",
    existing_rcts: document.existing_rcts || "",
    any_into_sinus: document.any_into_sinus ?? null,
    sinus_recommendations: document.sinus_recommendations || "",
    periodontal_condition: document.periodontal_condition || "",
    tx_recommendations: document.tx_recommendations || "",
    md_referral: document.md_referral ?? null,
    blood_test: document.blood_test ?? null,
    occlusion: document.occlusion || "",
    guidance: document.guidance || "",
    occlusion_recommendations: document.occlusion_recommendations || "",
  } as ClinicalFormData
}

function DocumentDetailModal({
  document, startInEditMode = false, onClose, onUpdate, onDelete, onDefaultFormConfigChanged,
}: {
  document: PatientDocumentRead
  startInEditMode?: boolean
  onClose: () => void
  onUpdate: (doc: PatientDocumentRead) => void
  onDelete: (documentId: string) => void
  // Editing a document's fields also updates the doctor's default template
  // (see FormSettingsModal.persist) -- lets the caller refresh its own
  // copy of that default so a blank "New patient document" form reflects it
  // without a full page reload.
  onDefaultFormConfigChanged?: () => void
}) {
  const token = useToken()
  const [editing, setEditing] = useState(startInEditMode)
  const [formData, setFormData] = useState<ClinicalFormData>(() => docToFormData(document))
  const [customFields, setCustomFields] = useState<Record<string, unknown>>(() => document.custom_fields || {})
  // Which field keys were actually edited this session (core -> formData,
  // custom -> customFields). Save sends only these -- this document may also
  // be open on a doctor-to-doctor share link right now, being edited by a
  // different doctor; sending the whole formData/customFields snapshot back
  // would silently overwrite whatever field(s) they just saved.
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const dirtyKeysRef = useRef(dirtyKeys)
  dirtyKeysRef.current = dirtyKeys
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [sharing, setSharing] = useState<"patient" | "doctor" | null>(null)
  const [shareCopied, setShareCopied] = useState<"patient" | "doctor" | null>(null)
  const [showFormSettings, setShowFormSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<PatientDocumentChangeLog[] | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const logoInputRef = useRef<HTMLInputElement>(null)
  const loadedDocIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!document) return
    // A live update (another doctor, the patient, another tab) can hand us a
    // newer copy while this doctor is mid-edit: take the new value for every
    // field they haven't touched, keep what they're typing in the rest.
    const merging = editing && loadedDocIdRef.current === document.id
    loadedDocIdRef.current = document.id
    const keep = <T extends Record<string, unknown>>(prev: T, fresh: T): T => {
      if (!merging) return fresh
      const merged = { ...fresh }
      for (const key of dirtyKeysRef.current) if (key in prev) (merged as Record<string, unknown>)[key] = prev[key]
      return merged
    }
    {
      setFormData((prev) => keep(prev as Record<string, unknown>, docToFormData(document) as Record<string, unknown>) as ClinicalFormData)
      setCustomFields((prev) => keep(prev, document.custom_fields || {}))
    }
  }, [document, editing])

  const handleSave = async () => {
    if (dirtyKeys.size === 0) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      const payload: Record<string, unknown> = {}
      const dirtyCustomFields: Record<string, unknown> = {}
      let touchedCustom = false
      for (const key of dirtyKeys) {
        if (key in formData) {
          payload[key] = (formData as Record<string, unknown>)[key]
        } else {
          dirtyCustomFields[key] = customFields[key]
          touchedCustom = true
        }
      }
      if (touchedCustom) payload.custom_fields = dirtyCustomFields

      const updated = await updatePatientDocument(token, document.id, payload)
      onUpdate(updated)
      setDirtyKeys(new Set())
      setEditing(false)
      Swal.fire({ icon: "success", title: "Saved", timer: 1000, showConfirmButton: false })
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't save", text: errMsg(error) })
    } finally {
      setSaving(false)
    }
  }

  const handleLogoUpload = async (file: File) => {
    setUploading(true)
    try {
      const result = await uploadPatientDocumentLogo(token, document.id, file)
      onUpdate({ ...document, logo_url: result.logo_url })
    } catch (error) {
      Swal.fire({ icon: "error", title: "Upload failed", text: errMsg(error) })
    } finally {
      setUploading(false)
    }
  }

  const handleFileUpload = async (files: File[]) => {
    if (files.length === 0) return
    setUploading(true)
    try {
      let updatedFiles = document.files
      for (const file of files) {
        const newFile = await uploadPatientDocumentAttachment(token, document.id, file)
        updatedFiles = [...updatedFiles, newFile]
        onUpdate({ ...document, files: updatedFiles })
      }
    } catch (error) {
      Swal.fire({ icon: "error", title: "Upload failed", text: errMsg(error) })
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteFile = async (fileId: string) => {
    try {
      await deletePatientDocumentFile(token, fileId)
      onUpdate({ ...document, files: document.files.filter((f) => f.id !== fileId) })
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't delete file", text: errMsg(error) })
    }
  }

  // Both audiences reuse the same document -- enabling is idempotent (the
  // token is created once, up front) so it's safe to call every time and
  // just copy whatever URL comes back, without ever showing the link itself.
  const handleShareTo = async (audience: "patient" | "doctor") => {
    setSharing(audience)
    try {
      let url: string | null | undefined
      if (audience === "patient") {
        const updated = document.fill_enabled ? document : await toggleFillLink(token, document.id, true)
        if (updated !== document) onUpdate(updated)
        url = updated.fill_url
      } else {
        const updated = document.is_shared ? document : await toggleDocumentSharing(token, document.id, true)
        if (updated !== document) onUpdate(updated)
        url = updated.share_url
      }
      if (!url) throw new Error("No share link available.")
      await navigator.clipboard.writeText(url)
      setShareCopied(audience)
      setTimeout(() => setShareCopied(null), 2000)
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't create share link", text: errMsg(error) })
    } finally {
      setSharing(null)
    }
  }

  const requestClose = async () => {
    const unsaved = editing && dirtyKeys.size > 0
    if ((uploading || unsaved) && !(await confirmDiscard({ uploading, unsaved }))) return
    onClose()
  }

  const markDirty = (key: string) => setDirtyKeys((prev) => (prev.has(key) ? prev : new Set(prev).add(key)))

  const handlePrint = () => window.open(`/documents/print/${document.id}`, "_blank")

  const fieldConfigs = document.form_config || []
  const groupedFields = fieldConfigs.filter((f) => f.active).reduce<Record<string, FieldConfig[]>>((acc, f) => {
    const section = f.section || "Overview"
    if (!acc[section]) acc[section] = []
    acc[section].push(f)
    return acc
  }, {})

  const displayBoxClass = "w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50 text-gray-900 min-h-[38px] flex items-center"
  const displayTextareaClass = "w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-gray-50 text-gray-900 min-h-[76px] whitespace-pre-wrap"

  const renderCoreField = (key: string, label: string, type = "text") => {
    const value = (formData as Record<string, unknown>)[key] as string | undefined || ""
    if (!editing) {
      return (
        <FieldShell label={label}>
          <div className={displayBoxClass}>{value || "—"}</div>
        </FieldShell>
      )
    }
    return (
      <FieldShell label={label}>
        <input
          type={type}
          value={value}
          onChange={(e) => { setFormData((p) => ({ ...p, [key]: e.target.value })); markDirty(key) }}
          className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none"
        />
      </FieldShell>
    )
  }

  const renderConfiguredField = (field: FieldConfig) => {
    const isCore = field.core
    const value = isCore ? (formData as Record<string, unknown>)[field.key] : customFields[field.key]
    const setValue = (v: unknown) => {
      if (isCore) setFormData((p) => ({ ...p, [field.key]: v }))
      else setCustomFields((p) => ({ ...p, [field.key]: v }))
      markDirty(field.key)
    }

    if (!editing) {
      let displayValue: string
      if (field.type === "checkbox") {
        displayValue = yesNoLabel(value)
      } else {
        displayValue = (value as string) || "—"
      }
      return (
        <FieldShell key={field.key} label={field.label}>
          <div className={field.type === "textarea" ? displayTextareaClass : displayBoxClass}>
            {displayValue}
          </div>
        </FieldShell>
      )
    }

    return (
      <FieldShell key={field.key} label={field.label}>
        {field.type === "checkbox" ? (
          <YesNoBoxes value={value} onChange={setValue} />
        ) : field.type === "textarea" ? (
          <textarea value={(value as string) || ""} onChange={(e) => setValue(e.target.value)} rows={3} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none resize-none" />
        ) : (
          <input type="text" value={(value as string) || ""} onChange={(e) => setValue(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
        )}
      </FieldShell>
    )
  }

  return (
    <div className="modal-in fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
      <div className="absolute inset-0" onClick={requestClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90dvh] overflow-hidden flex flex-col">
        <div className="shrink-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative group">
              {document.logo_url ? (
                <img src={document.logo_url} alt="Logo" className="w-12 h-12 rounded-lg object-cover border border-gray-200" />
              ) : (
                <div className="w-12 h-12 rounded-lg bg-gray-100 flex items-center justify-center border-2 border-dashed border-gray-300">
                  <FileText className="w-5 h-5 text-gray-400" />
                </div>
              )}
              <input ref={logoInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) handleLogoUpload(file); e.target.value = "" }} />
              <button onClick={() => logoInputRef.current?.click()} className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-lg text-white text-[9px] font-medium opacity-0 group-hover:opacity-100 transition-opacity">Change</button>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{document.patient_name}</h2>
              <p className="text-xs text-gray-500">{document.visit_date ? new Date(document.visit_date).toLocaleDateString() : "No date"}</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50" title="More options">
                  <MoreVertical className="w-4 h-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="z-[80] min-w-[200px] rounded-xl border-gray-200 p-1.5">
                {!editing && (
                  <DropdownMenuItem onClick={() => { setDirtyKeys(new Set()); setEditing(true) }} className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900">
                    <Pencil className="w-4 h-4 text-blue-600" /> Edit
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem
                  onClick={() => downloadAllAsZip(document.id, token, document.files, document.patient_name)}
                  className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900"
                >
                  <Download className="w-4 h-4 text-blue-600" /> Download ZIP
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setShowFormSettings(true)} className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900">
                  <Settings className="w-4 h-4 text-blue-600" /> Edit Form
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    setHistory(null)
                    setShowHistory(true)
                    getPatientDocumentChanges(token, document.id).then(setHistory).catch((error) => {
                      setShowHistory(false)
                      Swal.fire({ icon: "error", title: "Couldn't load history", text: errMsg(error) })
                    })
                  }}
                  className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900"
                >
                  <History className="w-4 h-4 text-blue-600" /> Change History
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handlePrint} className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900">
                  <Printer className="w-4 h-4 text-blue-600" /> Print
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  disabled={sharing !== null}
                  title="Share"
                  className={`p-2 rounded-lg border ${(document.is_shared || document.fill_enabled) ? "bg-green-50 border-green-200 text-green-600" : "border-gray-200 hover:bg-gray-50"} disabled:opacity-60`}
                >
                  {sharing ? <Loader2 className="w-4 h-4 animate-spin" /> : shareCopied ? <Check className="w-4 h-4" /> : <Share2 className="w-4 h-4" />}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="z-[80] min-w-[200px] rounded-xl border-gray-200 p-1.5">
                <DropdownMenuItem onClick={() => void handleShareTo("patient")} disabled={sharing !== null} className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900">
                  <Users className="w-4 h-4 text-blue-600" />
                  {sharing === "patient" ? "Copying…" : shareCopied === "patient" ? "Copied!" : "Share to Patient"}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => void handleShareTo("doctor")} disabled={sharing !== null} className="cursor-pointer gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-gray-900">
                  <Stethoscope className="w-4 h-4 text-blue-600" />
                  {sharing === "doctor" ? "Copying…" : shareCopied === "doctor" ? "Copied!" : "Share to Doctor"}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <button onClick={requestClose} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 shrink-0"><X className="w-4 h-4" /></button>
          </div>
        </div>

        <div className="overflow-y-auto overscroll-none px-6 py-4 space-y-4">
          <div className="border border-gray-200 rounded-xl p-4 bg-gray-50">
            <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Patient Information</h4>
            <div className="grid gap-3 sm:grid-cols-2">
              {renderCoreField("patient_name", "Patient Name")}
              {renderCoreField("visit_date", "Visit Date", "date")}
              {renderCoreField("patient_email", "Email", "email")}
              {renderCoreField("patient_phone", "Phone", "tel")}
            </div>
          </div>

          {Object.entries(groupedFields).map(([section, fields]) => (
            <div key={section} className="border border-gray-200 rounded-xl p-4">
              <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">{section}</h4>
              <div className="space-y-3">
                {fields.map((field) => renderConfiguredField(field))}
              </div>
            </div>
          ))}

          <div className="border border-gray-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-semibold text-gray-700">Attachments ({document.files?.length || 0})</h4>
              <div className="flex gap-2">
                <button onClick={() => downloadAllAsZip(document.id, token, document.files, document.patient_name)} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-gray-200 text-[11px] hover:bg-gray-50" title="Download All as ZIP">
                  <Download className="w-3 h-3" /> Download ZIP
                </button>
                <input ref={fileInputRef} type="file" accept="*/*" multiple className="hidden" onChange={(e) => { const files = Array.from(e.target.files || []); if (files.length) handleFileUpload(files); e.target.value = "" }} />
                <button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="inline-flex items-center gap-1 px-2 py-1 bg-blue-600 text-white rounded-lg text-[11px]">
                  {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />} Upload
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              {document.files?.length === 0 ? (
                <p className="text-[11px] text-gray-400">No attachments</p>
              ) : (
                document.files?.map((file) => (
                  <div key={file.id} className="flex items-center gap-2 rounded-lg border border-gray-100 px-3 py-2">
                    {getFileIcon(file.file_type, file.file_name)}
                    <span className="text-[11px] text-gray-700 truncate flex-1">{file.file_name}</span>
                    <span className="text-[10px] text-gray-400">{(file.file_size / 1024).toFixed(1)} KB</span>
                    {file.file_url && <a href={file.file_url} target="_blank" rel="noreferrer" className="text-[11px] text-blue-600">Download</a>}
                    <button onClick={() => handleDeleteFile(file.id)} className="p-0.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-600"><X className="w-3 h-3" /></button>
                  </div>
                ))
              )}
            </div>
          </div>

          {editing ? (
            <div>
              {uploading && (
                <p className="mb-2 text-xs text-amber-600">Please wait for the upload to finish before saving.</p>
              )}
              <div className="flex gap-2">
                <button onClick={handleSave} disabled={saving || uploading} className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed">{saving ? "Saving..." : "Save Changes"}</button>
                <button onClick={() => { setDirtyKeys(new Set()); setEditing(false) }} className="flex-1 py-2.5 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
              </div>
            </div>
          ) : (
            <button onClick={() => onDelete(document.id)} className="w-full py-2 border border-red-200 text-red-600 rounded-xl text-sm font-medium hover:bg-red-50">Delete Document</button>
          )}
        </div>
      </div>

      {showHistory && <ChangeHistoryModal changes={history} onClose={() => setShowHistory(false)} />}

      <FormSettingsModal
        isOpen={showFormSettings}
        onClose={() => setShowFormSettings(false)}
        documentId={document?.id ?? null}
        onSaved={async () => {
          // { ...document } is just a shallow copy of the already-stale prop --
          // it doesn't carry the form_config this modal just saved, so a newly
          // added/edited field never showed up here until the modal was
          // closed and reopened. Refetch the real thing instead.
          if (document?.id) onUpdate(await getPatientDocument(token, document.id))
          onDefaultFormConfigChanged?.()
        }}
      />
    </div>
  )
}

// ─── Share to Doctor Panel ───────────────────────────────────────────────────

function ShareToDoctorPanel({
  documents, onRefresh, onOpenDocument, context = "all",
}: {
  documents: PatientDocumentRead[]
  onRefresh?: () => void
  onOpenDocument?: (documentId: string, startEditing?: boolean) => void
  // Which sidebar page this panel is shown on -- the copy below references
  // "doctor" (view-only, print/download) by default, which is wrong on the
  // Doctor to Patient page where the doctor is actually generating a fill-in
  // link for the patient, not a copy for another doctor.
  context?: "doctor-to-doctor" | "doctor-to-patient" | "all"
}) {
  const token = useToken()
  const [mode, setMode] = useState<"existing" | "new">("existing")
  const [patients, setPatients] = useState<DoctorPatient[]>([])
  const [selectedPatientId, setSelectedPatientId] = useState("")
  const [selectedDocId, setSelectedDocId] = useState("")
  const [selectedDoc, setSelectedDoc] = useState<PatientDocumentRead | null>(null)
  const [loadingDoc, setLoadingDoc] = useState(false)
  // Every document this patient already has, so picking a patient never
  // silently hides one — the doctor sees them and chooses, instead of the
  // panel guessing which one they meant.
  const [patientDocs, setPatientDocs] = useState<PatientDocumentRead[]>([])
  const [showNewPatientModal, setShowNewPatientModal] = useState(false)
  const [newPatientName, setNewPatientName] = useState("")
  const [creatingPatient, setCreatingPatient] = useState(false)
  const [patientSearch, setPatientSearch] = useState("")
  const [patientDropdownOpen, setPatientDropdownOpen] = useState(false)

  const loadPatients = useCallback(async () => {
    try {
      const res = await getPatients(token, 1, 100)
      setPatients(res.items)
    } catch (e) { console.error(e) }
  }, [token])

  useEffect(() => { loadPatients() }, [loadPatients])
  // Patients added elsewhere (Patients page, another tab) show up in the
  // picker without a reload.
  useAutoRefresh(loadPatients, { intervalMs: 60_000 })
  // Instant: pushed the moment a patient is added anywhere (this app or the
  // legacy GenSmile app, if it's still running against the same database).
  useDocumentsLiveUpdates("patients_updated", loadPatients)

  // Keep the selected patient's document (files etc.) current as the
  // parent's list refreshes -- e.g. after the patient uploads through their
  // fill link.
  useEffect(() => {
    if (!selectedDocId) return
    const fresh = documents.find((d) => d.id === selectedDocId)
    if (fresh) setSelectedDoc((prev) => (prev && docSignature(prev) === docSignature(fresh) ? prev : fresh))
  }, [documents, selectedDocId])

  const handleSelectPatient = async (patientUserId: string) => {
    setSelectedPatientId(patientUserId)
    setSelectedDocId("")
    setSelectedDoc(null)
    setPatientDocs([])
    if (!patientUserId) return
    const existing = documents.filter((d) => d.patient_user_id === patientUserId)
    if (existing.length > 1) {
      // Several documents already exist for this patient -- let the doctor
      // pick one instead of guessing, rather than silently creating another.
      setPatientDocs(existing)
      return
    }
    setLoadingDoc(true)
    try {
      const doc = existing.length === 1 ? existing[0] : await createPatientDocument(token, { patient_user_id: patientUserId })
      setSelectedDocId(doc.id)
      setSelectedDoc(doc)
      // Without this the parent's list doesn't know about the new document,
      // so picking the same patient again would create a duplicate.
      if (existing.length === 0) onRefresh?.()
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't load patient", text: errMsg(e) })
    } finally {
      setLoadingDoc(false)
    }
  }

  const handlePickPatientDoc = (doc: PatientDocumentRead) => {
    setSelectedDocId(doc.id)
    setSelectedDoc(doc)
    setPatientDocs([])
  }

  const handleStartNewDocForPatient = async () => {
    if (!selectedPatientId) return
    setLoadingDoc(true)
    try {
      const doc = await createPatientDocument(token, { patient_user_id: selectedPatientId })
      setSelectedDocId(doc.id)
      setSelectedDoc(doc)
      setPatientDocs([])
      onRefresh?.()
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't create document", text: errMsg(e) })
    } finally {
      setLoadingDoc(false)
    }
  }

  const handleShare = () => {
    if (mode === "existing") {
      if (!selectedDocId) { Swal.fire({ icon: "warning", title: "Select a patient" }); return }
      // Let the doctor review the patient's existing details/files first,
      // then actually share from the Share dropdown inside that preview --
      // mirrors how a brand-new patient's document is handed off below.
      onOpenDocument?.(selectedDocId)
    } else {
      setShowNewPatientModal(true)
    }
  }

  const handleCreateNewPatient = async () => {
    if (!newPatientName.trim()) { Swal.fire({ icon: "warning", title: "Patient name required" }); return }
    setCreatingPatient(true)
    try {
      const newDoc = await createPatientDocument(token, { patient_name: newPatientName.trim() })
      onRefresh?.()
      setShowNewPatientModal(false)
      setNewPatientName("")
      // Hand off to the full document form so the doctor can fill it in,
      // then share it themselves once it's ready -- creating no longer
      // shares automatically.
      onOpenDocument?.(newDoc.id, true)
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't create", text: errMsg(e) })
    } finally {
      setCreatingPatient(false)
    }
  }

  const panelTitle = context === "doctor-to-patient" ? "Create for patient" : "Create for doctor"
  const panelSubtitle =
    context === "doctor-to-patient"
      ? "Pick the patient and send them a link to fill in."
      : "Pick the patient and generate a secure link -- the other doctor signs in to view and edit it."

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4 shadow-sm">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{panelTitle}</h3>
        <p className="text-xs text-gray-500 mt-0.5">{panelSubtitle}</p>
      </div>

      <div className="flex bg-gray-100 rounded-xl p-1">
        <button onClick={() => { setMode("existing"); setSelectedPatientId(""); setSelectedDocId(""); setSelectedDoc(null) }} className={`flex-1 text-center text-xs font-semibold py-2 rounded-lg transition-colors ${mode === "existing" ? "bg-white text-blue-600 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
          Existing patient
        </button>
        <button onClick={() => setMode("new")} className={`flex-1 text-center text-xs font-semibold py-2 rounded-lg transition-colors ${mode === "new" ? "bg-white text-blue-600 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
          New patient
        </button>
      </div>

      {mode === "existing" && (
        <>
          <Popover open={patientDropdownOpen} onOpenChange={setPatientDropdownOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                disabled={loadingDoc}
                className="relative w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-left focus:border-blue-500 outline-none disabled:opacity-60"
              >
                <span className={selectedPatientId ? "text-gray-900" : "text-gray-500"}>
                  {patients.find((p) => p.patient_user_id === selectedPatientId)?.full_name || "Select patient..."}
                </span>
                {loadingDoc ? (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />
                ) : (
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                )}
              </button>
            </PopoverTrigger>
            <PopoverContent className="z-[80] w-[var(--radix-popover-trigger-width)] p-0" align="start">
              <Command>
                <CommandInput placeholder="Search patients..." value={patientSearch} onValueChange={setPatientSearch} />
                <CommandList>
                  <CommandEmpty className="py-4 text-sm text-gray-500">No patients found.</CommandEmpty>
                  <CommandGroup>
                    {patients.map((p) => (
                      <CommandItem
                        key={p.patient_user_id}
                        value={p.full_name}
                        onSelect={() => {
                          handleSelectPatient(p.patient_user_id)
                          setPatientDropdownOpen(false)
                          setPatientSearch("")
                        }}
                      >
                        {p.full_name}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>

          {patientDocs.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-gray-600">This patient already has {patientDocs.length} documents -- pick one:</p>
              {patientDocs.map((doc) => (
                <button key={doc.id} onClick={() => handlePickPatientDoc(doc)} className="w-full text-left flex items-center justify-between gap-2 rounded-lg border border-gray-200 px-3 py-2 hover:border-blue-400 hover:bg-blue-50">
                  <span className="text-xs text-gray-700">
                    {doc.visit_date || new Date(doc.created_at).toLocaleDateString()} · {doc.files?.length || 0} file{doc.files?.length === 1 ? "" : "s"}
                    {doc.is_shared && <span className="ml-1.5 text-[10px] text-blue-600 font-medium">Sent to Doctor</span>}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-gray-400 -rotate-90" />
                </button>
              ))}
              <button onClick={handleStartNewDocForPatient} disabled={loadingDoc} className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 border border-dashed border-gray-300 rounded-lg text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-60">
                {loadingDoc ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Start a new document instead
              </button>
            </div>
          )}

          {selectedDoc && patientDocs.length === 0 && (
            <div className="space-y-1.5 rounded-lg border border-gray-200 p-3">
              <p className="text-xs font-medium text-gray-600">
                Existing files ({selectedDoc.files?.length || 0})
              </p>
              {selectedDoc.files?.length ? (
                selectedDoc.files.map((file) => (
                  <div key={file.id} className="flex items-center gap-2 rounded-lg border border-gray-100 px-2.5 py-1.5">
                    {getFileIcon(file.file_type, file.file_name)}
                    <span className="text-[11px] text-gray-700 truncate flex-1">{file.file_name}</span>
                  </div>
                ))
              ) : (
                <p className="text-[11px] text-gray-400">No files uploaded yet.</p>
              )}
            </div>
          )}

        </>
      )}

      {mode === "new" && (
        <div className="text-center py-4">
          <p className="text-xs text-gray-500">Create a new patient document and share it with a doctor.</p>
        </div>
      )}

      <button onClick={handleShare} disabled={mode === "existing" && !selectedDocId} className="w-full py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2">
        {mode === "existing" ? <Share2 className="w-4 h-4" /> : <Plus className="w-4 h-4" />} {mode === "existing" ? "Check and Share Link" : "Create"}
      </button>

      <div className="text-[11px] text-green-700 bg-green-50 border border-green-200 rounded-lg p-2.5">
        {context === "doctor-to-patient"
          ? "Patient gets a link to fill in and submit their own information."
          : "Receiving doctor must sign in with their own account, then can view, edit, and change form settings — every edit is logged with their name."}
      </div>

      {showNewPatientModal && (
        <div className="modal-in fixed inset-0 z-[75] flex items-center justify-center bg-black/50 p-4">
          <div className="absolute inset-0" onClick={() => setShowNewPatientModal(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[80dvh] overflow-hidden flex flex-col">
            <div className="shrink-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900">New Patient for Sharing</h3>
              <button onClick={() => setShowNewPatientModal(false)} className="p-2 rounded-lg hover:bg-gray-100"><X className="w-4 h-4" /></button>
            </div>
            <div className="overflow-y-auto overscroll-none px-6 py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Patient Name <span className="text-red-500">*</span></label>
                <input type="text" value={newPatientName} onChange={(e) => setNewPatientName(e.target.value)} placeholder="Enter patient name" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" autoFocus />
                <p className="text-[11px] text-gray-500 mt-1.5">You'll fill in the rest of the form and share it once the patient document is created.</p>
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={handleCreateNewPatient} disabled={creatingPatient || !newPatientName.trim()} className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 inline-flex items-center justify-center gap-2">
                  {creatingPatient ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Create
                </button>
                <button onClick={() => setShowNewPatientModal(false)} className="flex-1 py-2.5 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Desktop-recommended nudge ──────────────────────────────────────────────
// This page's two-column create-form + recent-documents layout is cramped on
// small screens. Shown only below the md breakpoint, once per visit unless
// permanently dismissed.
const DESKTOP_HINT_KEY = "patientDocumentsDesktopHintDismissed"

function DesktopRecommendedPopup() {
  const [open, setOpen] = useState(false)
  const [dontShowAgain, setDontShowAgain] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined") return
    let dismissed = false
    try {
      dismissed = localStorage.getItem(DESKTOP_HINT_KEY) === "1"
    } catch {}
    if (dismissed || window.innerWidth >= 768) return
    setOpen(true)
  }, [])

  if (!open) return null

  const close = () => {
    if (dontShowAgain) {
      try {
        localStorage.setItem(DESKTOP_HINT_KEY, "1")
      } catch {}
    }
    setOpen(false)
  }

  return (
    <div className="modal-in fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
        <h3 className="text-lg font-bold text-gray-900">Better on Desktop</h3>
        <p className="mt-2 text-sm leading-5 text-gray-600">
          For a better experience, use this feature on desktop.
        </p>
        <label className="mt-4 flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={dontShowAgain}
            onChange={(e) => setDontShowAgain(e.target.checked)}
            className="size-4 rounded border-gray-300 text-blue-600"
          />
          Don&apos;t show this again
        </label>
        <div className="mt-5 flex justify-end">
          <button
            type="button"
            onClick={close}
            className="h-10 rounded-full bg-blue-600 px-5 text-sm font-medium text-white hover:bg-blue-700"
          >
            {dontShowAgain ? "OK" : "Continue"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Shared "new document" form fields ─────────────────────────────────────
// Used both inside the New Document modal (Doctor to Doctor / Doctor to
// Patient pages) and inline on the combined Document page below -- kept as
// one component so the two stay in sync instead of drifting apart.
function DocumentFormFields({
  formData, customFields, groupedFields, handleInputChange, handleCustomFieldChange,
  logoPreview, logoInputRef, handleLogoSelect,
  attachments, attachmentInputRef, handleAttachmentSelect, removeAttachment,
  onOpenFormSettings,
}: {
  formData: Record<string, unknown>
  customFields: Record<string, unknown>
  groupedFields: Record<string, FieldConfig[]>
  handleInputChange: (key: string, value: unknown) => void
  handleCustomFieldChange: (key: string, value: unknown) => void
  logoPreview: string | null
  logoInputRef: React.RefObject<HTMLInputElement | null>
  handleLogoSelect: (file: File | undefined) => void
  attachments: File[]
  attachmentInputRef: React.RefObject<HTMLInputElement | null>
  handleAttachmentSelect: (files: FileList | null) => void
  removeAttachment: (index: number) => void
  onOpenFormSettings: () => void
}) {
  return (
    <>
      <div className="flex flex-col md:flex-row items-start justify-between gap-4 pb-4">
        <div className="flex items-center gap-4">
          <div className="relative group shrink-0">
            {logoPreview ? (
              <img src={logoPreview} alt="Logo" className="w-16 h-16 rounded-xl object-cover border border-gray-200" />
            ) : (
              <div className="w-16 h-16 rounded-xl bg-gray-50 border-2 border-dashed border-gray-300 flex flex-col items-center justify-center text-gray-400">
                <Upload className="w-5 h-5" />
                <span className="text-[9px] mt-1 font-medium">Logo</span>
              </div>
            )}
            <input ref={logoInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; handleLogoSelect(file); e.target.value = "" }} />
            <button onClick={() => logoInputRef.current?.click()} className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-xl text-white text-[10px] font-medium cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity">
              {logoPreview ? "Change" : "Upload"}
            </button>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">New patient document</h1>
            <p className="text-xs text-gray-500 mt-0.5">Upload a logo for this document.</p>
          </div>
        </div>
        <button onClick={onOpenFormSettings} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shrink-0">
          <Settings className="w-4 h-4 text-blue-500" /> Form Settings
        </button>
      </div>

      <div className="space-y-5">
        <div>
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-3 pb-2 border-b border-gray-100">Patient</h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Patient Name <span className="text-red-500">*</span></label>
              <input type="text" value={(formData.patient_name as string) || ""} onChange={(e) => handleInputChange("patient_name", e.target.value)} placeholder="Full name" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Visit Date</label>
              <input type="date" value={(formData.visit_date as string) || ""} onChange={(e) => handleInputChange("visit_date", e.target.value)} className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Email</label>
              <input type="email" value={(formData.patient_email as string) || ""} onChange={(e) => handleInputChange("patient_email", e.target.value)} placeholder="patient@email.com" className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Phone</label>
              <input type="tel" value={(formData.patient_phone as string) || ""} onChange={(e) => handleInputChange("patient_phone", e.target.value)} placeholder="+1 ..." className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
            </div>
          </div>
        </div>

        {Object.entries(groupedFields).map(([section, fields]) => (
          <div key={section}>
            <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-3 pb-2 border-b border-gray-100">{section}</h4>
            <div className="grid gap-3 sm:grid-cols-2">
              {fields.map((field) => {
                const isCore = field.core
                const value = isCore ? formData[field.key] : customFields[field.key]
                return (
                  <div key={field.key} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                    <label className="block text-[11px] font-medium text-gray-600 mb-1">{field.label}{field.required && <span className="text-red-500"> *</span>}</label>
                    {field.type === "checkbox" ? (
                      <YesNoBoxes value={value} onChange={(v) => { if (isCore) handleInputChange(field.key, v); else handleCustomFieldChange(field.key, v) }} />
                    ) : field.type === "textarea" ? (
                      <textarea value={(value as string) || ""} onChange={(e) => { if (isCore) handleInputChange(field.key, e.target.value); else handleCustomFieldChange(field.key, e.target.value) }} rows={2} placeholder={`Enter ${field.label.toLowerCase()}...`} className="w-full px-3 py-1.5 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none resize-none" />
                    ) : field.type === "date" ? (
                      <input type="date" value={(value as string) || ""} onChange={(e) => { if (isCore) handleInputChange(field.key, e.target.value); else handleCustomFieldChange(field.key, e.target.value) }} className="w-full px-3 py-1.5 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
                    ) : (
                      <input type="text" value={(value as string) || ""} onChange={(e) => { if (isCore) handleInputChange(field.key, e.target.value); else handleCustomFieldChange(field.key, e.target.value) }} placeholder={`Enter ${field.label.toLowerCase()}...`} className="w-full px-3 py-1.5 rounded-lg border border-gray-200 text-sm focus:border-blue-500 outline-none" />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        <div>
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-3 pb-2 border-b border-gray-100">Attachments ({attachments.length})</h4>
          {attachments.length > 0 && (
            <div className="space-y-1.5 mb-3">
              {attachments.map((file, index) => (
                <div key={index} className="flex items-center gap-2 rounded-lg border border-gray-100 px-3 py-2">
                  <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                  <span className="text-xs text-gray-700 truncate flex-1">{file.name}</span>
                  <span className="text-[10px] text-gray-400 shrink-0">{(file.size / 1024).toFixed(1)} KB</span>
                  <button onClick={() => removeAttachment(index)} className="p-0.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-600 shrink-0"><X className="w-3 h-3" /></button>
                </div>
              ))}
            </div>
          )}
          <input ref={attachmentInputRef} type="file" accept="*/*" multiple className="hidden" onChange={(e: ChangeEvent<HTMLInputElement>) => { handleAttachmentSelect(e.target.files); e.target.value = "" }} />
          <button onClick={() => attachmentInputRef.current?.click()} className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2.5 border border-dashed border-gray-300 rounded-lg text-xs text-gray-600 hover:bg-gray-50">
            <Upload className="w-3.5 h-3.5" /> Upload Attachments
          </button>
        </div>
      </div>
    </>
  )
}

// ─── Shared document-list table ─────────────────────────────────────────────
// One table, reused for the Doctor to Doctor / Doctor to Patient sections on
// both their own dedicated pages and side-by-side on the combined Document
// page, so the two never show the list differently.
function DocumentListSection({
  title, docs, emptyText, loading, onView, showHeader = true,
}: {
  title: string
  docs: PatientDocumentRead[]
  emptyText: string
  loading: boolean
  onView: (docId: string) => void
  // The per-mode Doctor to Doctor / Doctor to Patient pages already show the
  // title + count in their own page header, so this list doesn't repeat it
  // there -- only on the combined Document page, where two lists sit side by
  // side and each needs its own label.
  showHeader?: boolean
}) {
  return (
    <div>
      {showHeader && (
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
          <span className="text-xs text-gray-500">{docs.length} document{docs.length === 1 ? "" : "s"}</span>
        </div>
      )}
      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : docs.length === 0 ? (
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
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Updated</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {docs.map((doc) => {
                  const status = getDocStatus(doc)
                  return (
                    <tr key={doc.id} onClick={() => onView(doc.id)} className="cursor-pointer transition-colors hover:bg-gray-50">
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
                      <td className="px-5 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${status.color}`}>
                          <span className="h-1.5 w-1.5 rounded-full bg-current" />{status.label}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-gray-500">{new Date(doc.updated_at).toLocaleDateString()}</td>
                      <td className="px-5 py-3 text-right"><ChevronRight className="inline-block h-4 w-4 text-gray-300" /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Compact "Recent documents" list (combined Document page) ──────────────
// Matches the legacy GenSmile app's patient-documents sidebar: a handful of
// rows per section (avatar, name + date, status pill) instead of a table,
// with a "See more (N)" link to the full filtered list once there are more.
function RecentDocumentsList({
  title, docs, viewAllHref, onView,
}: {
  title: string
  docs: PatientDocumentRead[]
  viewAllHref: string
  onView: (docId: string) => void
}) {
  const VISIBLE = 4
  const shown = docs.slice(0, VISIBLE)
  const remaining = docs.length - shown.length

  return (
    <div>
      <h3 className="mb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">{title}</h3>
      {shown.length === 0 ? (
        <p className="py-3 text-xs text-gray-400">No documents yet</p>
      ) : (
        <div className="divide-y divide-gray-100">
          {shown.map((doc) => {
            const status = getDocStatus(doc)
            return (
              <button
                key={doc.id}
                onClick={() => onView(doc.id)}
                className="flex w-full items-center gap-3 rounded-lg px-1 py-2.5 text-left transition-colors hover:bg-gray-50"
              >
                {doc.logo_url ? (
                  <img src={doc.logo_url} alt="" className="h-9 w-9 shrink-0 rounded-lg border border-gray-200 object-cover" />
                ) : (
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-600">
                    {doc.patient_name?.[0]?.toUpperCase()}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">{doc.patient_name}</p>
                  <p className="text-xs text-gray-400">{new Date(doc.updated_at).toLocaleDateString()}</p>
                </div>
                <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${status.color}`}>
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />{status.label}
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-gray-300" />
              </button>
            )
          })}
        </div>
      )}
      {remaining > 0 && (
        <Link to={viewAllHref} className="mt-1.5 inline-block text-xs font-medium text-blue-600 hover:text-blue-700">
          See more ({remaining}) →
        </Link>
      )}
    </div>
  )
}

// ============================================
// MAIN PATIENT DOCUMENTS PAGE
// ============================================
type PatientDocumentsPageProps = {
  // Which sidebar section this page renders as. "all" (the default) keeps
  // the original single-page behavior with both sections stacked.
  mode?: "doctor-to-doctor" | "doctor-to-patient" | "all"
}

export function PatientDocumentsPage({ mode = "all" }: PatientDocumentsPageProps = {}) {
  const token = useToken()
  const [searchParams] = useSearchParams()
  const [documents, setDocuments] = useState<PatientDocumentRead[]>([])
  const [selectedDoc, setSelectedDoc] = useState<PatientDocumentRead | null>(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [detailModalStartEditing, setDetailModalStartEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")
  const [saving, setSaving] = useState(false)
  const createRunRef = useRef(0)
  const [formFields, setFormFields] = useState<FieldConfig[]>([])
  const [formData, setFormData] = useState<Record<string, unknown>>({ visit_date: todayISO() })
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const [showDefaultFormSettings, setShowDefaultFormSettings] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<File[]>([])
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState(false)
  const logoInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)

  // Silent refresh (no spinner) -- used after every change and by the
  // background auto-refresh, so patient submissions and edits made in another
  // tab show up on their own. Also swaps in the newer copy of the document
  // open in the detail modal, if it changed.
  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await listPatientDocuments(token)
      setDocuments(docs)
      setSelectedDoc((prev) => {
        if (!prev) return prev
        const fresh = docs.find((d) => d.id === prev.id)
        return fresh && docSignature(fresh) !== docSignature(prev) ? fresh : prev
      })
    } catch (e) { console.error(e) }
  }, [token])

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    try { await refreshDocuments() }
    finally { setLoading(false) }
  }, [refreshDocuments])

  const loadFormConfig = useCallback(async () => {
    try {
      const data = await getFormConfig(token)
      setFormFields([...data.fields].sort((a, b) => a.order - b.order))
    } catch (e) { console.error(e) }
  }, [token])

  useEffect(() => { loadDocuments(); loadFormConfig() }, [loadDocuments, loadFormConfig])
  // Instant: the server pushes a message the moment a patient changes a
  // document. The slower periodic refresh (plus refresh on tab focus) stays
  // as a safety net for a dropped connection or a missed message.
  useDocumentsLiveUpdates("document_updated", refreshDocuments)
  useAutoRefresh(refreshDocuments, { intervalMs: 30_000 })

  const handleLogoSelect = (file: File | undefined) => {
    if (!file) return
    if (!file.type.startsWith("image/")) {
      Swal.fire({ icon: "warning", title: "Invalid file", text: "Logo must be an image file." })
      return
    }
    setLogoFile(file)
    setLogoPreview(URL.createObjectURL(file))
  }

  const handleAttachmentSelect = (files: FileList | null) => {
    const fileArray = Array.from(files ?? [])
    if (fileArray.length === 0) return
    setAttachments((prev) => [...prev, ...fileArray])
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  const handleCreate = async () => {
    if (!(formData.patient_name as string | undefined)?.trim()) {
      Swal.fire({ icon: "warning", title: "Patient name required" })
      return
    }
    // Each create gets an id; "Continue upload in background" bumps
    // createRunRef, detaching this run from the screen -- it still finishes,
    // but must not touch the (now cleared, maybe refilled) form or open
    // anything when it's done.
    const runId = ++createRunRef.current
    const onScreen = () => createRunRef.current === runId
    const patientName = formData.patient_name as string
    const logo = logoFile, files = attachments
    setSaving(true)
    try {
      const payload = { ...formData, custom_fields: customFields } as PatientDocumentCreate
      const newDoc = await createPatientDocument(token, payload)

      if (logo) {
        if (onScreen()) setUploadingLogo(true)
        try { await uploadPatientDocumentLogo(token, newDoc.id, logo) }
        catch (e) { console.error("Logo upload failed:", e) }
        finally { if (onScreen()) setUploadingLogo(false) }
      }

      if (files.length > 0) {
        if (onScreen()) setUploadingFiles(true)
        try { for (const file of files) { await uploadPatientDocumentAttachment(token, newDoc.id, file) } }
        catch (e) { console.error("File upload failed:", e) }
        finally { if (onScreen()) setUploadingFiles(false) }
      }

      await refreshDocuments()
      if (!onScreen()) {
        void Swal.fire({ toast: true, position: "top-end", icon: "success", title: `Document for ${patientName} is ready`, text: "Files finished uploading.", timer: 4000, showConfirmButton: false })
        return
      }
      setFormData({ visit_date: todayISO() }); setCustomFields({})
      setLogoFile(null); setLogoPreview(null); setAttachments([])

      // Show the just-created document so the doctor can see it as it'll
      // actually look, instead of only getting a toast.
      setShowCreateModal(false)
      handleViewDocument(newDoc.id)

      Swal.fire({ icon: "success", title: "Document created!", timer: 1000, showConfirmButton: false })
    } catch (e) {
      Swal.fire(onScreen()
        ? { icon: "error", title: "Couldn't create", text: errMsg(e) }
        : { toast: true, position: "top-end", icon: "error", title: `Couldn't create the document for ${patientName}`, text: errMsg(e), timer: 6000, showConfirmButton: false })
    } finally {
      if (onScreen()) setSaving(false)
    }
  }

  const deepLinkedDocId = searchParams.get("doc")
  useEffect(() => {
    if (deepLinkedDocId) handleViewDocument(deepLinkedDocId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkedDocId])

  const handleViewDocument = async (docId: string, startEditing = false) => {
    try {
      setSelectedDoc(await getPatientDocument(token, docId))
      setShowDetailModal(true)
      setDetailModalStartEditing(startEditing)
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't load", text: errMsg(e) })
    }
  }

  const handleUpdateDocument = (updated: PatientDocumentRead) => { setSelectedDoc(updated); refreshDocuments() }

  const handleDeleteDocument = async (docId: string) => {
    const confirmed = await Swal.fire({ icon: "warning", title: "Delete?", showCancelButton: true, confirmButtonText: "Delete", confirmButtonColor: "#dc2626" })
    if (!confirmed.isConfirmed) return
    try {
      await deletePatientDocument(token, docId)
      setShowDetailModal(false)
      await refreshDocuments()
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't delete", text: errMsg(e) })
    }
  }

  const createFormDirty =
    Object.entries(formData).some(([k, v]) => k !== "visit_date" && v !== "" && v != null) ||
    formData.visit_date !== todayISO() ||
    Object.values(customFields).some((v) => v !== "" && v != null) ||
    !!logoFile || attachments.length > 0
  const requestCloseCreate = async () => {
    // Mid-create: let it finish in the background (handleCreate captured the
    // form and files already), detach it from the screen, and give the
    // doctor a clean form for the next document.
    if (saving || uploadingLogo || uploadingFiles) {
      if (!(await confirmDiscard({ uploading: true, unsaved: false }))) return
      createRunRef.current++
      setSaving(false); setUploadingLogo(false); setUploadingFiles(false)
      setFormData({ visit_date: todayISO() }); setCustomFields({})
      setLogoFile(null); setLogoPreview(null); setAttachments([])
    } else if (createFormDirty) {
      if (!(await confirmDiscard())) return
      setFormData({ visit_date: todayISO() }); setCustomFields({})
      setLogoFile(null); setLogoPreview(null); setAttachments([])
    }
    setShowCreateModal(false)
  }

  const handleInputChange = (key: string, value: unknown) => setFormData((prev) => ({ ...prev, [key]: value }))
  const handleCustomFieldChange = (key: string, value: unknown) => setCustomFields((prev) => ({ ...prev, [key]: value }))

  const filteredDocuments = documents.filter((d) => d.patient_name?.toLowerCase().includes(searchTerm.toLowerCase()))
  const modeDocuments =
    mode === "doctor-to-doctor" ? filteredDocuments.filter((d) => d.is_shared)
    : mode === "doctor-to-patient" ? filteredDocuments.filter((d) => d.fill_enabled)
    : filteredDocuments
  const modeTitle = mode === "doctor-to-doctor" ? "Doctor to Doctor" : mode === "doctor-to-patient" ? "Doctor to Patient" : "Documents"
  const modeEmptyText =
    mode === "doctor-to-doctor" ? "No documents shared with other doctors yet"
    : mode === "doctor-to-patient" ? "No documents sent to patients yet"
    : "No documents yet"
  const activeFormFields = formFields.filter((f) => f.active)
  const groupedFields = activeFormFields.reduce<Record<string, FieldConfig[]>>((acc, f) => {
    const section = f.section || "Overview"
    if (!acc[section]) acc[section] = []
    acc[section].push(f)
    return acc
  }, {})

  // Combined "Document" sidebar page: the create/share form stays visible on
  // the left instead of behind a "New Document" modal, and Doctor to Doctor /
  // Doctor to Patient list side by side on the right -- this is the
  // form-plus-lists layout the standalone pages had before they were split
  // into their own sidebar entries.
  if (mode === "all") {
    return (
      <>
        <DesktopRecommendedPopup />
        <div className="w-full min-w-0">
          <div className="mb-5">
            <h1 className="text-lg font-semibold text-gray-900">Document</h1>
            <p className="text-sm text-gray-500">Create or share a document on the left -- Doctor to Doctor and Doctor to Patient documents are listed on the right.</p>
          </div>

          <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
            {/* Left: the full create form, always visible (wider column) */}
            <div className="min-w-0 space-y-6">
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <DocumentFormFields
                  formData={formData}
                  customFields={customFields}
                  groupedFields={groupedFields}
                  handleInputChange={handleInputChange}
                  handleCustomFieldChange={handleCustomFieldChange}
                  logoPreview={logoPreview}
                  logoInputRef={logoInputRef}
                  handleLogoSelect={handleLogoSelect}
                  attachments={attachments}
                  attachmentInputRef={attachmentInputRef}
                  handleAttachmentSelect={handleAttachmentSelect}
                  removeAttachment={removeAttachment}
                  onOpenFormSettings={() => setShowDefaultFormSettings(true)}
                />
                <div className="mt-5 flex justify-end border-t border-gray-100 pt-4">
                  <button
                    onClick={handleCreate}
                    disabled={saving || uploadingLogo || uploadingFiles}
                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-full text-sm font-medium hover:bg-blue-700 disabled:opacity-50 shadow-lg shadow-blue-200"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Create Document
                  </button>
                </div>
              </div>
            </div>

            {/* Right: "Create for doctor" panel + a single "Recent documents" card
                (Doctor to Doctor / Doctor to Patient), matching the legacy
                GenSmile app's patient-documents sidebar layout. */}
            <div className="min-w-0 space-y-6">
              <ShareToDoctorPanel
                documents={documents}
                onRefresh={refreshDocuments}
                onOpenDocument={(docId, startEditing) => handleViewDocument(docId, startEditing)}
              />

              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-gray-900">Recent documents</h2>
                  <span className="text-xs text-gray-500">{documents.length} total</span>
                </div>
                <div className="relative mb-4">
                  <Search className="absolute left-3 top-1/2 w-4 h-4 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search patients..."
                    className="w-full rounded-full border border-gray-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-blue-500"
                  />
                </div>
                {loading ? (
                  <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
                ) : (
                  <div className="space-y-5">
                    <RecentDocumentsList
                      title="Doctor to Doctor"
                      docs={filteredDocuments.filter((d) => d.is_shared)}
                      viewAllHref="/dashboard/doctor-to-doctor"
                      onView={handleViewDocument}
                    />
                    <RecentDocumentsList
                      title="Doctor to Patient"
                      docs={filteredDocuments.filter((d) => d.fill_enabled)}
                      viewAllHref="/dashboard/doctor-to-patient"
                      onView={handleViewDocument}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {showDetailModal && selectedDoc && (
          <DocumentDetailModal document={selectedDoc} startInEditMode={detailModalStartEditing} onClose={() => setShowDetailModal(false)} onUpdate={handleUpdateDocument} onDelete={handleDeleteDocument} onDefaultFormConfigChanged={loadFormConfig} />
        )}
        <FormSettingsModal isOpen={showDefaultFormSettings} onClose={() => setShowDefaultFormSettings(false)} documentId={null} isDefault onSaved={loadFormConfig} />
      </>
    )
  }

  return (
    <>
      <DesktopRecommendedPopup />
      <div className="w-full min-w-0">
        {/* Header: title + search + New Document */}
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">{modeTitle}</h1>
            <p className="text-sm text-gray-500">{modeDocuments.length} document{modeDocuments.length === 1 ? "" : "s"}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 w-4 h-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search patients..."
                className="w-full rounded-full border border-gray-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-blue-500 sm:w-56"
              />
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex shrink-0 items-center gap-2 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-blue-200 hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" /> New Document
            </button>
          </div>
        </div>

        {/* List - the landing content for this section */}
        <DocumentListSection title={modeTitle} docs={modeDocuments} emptyText={modeEmptyText} loading={loading} onView={handleViewDocument} showHeader={false} />
      </div>

      {/* Create-document modal: quick "share for doctor" panel + the full form */}
      {showCreateModal && (
        <div className="modal-in fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onClick={requestCloseCreate}>
          <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
              <h2 className="text-base font-semibold text-gray-900">New Document</h2>
              <button onClick={requestCloseCreate} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-6 overflow-y-auto overscroll-none px-6 py-5">
              <ShareToDoctorPanel
                documents={documents}
                onRefresh={refreshDocuments}
                onOpenDocument={(docId, startEditing) => { setShowCreateModal(false); handleViewDocument(docId, startEditing) }}
                context={mode}
              />

              <div className="border-t border-gray-100 pt-5">
                <DocumentFormFields
                  formData={formData}
                  customFields={customFields}
                  groupedFields={groupedFields}
                  handleInputChange={handleInputChange}
                  handleCustomFieldChange={handleCustomFieldChange}
                  logoPreview={logoPreview}
                  logoInputRef={logoInputRef}
                  handleLogoSelect={handleLogoSelect}
                  attachments={attachments}
                  attachmentInputRef={attachmentInputRef}
                  handleAttachmentSelect={handleAttachmentSelect}
                  removeAttachment={removeAttachment}
                  onOpenFormSettings={() => setShowDefaultFormSettings(true)}
                />
              </div>
            </div>
            <div className="flex justify-end border-t border-gray-100 px-6 py-4">
              <button
                onClick={handleCreate}
                disabled={saving || uploadingLogo || uploadingFiles}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-full text-sm font-medium hover:bg-blue-700 disabled:opacity-50 shadow-lg shadow-blue-200"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Create Document
              </button>
            </div>
          </div>
        </div>
      )}

      {showDetailModal && selectedDoc && (
        <DocumentDetailModal document={selectedDoc} startInEditMode={detailModalStartEditing} onClose={() => setShowDetailModal(false)} onUpdate={handleUpdateDocument} onDelete={handleDeleteDocument} onDefaultFormConfigChanged={loadFormConfig} />
      )}
      <FormSettingsModal isOpen={showDefaultFormSettings} onClose={() => setShowDefaultFormSettings(false)} documentId={null} isDefault onSaved={loadFormConfig} />
    </>
  )
}

// ============================================
// FORM SETTINGS PAGE (doctor default field layout)
// ============================================
export function PatientDocumentSettingsPage() {
  const token = useToken()
  const [fields, setFields] = useState<FieldConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showAddField, setShowAddField] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getFormConfig(token)
      setFields([...data.fields].sort((a, b) => a.order - b.order))
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't load settings", text: errMsg(error) })
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  const updateField = (key: string, patch: Partial<FieldConfig>) => {
    setFields((prev) => prev.map((f) => (f.key === key ? { ...f, ...patch } : f)))
  }

  const addField = (draft: NewFieldDraft) => {
    const slug = draft.label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40)
    const key = `custom_${slug || "field"}_${Date.now().toString(36)}`

    setFields((prev) => [
      ...prev,
      {
        key, label: draft.label, type: draft.type, section: draft.section,
        order: (prev[prev.length - 1]?.order || 0) + 1, active: true, required: false,
        patient_editable: false, core: false,
      },
    ])
    setShowAddField(false)
  }

  const move = (index: number, direction: number) => {
    setFields((prev) => {
      const next = [...prev]
      const target = index + direction
      if (target < 0 || target >= next.length) return prev
      ;[next[index], next[target]] = [next[target], next[index]]
      return next.map((f, i) => ({ ...f, order: i + 1 }))
    })
  }

  const deleteField = async (field: FieldConfig) => {
    const confirmed = await Swal.fire({
      icon: "warning",
      title: `Delete "${field.label}"?`,
      text: "This removes it from the form. Already-entered values for it on existing documents are kept, just no longer shown.",
      showCancelButton: true,
      confirmButtonText: "Delete",
      confirmButtonColor: "#dc2626",
    })
    if (!confirmed.isConfirmed) return
    setFields((prev) => prev.filter((f) => f.key !== field.key))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateFormConfig(token, { fields: fields.map((f, i) => ({ ...f, order: i + 1 })) })
      Swal.fire({ icon: "success", title: "Saved", timer: 1200, showConfirmButton: false })
    } catch (error) {
      Swal.fire({ icon: "error", title: "Couldn't save", text: errMsg(error) })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Form Settings</h1>
          <p className="text-sm text-gray-600">
            Show, hide, relabel, reorder, or add fields on your patient document form.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowAddField(true)} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-gray-200 bg-white text-sm font-medium hover:bg-gray-50">
            <Plus className="w-4 h-4" />
            Add Field
          </button>
          <button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Changes
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 divide-y divide-gray-100 overflow-x-auto">
        {fields.map((field, index) => (
          <div key={field.key} className={`flex items-center gap-3 px-4 py-3 min-w-[900px] ${!field.active ? "opacity-50" : ""}`}>
            <div className="flex flex-col gap-1 shrink-0">
              <button onClick={() => move(index, -1)} className="text-gray-400 hover:text-gray-600" title="Move up">&#9650;</button>
              <button onClick={() => move(index, 1)} className="text-gray-400 hover:text-gray-600" title="Move down">&#9660;</button>
            </div>
            <GripVertical className="w-4 h-4 text-gray-300 shrink-0" />

            <input type="text" value={field.label} onChange={(e) => updateField(field.key, { label: e.target.value })} className="flex-1 min-w-[160px] px-3 py-1.5 rounded-lg border border-gray-200 text-sm" />

            <input type="text" value={field.section} onChange={(e) => updateField(field.key, { section: e.target.value })} className="w-40 shrink-0 px-3 py-1.5 rounded-lg border border-gray-200 text-sm" placeholder="Section" />

            <select value={field.type} onChange={(e) => updateField(field.key, { type: e.target.value as FieldConfig["type"] })} disabled={field.core} className="w-32 shrink-0 px-3 py-1.5 rounded-lg border border-gray-200 text-sm disabled:bg-gray-50">
              {FIELD_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>

            <label className="flex items-center gap-1.5 text-xs text-gray-600 shrink-0">
              <input type="checkbox" checked={field.required} onChange={(e) => updateField(field.key, { required: e.target.checked })} />
              Required
            </label>

            <label className="flex items-center gap-1.5 text-xs text-gray-600 shrink-0">
              <input type="checkbox" checked={field.patient_editable} onChange={(e) => updateField(field.key, { patient_editable: e.target.checked })} />
              Patient can fill
            </label>

            <button onClick={() => deleteField(field)} className="p-1.5 rounded-lg hover:bg-red-50 text-red-500 shrink-0" title="Delete field">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <AddFieldModal
        isOpen={showAddField}
        onClose={() => setShowAddField(false)}
        onAdd={addField}
        existingSections={[...new Set(fields.map((f) => f.section || "Other"))]}
      />
    </div>
  )
}

// ============================================
// PRINT PAGE
// ============================================

const SECTION_FIELDS: { title: string; fields: [string, string][] }[] = [
  { title: "Chief Concern", fields: [["chief_concern", "Chief Concern"]] },
  {
    title: "CBCT Information",
    fields: [
      ["last_dds_visit", "Last DDS Visit"],
      ["cbct_taken", "CBCT Taken"],
      ["req_radiologist", "Requesting Radiologist"],
      ["exam_salivary_ph", "Salivary pH"],
      ["recommend_salivary_test", "Recommend Salivary Test"],
      ["cbct_notes", "Notes"],
    ],
  },
  {
    title: "Third Molars",
    fields: [
      ["third_molar_ll", "LL"],
      ["third_molar_lr", "LR"],
      ["third_molar_ul", "UL"],
      ["third_molar_ur", "UR"],
      ["cavitations", "Cavitations"],
      ["third_molar_recommendations", "Recommendations"],
    ],
  },
  {
    title: "Sinus Areas",
    fields: [
      ["sinus_ul", "UL"],
      ["sinus_ur", "UR"],
      ["existing_rcts", "Existing RCTs"],
      ["any_into_sinus", "Any Into Sinus"],
      ["sinus_recommendations", "Recommendations"],
    ],
  },
  {
    title: "Periodontal",
    fields: [
      ["periodontal_condition", "Condition"],
      ["tx_recommendations", "Tx Recommendations"],
      ["md_referral", "MD Referral"],
      ["blood_test", "Blood Test"],
    ],
  },
  {
    title: "Occlusion",
    fields: [
      ["occlusion", "Occlusion"],
      ["guidance", "Guidance"],
      ["occlusion_recommendations", "Recommendations"],
    ],
  },
]

function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—"
  if (typeof v === "boolean") return v ? "Yes" : "No"
  return String(v)
}

export function PatientDocumentPrintPage({ documentId }: { documentId: string }) {
  const token = useToken()
  const [doc, setDoc] = useState<PatientDocumentRead | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    getPatientDocument(token, documentId).then((data) => {
      setDoc(data)
      setTimeout(() => window.print(), 400)
    }).catch((error) => {
      setLoadError(
        errMsg(error),
      )
    })
  }, [documentId, token])

  if (loadError) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 text-center">
        <p className="text-sm text-gray-600">{loadError}</p>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="print-sheet">
      <style>{`
        @page { size: A4; margin: 16mm; }
        body { background: white; }
        .print-sheet { font-family: 'Segoe UI', system-ui, sans-serif; color: #111827; max-width: 800px; margin: 0 auto; padding: 24px; }
        .print-header { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #1d4ed8; padding-bottom: 16px; margin-bottom: 24px; }
        .print-header img { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; }
        .print-title { font-size: 20px; font-weight: 700; margin: 0; }
        .print-sub { font-size: 13px; color: #6b7280; margin: 2px 0 0; }
        .patient-meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; font-size: 13px; }
        .patient-meta div span { display: block; color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
        .section { break-inside: avoid; margin-bottom: 18px; }
        .section h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: #1d4ed8; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; margin: 0 0 8px; }
        .field-row { display: grid; grid-template-columns: 160px 1fr; gap: 8px; padding: 4px 0; font-size: 13px; }
        .field-row .label { color: #6b7280; }
        .field-row .value { white-space: pre-wrap; }
        .print-footer { margin-top: 32px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 8px; }
      `}</style>

      <div className="print-header">
        {doc.logo_url && <img src={doc.logo_url} alt="Clinic logo" />}
        <div>
          <p className="print-title">Patient Clinical Document</p>
          <p className="print-sub">Generated {new Date().toLocaleDateString()}</p>
        </div>
      </div>

      <div className="patient-meta">
        <div>
          <span>Patient</span>
          {doc.patient_name}
        </div>
        <div>
          <span>Visit Date</span>
          {doc.visit_date ? new Date(doc.visit_date).toLocaleDateString() : "—"}
        </div>
        <div>
          <span>Contact</span>
          {doc.patient_phone || doc.patient_email || "—"}
        </div>
      </div>

      {SECTION_FIELDS.map((section) => (
        <div className="section" key={section.title}>
          <h3>{section.title}</h3>
          {section.fields.map(([key, label]) => (
            <div className="field-row" key={key}>
              <div className="label">{label}</div>
              <div className="value">{formatValue((doc as unknown as Record<string, unknown>)[key])}</div>
            </div>
          ))}
        </div>
      ))}

      {Object.keys(doc.custom_fields || {}).length > 0 && (
        <div className="section">
          <h3>Additional Fields</h3>
          {Object.entries(doc.custom_fields).map(([key, value]) => (
            <div className="field-row" key={key}>
              <div className="label">{key.replace(/^custom_[a-z0-9]*_?/, "").replace(/_/g, " ")}</div>
              <div className="value">{formatValue(value)}</div>
            </div>
          ))}
        </div>
      )}

      <div className="print-footer">
        This document was generated by Documents.
      </div>
    </div>
  )
}
