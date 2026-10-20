import logging

from fastapi import FastAPI

from nfse_audit import __version__
from nfse_audit.api.routes import router
from nfse_audit.config import get_settings


def create_app() -> FastAPI:
    logging.basicConfig(level=get_settings().log_level)
    app = FastAPI(
        title="NFS-e Audit Pipeline",
        version=__version__,
        description="Batch auditing of NFS-e invoices against versioned tax rules.",
    )
    app.include_router(router)
    return app


app = create_app()
