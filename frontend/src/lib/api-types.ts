type AdminDoctor = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
}

type AdminDoctorCreate = {
  email: string
  full_name: string
  password: string
}

type AdminDocument = {
  id: string
  doctor_profile_id: string
  doctor_name: string
  doctor_email: string
  patient_name: string
  patient_email: string | null
  logo_url: string | null
  is_shared: boolean
  fill_enabled: boolean
  patient_submitted_at: string | null
  created_at: string
  updated_at: string
}

type StaffMember = {
  id: string
  full_name: string
  email: string
  role: string
  status: string
  permissions: Record<string, boolean>
  is_active: boolean
  // Why is_active is false, if it is: "manual" (doctor removed them),
  // "capacity_limit" (plan/add-on downgrade), or "subscription_suspended"
  // (frozen by a suspended subscription -- comes back automatically on restore).
  deactivation_reason: string | null
  sort_order: number
  credit_balance: number
  primary_clinic_id: string | null
  created_at: string
  updated_at: string
  setup_url?: string | null
}

export type DoctorPatientStatus = "pending" | "active" | "inactive"

export interface Clinic {
  id: string
  doctor_profile_id: string
  clinic_name: string
  description: string | null
  address: string
  phone: string
  logo_name?: string | null
  logo_url?: string | null
  is_active: boolean
  // Why is_active is false, if it is: "manual", "capacity_limit", or
  // "subscription_suspended" (frozen by a suspended subscription -- comes
  // back automatically on restore).
  deactivation_reason?: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface DoctorPatient {
  id: string
  patient_user_id: string
  full_name: string
  email: string | null
  phone: string | null
  gender: string | null
  birth_date: string | null
  status: DoctorPatientStatus
  linked_at: string
  last_visit: string | null
}

type FieldConfig = {
  key: string
  label: string
  type: "text" | "textarea" | "checkbox" | "date" | "select"
  section: string
  order: number
  active: boolean
  required: boolean
  patient_editable: boolean
  core: boolean
  options?: string[] | null
}

type FormConfigRead = {
  doctor_profile_id: string
  fields: FieldConfig[]
  logo_url: string | null
}

type FormConfigUpdate = {
  fields: FieldConfig[]
}

type DocumentFormConfigUpdate = {
  fields: FieldConfig[]
}

type SharedWithMeDocument = {
  share_token: string
  patient_name: string
  owner_name: string
  visit_date: string | null
  updated_at: string
  last_opened_at: string
}

type LogoUploadResponse = {
  logo_url: string
}

type PatientDocumentFileRead = {
  id: string
  file_name: string
  file_type: string
  file_size: number
  file_url: string | null
  uploaded_by_patient: boolean
  uploaded_by?: string | null
  created_at: string
}

type PatientDocumentClinicalFields = {
  chief_concern: string | null
  last_dds_visit: string | null
  cbct_taken: boolean | null
  req_radiologist: string | null
  exam_salivary_ph: string | null
  recommend_salivary_test: boolean | null
  cbct_notes: string | null
  third_molar_ll: string | null
  third_molar_lr: string | null
  third_molar_ul: string | null
  third_molar_ur: string | null
  cavitations: string | null
  third_molar_recommendations: string | null
  sinus_ul: string | null
  sinus_ur: string | null
  existing_rcts: string | null
  any_into_sinus: boolean | null
  sinus_recommendations: string | null
  periodontal_condition: string | null
  tx_recommendations: string | null
  md_referral: boolean | null
  blood_test: boolean | null
  occlusion: string | null
  guidance: string | null
  occlusion_recommendations: string | null
}

type PatientDocumentRead = PatientDocumentClinicalFields & {
  id: string
  doctor_profile_id: string
  patient_name: string
  patient_email: string | null
  patient_phone: string | null
  patient_user_id: string | null
  visit_date: string | null
  custom_fields: Record<string, unknown>
  is_active: boolean
  logo_url: string | null
  form_config: FieldConfig[] | null
  share_token: string
  is_shared: boolean
  share_url: string | null
  fill_token: string
  fill_enabled: boolean
  fill_url: string | null
  patient_submitted_at: string | null
  files: PatientDocumentFileRead[]
  created_at: string
  updated_at: string
}

type PatientDocumentCreate = Partial<PatientDocumentClinicalFields> & {
  patient_name?: string
  patient_email?: string | null
  patient_phone?: string | null
  patient_user_id?: string | null
  visit_date?: string | null
  custom_fields?: Record<string, unknown>
  // One-off field layout for just this document; omitted = the default form.
  form_config?: FieldConfig[]
}

type PatientDocumentUpdate = Partial<PatientDocumentClinicalFields> & {
  patient_name?: string
  patient_email?: string | null
  patient_phone?: string | null
  visit_date?: string | null
  custom_fields?: Record<string, unknown>
  is_active?: boolean
  fill_enabled?: boolean
}

type PatientDocumentChangeLog = {
  id: string
  changed_by_name: string
  change_type: "value" | "settings" | "file" | "sharing" | "document"
  field_key: string | null
  field_label: string
  old_value: string | null
  new_value: string | null
  created_at: string
}

type PatientDocumentPublicRead = {
  patient_name: string
  patient_email: string | null
  patient_phone: string | null
  doctor_name: string
  logo_url: string | null
  visit_date: string | null
  shared_at: string | null
  fields: FieldConfig[]
  values: Record<string, unknown>
  files: PatientDocumentFileRead[]
  changes: PatientDocumentChangeLog[]
}

type PatientFillFormRead = {
  id: string
  patient_name: string
  patient_email: string | null
  patient_phone: string | null
  doctor_name: string
  logo_url: string | null
  fields: FieldConfig[]
  values: Record<string, unknown>
  submitted: boolean
  files: PatientDocumentFileRead[]
}

type PatientFillFormSubmit = {
  patient_name?: string | null
  patient_email?: string | null
  patient_phone?: string | null
  values: Record<string, unknown>
}

type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

type ContactMethod = "sms" | "email" | "phone"

// Mirrors the backend's UserRole enum. Only doctor and staff can use this
// app (see lib/auth-routing), but /auth/me can return any of them.
type AccountRole = "doctor" | "patient" | "staff" | "admin" | "affiliate"

type Account = {
  id: string
  role: AccountRole
  email: string
  full_name: string
  is_active: boolean
  onboarding_completed: boolean
  created_at: string
  updated_at: string
}

type StaffInvite = {
  id: string
  full_name: string
  email: string
  role: string
  sort_order: number
}

type DoctorProfile = {
  id: string
  clinics: Clinic[]
  staff_members: StaffInvite[]
}

type PatientProfile = {
  id: string
  phone: string | null
  birth_date: string | null
  gender: string | null
  blood_group: string | null
  full_address: string | null
  street_address: string | null
  city: string | null
  state_name: string | null
  state_code: string | null
  country_name: string | null
  country_code: string | null
  zip_code: string | null
  preferred_contact_method: ContactMethod
}

type TokenPairResponse = {
  access_token: string
  refresh_token: string
  token_type: "bearer"
  access_token_expires_at: string
  refresh_token_expires_at: string
  user: Account
}

type CurrentUserResponse = {
  user: Account
  doctor_profile: DoctorProfile | null
  patient_profile: PatientProfile | null
}

type ForgotPasswordResponse = {
  message: string
  reset_token: string | null
  reset_url: string | null
}

type ResetPasswordResponse = {
  message: string
}

export type {
  Account,
  ContactMethod,
  CurrentUserResponse,
  FieldConfig,
  FormConfigRead,
  FormConfigUpdate,
  DocumentFormConfigUpdate,
  LogoUploadResponse,
  SharedWithMeDocument,
  AdminDoctor,
  AdminDoctorCreate,
  AdminDocument,
  PatientDocumentChangeLog,
  PatientDocumentFileRead,
  PatientDocumentRead,
  PatientDocumentCreate,
  PatientDocumentUpdate,
  PatientDocumentPublicRead,
  PatientFillFormRead,
  PatientFillFormSubmit,
  DoctorProfile,
  ForgotPasswordResponse,
  PaginatedResponse,
  PatientProfile,
  ResetPasswordResponse,
  StaffInvite,
  StaffMember,
  TokenPairResponse,
}
