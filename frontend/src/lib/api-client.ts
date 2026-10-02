import { ApiError, apiRequest, getApiBaseUrl, refreshAccessToken } from "@/lib/api"
import type {
  AdminDoctor,
  AdminDoctorCreate,
  AdminDocument,
  FieldConfig,
  FormConfigRead,
  FormConfigUpdate,
  DocumentFormConfigUpdate,
  LogoUploadResponse,
  PatientDocumentFileRead,
  PatientDocumentChangeLog,
  PatientDocumentRead,
  PatientDocumentCreate,
  PatientDocumentUpdate,
  PatientDocumentPublicRead,
  PatientFillFormRead,
  PatientFillFormSubmit,
  DoctorPatient,
  DoctorPatientStatus,
  PaginatedResponse,
  StaffMember,
} from "@/lib/api-types"

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

export async function getMyStaffRecord(token: string): Promise<StaffMember> {
  return apiRequest<StaffMember>("/staff/me", { headers: authHeaders(token) })
}

export async function listDoctors(token: string): Promise<AdminDoctor[]> {
  return apiRequest<AdminDoctor[]>("/admin/doctors", { headers: authHeaders(token) })
}

export async function createDoctor(token: string, payload: AdminDoctorCreate): Promise<AdminDoctor> {
  return apiRequest<AdminDoctor>("/admin/doctors", {
    method: "POST",
    headers: authHeaders(token),
    body: payload,
  })
}

export async function deleteDoctor(token: string, doctorId: string): Promise<void> {
  await apiRequest<void>(`/admin/doctors/${doctorId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  })
}

export async function listAllDocuments(token: string): Promise<AdminDocument[]> {
  return apiRequest<AdminDocument[]>("/admin/documents", { headers: authHeaders(token) })
}

export async function getPatients(
  token: string,
  page = 1,
  pageSize = 50,
  status?: DoctorPatientStatus,
): Promise<PaginatedResponse<DoctorPatient>> {
  const url = status
    ? `/doctors/patients?page=${page}&page_size=${pageSize}&status=${status}`
    : `/doctors/patients?page=${page}&page_size=${pageSize}`
  return apiRequest<PaginatedResponse<DoctorPatient>>(url, { headers: authHeaders(token) })
}

// Raw fetch (uploads/downloads) with the same "refresh once on 401 and retry"
// apiRequest does, so an expired access token doesn't bounce the doctor out
// mid-upload.
async function fetchWithAuthRetry(url: string, init: RequestInit, token: string): Promise<Response> {
  const response = await fetch(url, { ...init, headers: { ...init.headers, ...authHeaders(token) } })
  if (response.status !== 401) return response
  const newToken = await refreshAccessToken()
  if (!newToken) return response
  return fetch(url, { ...init, headers: { ...init.headers, ...authHeaders(newToken) } })
}

function waitForNetwork(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    if (navigator.onLine) return setTimeout(resolve, delayMs)
    window.addEventListener("online", () => resolve(), { once: true })
  })
}

async function uploadPatientDocumentFile(
  token: string,
  path: string,
  file: File,
): Promise<Response> {
  const formData = new FormData()
  formData.append("file", file)
  const baseUrl = getApiBaseUrl()
  // Survive a dropped connection: on a network error (or a gateway 502-504
  // while the server restarts) wait until the browser is back online, then
  // retry the same file. The spinner just keeps spinning meanwhile.
  // ponytail: retry lives in memory only, a page reload while offline loses
  // the pending upload; persist to IndexedDB if that turns out to matter.
  let response: Response
  for (let attempt = 0; ; attempt++) {
    try {
      response = await fetchWithAuthRetry(`${baseUrl}${path}`, {
        method: "POST",
        body: formData,
      }, token)
      if (![502, 503, 504].includes(response.status)) break
    } catch (err) {
      if (!(err instanceof TypeError)) throw err
    }
    await waitForNetwork(Math.min(1000 * 2 ** attempt, 30_000))
  }
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new ApiError(err.detail || "Upload failed", response.status, err)
  }
  return response
}

export async function listPatientDocuments(token: string): Promise<PatientDocumentRead[]> {
  return apiRequest<PatientDocumentRead[]>("/patient-documents", { headers: authHeaders(token) })
}

export async function createPatientDocument(
  token: string,
  payload: PatientDocumentCreate,
): Promise<PatientDocumentRead> {
  return apiRequest<PatientDocumentRead>("/patient-documents", {
    method: "POST",
    headers: authHeaders(token),
    body: payload,
  })
}

export async function getPatientDocument(token: string, documentId: string): Promise<PatientDocumentRead> {
  return apiRequest<PatientDocumentRead>(`/patient-documents/${documentId}`, { headers: authHeaders(token) })
}

export async function getPatientDocumentChanges(token: string, documentId: string): Promise<PatientDocumentChangeLog[]> {
  return apiRequest<PatientDocumentChangeLog[]>(`/patient-documents/${documentId}/changes`, { headers: authHeaders(token) })
}

export async function updatePatientDocument(
  token: string,
  documentId: string,
  payload: PatientDocumentUpdate,
): Promise<PatientDocumentRead> {
  return apiRequest<PatientDocumentRead>(`/patient-documents/${documentId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: payload,
  })
}

