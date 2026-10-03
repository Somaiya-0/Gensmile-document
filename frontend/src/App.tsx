import { lazy, Suspense, type ComponentType } from "react"
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom"
import { Toaster } from "@/components/ui/toaster"
import { Toaster as Sonner } from "@/components/ui/sonner"

import { PageLoader } from "@/components/ui/spinner"
import DocumentsLayout from "@/layouts/documents-layout"
import DashboardLayout from "@/layouts/dashboard-layout"
import NotFound from "@/pages/not-found"
import { destinationForRole } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

function PageFallback() {
  return <PageLoader fullscreen />
}

function PageBoundary({ Component }: { Component: ComponentType }) {
  return (
    <Suspense fallback={<PageFallback />}>
      <Component />
    </Suspense>
  )
}

// "/" has no page of its own: signed in -> the dashboard (doctor/staff or
// admin landing spot), otherwise -> sign in.
function RootRedirect() {
  const hydrated = useAuthStore((state) => state.hydrated)
  const token = useAuthStore((state) => state.accessToken)
  const user = useAuthStore((state) => state.user)
  if (!hydrated) return <PageLoader fullscreen />
  return <Navigate to={token ? destinationForRole(user?.role) : "/signin"} replace />
}

// ===== LAZY IMPORTS =====
const PageSignin = lazy(() => import("@/pages/signin/page"))
const PageForgotPassword = lazy(() => import("@/pages/forgot-password/page"))
const PageResetPassword = lazy(() => import("@/pages/reset-password/page"))
const PageSetPassword = lazy(() => import("@/pages/set-password/page"))
const PageDocumentSettings = lazy(() => import("@/pages/documents/settings/page"))
const PageDocumentPrint = lazy(() => import("@/pages/documents/print/[id]/page"))
const PagePatientDocumentFillToken = lazy(() => import("@/pages/patient-document/[fillToken]/page"))
const PageDoctorToDoctorDocumentsToken = lazy(() => import("@/pages/doctor-to-doctor/documents/[token]/page"))
const PageDashboardOverview = lazy(() => import("@/pages/dashboard/overview/page"))
const PageDashboardDocuments = lazy(() => import("@/pages/dashboard/documents/page"))
const PageDashboardDoctorToDoctor = lazy(() => import("@/pages/dashboard/doctor-to-doctor/page"))
const PageDashboardDoctorToPatient = lazy(() => import("@/pages/dashboard/doctor-to-patient/page"))
const PageDashboardShared = lazy(() => import("@/pages/dashboard/shared/page"))
const PageDashboardDoctors = lazy(() => import("@/pages/dashboard/doctors/page"))

export default function App() {
  return (
    <BrowserRouter>
      <Toaster />
      <Sonner />
      <Routes>
        <Route path="/" element={<RootRedirect />} />

        {/* ===== SIGN IN ===== */}
        <Route path="/signin" element={<PageBoundary Component={PageSignin} />} />
        <Route path="/forgot-password" element={<PageBoundary Component={PageForgotPassword} />} />
        <Route path="/reset-password" element={<PageBoundary Component={PageResetPassword} />} />
        {/* Staff invitation emails link here to set a first password. */}
        <Route path="/set-password" element={<PageBoundary Component={PageSetPassword} />} />

        {/* ===== PUBLIC DOCUMENT LINKS (the token in the URL is the key) =====
            These paths must match what the backend puts in fill_url/share_url. */}
        <Route path="/patient-document/:fillToken" element={<PageBoundary Component={PagePatientDocumentFillToken} />} />
        {/* Signed-in doctors see the share link inside the normal dashboard shell (sidebar + top bar). */}
        <Route element={<DashboardLayout />}>
          <Route path="/doctor-to-doctor/documents/:token" element={<PageBoundary Component={PageDoctorToDoctorDocumentsToken} />} />
        </Route>

        {/* Print view -- signed-in, but outside any layout so it renders
            without the top bar/sidebar. */}
        <Route path="/documents/print/:id" element={<PageBoundary Component={PageDocumentPrint} />} />

        {/* Document form-settings page keeps its original top-bar-only chrome. */}
        <Route path="/documents" element={<DocumentsLayout />}>
          <Route path="settings" element={<PageBoundary Component={PageDocumentSettings} />} />
        </Route>

        {/* ===== DASHBOARD (signed in): sidebar with Overview, Document,
            Doctor-to-Doctor / Doctor-to-Patient (doctors & staff) and
            Doctors (admins). ===== */}
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route path="overview" element={<PageBoundary Component={PageDashboardOverview} />} />
          <Route path="documents" element={<PageBoundary Component={PageDashboardDocuments} />} />
          <Route path="doctor-to-doctor" element={<PageBoundary Component={PageDashboardDoctorToDoctor} />} />
          <Route path="doctor-to-patient" element={<PageBoundary Component={PageDashboardDoctorToPatient} />} />
          <Route path="shared" element={<PageBoundary Component={PageDashboardShared} />} />
          <Route path="doctors" element={<PageBoundary Component={PageDashboardDoctors} />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  )
}
