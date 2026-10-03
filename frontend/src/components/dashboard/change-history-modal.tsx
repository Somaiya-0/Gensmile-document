import { History, Loader2, X } from "lucide-react"

import type { PatientDocumentChangeLog } from "@/lib/api-types"

const TYPE_BADGES: Record<PatientDocumentChangeLog["change_type"], [string, string]> = {
  value: ["Value", "bg-blue-50 text-blue-700"],
  settings: ["Setting", "bg-amber-50 text-amber-700"],
  file: ["File", "bg-purple-50 text-purple-700"],
  sharing: ["Sharing", "bg-green-50 text-green-700"],
  document: ["Document", "bg-gray-100 text-gray-700"],
}

function formatDateTime(dateString: string) {
  return new Date(dateString).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  })
}

/** Audit trail for one document: who changed what, from what to what, and when. */
export function ChangeHistoryModal({
  changes, onClose,
}: {
  changes: PatientDocumentChangeLog[] | null // null = still loading
  onClose: () => void
}) {
  return (
    <div className="modal-in fixed inset-0 z-[85] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[80dvh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="shrink-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Change History</h3>
            <p className="text-xs text-gray-500">Who changed what, and when</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto overscroll-none px-6 py-4 space-y-3">
          {changes === null ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>
          ) : changes.length === 0 ? (
            <div className="text-center py-8">
              <History className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No changes recorded yet.</p>
            </div>
          ) : (
            changes.map((change) => {
              const [badge, badgeClass] = TYPE_BADGES[change.change_type] ?? [change.change_type, "bg-gray-100 text-gray-700"]
              return (
                <div key={change.id} className="rounded-xl border border-gray-200 px-3.5 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-gray-900">{change.changed_by_name}</span>
                    <span className="text-[10px] text-gray-400 shrink-0">{formatDateTime(change.created_at)}</span>
                  </div>
                  <p className="text-xs text-gray-600 mt-1">
                    <span className={`inline-block mr-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium ${badgeClass}`}>{badge}</span>
                    {change.field_label}:{" "}
                    <span className="text-gray-500">{change.old_value ?? "—"}</span>
                    {" → "}
                    <span className="text-gray-900 font-medium">{change.new_value ?? "—"}</span>
                  </p>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