export async function deletePatientDocument(token: string, documentId: string): Promise<void> {
  await apiRequest<unknown>(`/patient-documents/${documentId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  })
}

// apiRequest always parses JSON, so the zip download (a binary body) goes
// through a plain fetch instead.
export async function downloadPatientDocumentZip(token: string, documentId: string): Promise<Blob> {
  // no-store: this is a dynamically generated file, and Android WebView's
  // HTTP cache is more aggressive than a normal browser's about reusing a
  // GET response for the same URL -- without this, a bad response from an
  // earlier attempt (e.g. mid-testing before a backend fix) can keep being
  // replayed on retry even after the server-side issue is resolved.
  const response = await fetchWithAuthRetry(`${getApiBaseUrl()}/patient-documents/${documentId}/download-zip`, {
    cache: "no-store",
  }, token)
  if (!response.ok) throw new ApiError("Couldn't download zip", response.status, await response.text())
  return response.blob()
}

export async function uploadPatientDocumentLogo(
  token: string,
  documentId: string,
  file: File,
): Promise<LogoUploadResponse> {
  const response = await uploadPatientDocumentFile(token, `/patient-documents/${documentId}/logo`, file)
  return response.json()
}

export async function uploadPatientDocumentAttachment(
  token: string,
  documentId: string,
  file: File,
): Promise<PatientDocumentFileRead> {
  const response = await uploadPatientDocumentFile(token, `/patient-documents/${documentId}/files`, file)
  return response.json()
}

export async function deletePatientDocumentFile(token: string, fileId: string): Promise<void> {
  await apiRequest<unknown>(`/patient-documents/files/${fileId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  })
}

export async function toggleDocumentSharing(
  token: string,
  documentId: string,
  isShared: boolean,
): Promise<PatientDocumentRead> {
  return apiRequest<PatientDocumentRead>(
    `/patient-documents/${documentId}/share?is_shared=${isShared}`,
    { method: "PATCH", headers: authHeaders(token) },
  )
}

export async function toggleFillLink(
  token: string,
  documentId: string,
  fillEnabled: boolean,
): Promise<PatientDocumentRead> {
  return apiRequest<PatientDocumentRead>(
    `/patient-documents/${documentId}/fill-link?fill_enabled=${fillEnabled}`,
    { method: "PATCH", headers: authHeaders(token) },
  )
}

export async function getDocumentFormConfig(token: string, documentId: string): Promise<{ fields: FieldConfig[] }> {
  return apiRequest<{ fields: FieldConfig[] }>(`/patient-documents/${documentId}/form-config`, {
    headers: authHeaders(token),
  })
}

export async function updateDocumentFormConfig(
  token: string,
  documentId: string,
  payload: DocumentFormConfigUpdate,
): Promise<{ fields: FieldConfig[] }> {
  return apiRequest<{ fields: FieldConfig[] }>(`/patient-documents/${documentId}/form-config`, {
    method: "PUT",
    headers: authHeaders(token),
    body: payload,
  })
}

