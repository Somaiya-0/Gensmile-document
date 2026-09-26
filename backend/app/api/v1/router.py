from fastapi import APIRouter

from app.api.v1.routes.admin_doctors import router as admin_doctors_router
from app.api.v1.routes.admin_documents import router as admin_documents_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.documents_support import router as documents_support_router
from app.api.v1.routes.form_config import router as form_config_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.patient_documents import router as patient_documents_router

router = APIRouter()
router.include_router(auth_router, tags=["auth"])
router.include_router(health_router, tags=["health"])
router.include_router(documents_support_router)
router.include_router(form_config_router, tags=["form-config"])
router.include_router(patient_documents_router, tags=["patient-documents"])
router.include_router(admin_doctors_router)
router.include_router(admin_documents_router)
