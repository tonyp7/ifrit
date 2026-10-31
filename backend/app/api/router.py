from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.companies import router as companies_router
from app.api.currencies import router as currencies_router
from app.api.file_tags import router as file_tags_router
from app.api.files import router as files_router
from app.api.information_banner import router as information_banner_router
from app.api.invoice_numbering import router as invoice_numbering_router
from app.api.invoice_template import router as invoice_template_router
from app.api.invoices import router as invoices_router
from app.api.projects import router as projects_router
from app.api.settings import router as settings_router
from app.api.time_entries import router as time_entries_router
from app.api.users import router as users_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(companies_router)
api_router.include_router(currencies_router)
api_router.include_router(files_router)
api_router.include_router(file_tags_router)
api_router.include_router(settings_router)
api_router.include_router(information_banner_router)
api_router.include_router(projects_router)
api_router.include_router(time_entries_router)
api_router.include_router(invoices_router)
api_router.include_router(invoice_numbering_router)
api_router.include_router(invoice_template_router)