export async function getFormConfig(token: string): Promise<FormConfigRead> {
  return apiRequest<FormConfigRead>("/form-config", { headers: authHeaders(token) })
}

export async function updateFormConfig(token: string, payload: FormConfigUpdate): Promise<FormConfigRead> {
  return apiRequest<FormConfigRead>("/form-config", {
    method: "PUT",
    headers: authHeaders(token),
    body: payload,
  })
}

// Doctor-authenticated: another doctor opening a doctor-to-doctor share
// link, having signed in first (any doctor/staff account, not just the
// document's owner).
export async function getDoctorToDoctorDocument(token: string, shareToken: string): Promise<PatientDocumentPublicRead> {
  return apiRequest<PatientDocumentPublicRead>(`/doctor-to-doctor/documents/${shareToken}`, {
    headers: authHeaders(token),
  })
}

export async function updateDoctorToDoctorDocument(
  token: string,
  shareToken: string,
  payload: PatientDocumentUpdate,
): Promise<PatientDocumentPublicRead> {
  return apiRequest<PatientDocumentPublicRead>(`/doctor-to-doctor/documents/${shareToken}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: payload,
  })
}

export async function getDoctorToDoctorFormConfig(
  token: string,
  shareToken: string,
): Promise<{ fields: FieldConfig[] }> {
  return apiRequest<{ fields: FieldConfig[] }>(`/doctor-to-doctor/documents/${shareToken}/form-config`, {
    headers: authHeaders(token),
  })
}

export async function updateDoctorToDoctorFormConfig(
  token: string,
  shareToken: string,
  payload: DocumentFormConfigUpdate,
): Promise<{ fields: FieldConfig[] }> {
  return apiRequest<{ fields: FieldConfig[] }>(`/doctor-to-doctor/documents/${shareToken}/form-config`, {
    method: "PUT",
    headers: authHeaders(token),
    body: payload,
  })
}

export async function downloadDoctorToDoctorZip(token: string, shareToken: string): Promise<Blob> {
  const response = await fetchWithAuthRetry(`${getApiBaseUrl()}/doctor-to-doctor/documents/${shareToken}/download-zip`, {
    cache: "no-store",
  }, token)
  if (!response.ok) throw new ApiError("Couldn't download zip", response.status, await response.text())
  return response.blob()
}

// Public (no auth): the patient's own self-fill form.
export async function getPatientFillForm(fillToken: string): Promise<PatientFillFormRead> {
  return apiRequest<PatientFillFormRead>(`/patient-document/${fillToken}`)
}

export async function submitPatientFillForm(
  fillToken: string,
  payload: PatientFillFormSubmit,
): Promise<PatientFillFormRead> {
  return apiRequest<PatientFillFormRead>(`/patient-document/${fillToken}`, {
    method: "POST",
    body: payload,
  })
}

export async function uploadDoctorToDoctorFile(token: string, shareToken: string, file: File): Promise<PatientDocumentFileRead> {
  const response = await uploadPatientDocumentFile(token, `/doctor-to-doctor/documents/${shareToken}/files`, file)
  return response.json()
}

export async function deleteDoctorToDoctorFile(token: string, shareToken: string, fileId: string): Promise<void> {
  await apiRequest<unknown>(`/doctor-to-doctor/documents/${shareToken}/files/${fileId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  })
}

export async function uploadPatientFillFile(
  fillToken: string,
  file: File,
): Promise<PatientDocumentFileRead> {
  const response = await uploadPatientDocumentFile(fillToken, `/patient-document/${fillToken}/files`, file)
  return response.json()
}

export async function deletePatientFillFile(fillToken: string, fileId: string): Promise<void> {
  await apiRequest<unknown>(`/patient-document/${fillToken}/files/${fileId}`, {
    method: "DELETE",
  })
}

// Binary body, so a plain fetch instead of apiRequest (which always parses JSON).
export async function downloadPatientFillZip(fillToken: string): Promise<Blob> {
  const response = await fetch(`${getApiBaseUrl()}/patient-document/${fillToken}/download-zip`, {
    cache: "no-store",
  })
  if (!response.ok) throw new ApiError("Couldn't download zip", response.status, await response.text())
  return response.blob()
}
