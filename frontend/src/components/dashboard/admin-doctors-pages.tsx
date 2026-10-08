import { useCallback, useEffect, useState } from "react"
import Swal from "sweetalert2"
import { Copy, Loader2, Plus, ShieldAlert, Trash2, UserRound, X } from "lucide-react"

import { createDoctor, deleteDoctor, listDoctors } from "@/lib/api-client"
import type { AdminDoctor } from "@/lib/api-types"
import { isAdmin } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"
import { ModalExit } from "@/components/ui/modal-exit"

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong."
}

function useToken(): string {
  const token = useAuthStore((state) => state.accessToken)
  return token ?? ""
}

export function AdminAccessGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((state) => state.user)

  if (!isAdmin(user?.role)) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-gray-200 bg-white p-8 text-center shadow-sm">
        <ShieldAlert className="mx-auto mb-3 h-8 w-8 text-gray-300" />
        <h1 className="text-base font-semibold text-gray-900">Admins only</h1>
        <p className="mt-1 text-sm text-gray-500">This page is only available to admin accounts.</p>
      </div>
    )
  }

  return <>{children}</>
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
}

function AddDoctorModal({
  isOpen,
  onClose,
  onCreated,
}: {
  isOpen: boolean
  onClose: () => void
  onCreated: (doctor: AdminDoctor, password: string) => void
}) {
  const token = useToken()
  const [email, setEmail] = useState("")
  const [fullName, setFullName] = useState("")
  const [password, setPassword] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setEmail("")
    setFullName("")
    setPassword("")
  }, [isOpen])


  async function handleSubmit() {
    if (!email.trim() || !fullName.trim() || password.length < 8) {
      Swal.fire({ icon: "warning", title: "Check the form", text: "Email, name, and an 8+ character password are required." })
      return
    }
    setSaving(true)
    try {
      const doctor = await createDoctor(token, { email: email.trim(), full_name: fullName.trim(), password })
      onCreated(doctor, password)
      onClose()
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't create doctor", text: errMsg(e) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalExit show={isOpen}>{isOpen && (
    <div className="modal-in fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-900">Add Doctor</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-3 p-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Full Name</label>
            <input
              autoFocus
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Dr. Jane Smith"
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="doctor@example.com"
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Password</label>
            <input
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="mt-1 text-[11px] text-gray-400">Shown once after creation -- share it with the doctor directly.</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-gray-100 px-5 py-4">
          <button onClick={onClose} className="rounded-full px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Create Doctor
          </button>
        </div>
      </div>
    </div>
    )}</ModalExit>
  )
}

function CredentialsCallout({
  doctor,
  password,
  onDismiss,
}: {
  doctor: AdminDoctor
  password: string
  onDismiss: () => void
}) {
  const copy = () => {
    void navigator.clipboard.writeText(`Email: ${doctor.email}\nPassword: ${password}`)
    Swal.fire({ icon: "success", title: "Copied", timer: 1200, showConfirmButton: false })
  }

  return (
    <div className="mb-4 flex items-start gap-3 rounded-2xl border border-green-200 bg-green-50 p-4">
      <UserRound className="mt-0.5 h-5 w-5 shrink-0 text-green-600" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-green-900">{doctor.full_name} was created</p>
        <p className="mt-1 text-sm text-green-800">
          Email: <span className="font-mono">{doctor.email}</span> &middot; Password: <span className="font-mono">{password}</span>
        </p>
        <p className="mt-1 text-xs text-green-700">This password is only shown once -- copy it now and share it with the doctor.</p>
      </div>
      <button onClick={copy} title="Copy credentials" className="shrink-0 rounded-lg p-1.5 text-green-700 hover:bg-green-100"><Copy className="h-4 w-4" /></button>
      <button onClick={onDismiss} title="Dismiss" className="shrink-0 rounded-lg p-1.5 text-green-700 hover:bg-green-100"><X className="h-4 w-4" /></button>
    </div>
  )
}

export function DoctorsPage() {
  const token = useToken()
  const [doctors, setDoctors] = useState<AdminDoctor[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newCredentials, setNewCredentials] = useState<{ doctor: AdminDoctor; password: string } | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const loadDoctors = useCallback(async () => {
    setLoading(true)
    try {
      setDoctors(await listDoctors(token))
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't load doctors", text: errMsg(e) })
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { loadDoctors() }, [loadDoctors])

  async function handleDelete(doctor: AdminDoctor) {
    const result = await Swal.fire({
      icon: "warning",
      title: `Delete ${doctor.full_name}?`,
      text: "This permanently removes their account and all of their patients, documents, and staff. This cannot be undone.",
      showCancelButton: true,
      confirmButtonText: "Delete",
      confirmButtonColor: "#dc2626",
    })
    if (!result.isConfirmed) return

    setDeletingId(doctor.id)
    try {
      await deleteDoctor(token, doctor.id)
      setDoctors((prev) => prev.filter((d) => d.id !== doctor.id))
    } catch (e) {
      Swal.fire({ icon: "error", title: "Couldn't delete doctor", text: errMsg(e) })
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Doctors</h1>
          <p className="text-sm text-gray-500">{doctors.length} doctor{doctors.length === 1 ? "" : "s"}</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-blue-200 hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> Add Doctor
        </button>
      </div>

      {newCredentials && (
        <CredentialsCallout
          doctor={newCredentials.doctor}
          password={newCredentials.password}
          onDismiss={() => setNewCredentials(null)}
        />
      )}

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : doctors.length === 0 ? (
          <div className="p-10 text-center">
            <UserRound className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            <p className="text-sm text-gray-500">No doctors yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Created</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {doctors.map((doctor) => (
                <tr key={doctor.id}>
                  <td className="px-5 py-3 font-medium text-gray-900">{doctor.full_name}</td>
                  <td className="px-5 py-3 text-gray-600">{doctor.email}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${doctor.is_active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {doctor.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500">{formatDate(doctor.created_at)}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleDelete(doctor)}
                      disabled={deletingId === doctor.id}
                      title="Delete doctor"
                      className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                    >
                      {deletingId === doctor.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <AddDoctorModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onCreated={(doctor, password) => {
          setNewCredentials({ doctor, password })
          void loadDoctors()
        }}
      />
    </div>
  )
}
