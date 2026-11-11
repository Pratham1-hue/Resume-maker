from fastapi import APIRouter

from . import profiles, ingest, align, export

# NOTE: no prefix here. app.main includes this router with prefix="/api/v1",
# and each sub-router below already carries its own section prefix, giving:
#   POST /api/v1/profiles/  GET /api/v1/profiles/{id}
#   POST /api/v1/profiles/{id}/ingest  GET /api/v1/profiles/{id}/ingest/status
#   POST /api/v1/align/  POST /api/v1/export/
router = APIRouter()

router.include_router(profiles.router)
router.include_router(ingest.router)
router.include_router(align.router)
router.include_router(export.router)
