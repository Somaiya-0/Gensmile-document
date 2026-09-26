import { Link } from "react-router-dom"

import { useAuthStore } from "@/stores/auth-store"

export default function NotFound() {
  const user = useAuthStore((state) => state.user)

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <p className="text-sm font-medium text-[#475569] mb-2">404</p>
      <h1 className="text-2xl font-semibold text-[#101828] mb-2">Page not found</h1>
      <p className="text-sm text-[#475569] mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="inline-flex h-9 items-center justify-center rounded-full bg-[#0052cc] px-4 text-sm font-medium text-white transition-colors hover:bg-[#0047b3]"
      >
        {user ? "Back to Documents" : "Go to sign in"}
      </Link>
    </div>
  )
}