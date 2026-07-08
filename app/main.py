from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as billing_router
from app.config import get_settings

app = FastAPI(
    title="VoltFlow API",
    description=(
        "Facturation à l'usage pour Meridian — Stripe Checkout, Billing Portal, "
        "webhooks et suivi d'usage."
    ),
    version="0.1.0",
)

_settings = get_settings()
_origins = [o.strip() for o in str(_settings["cors_origins"]).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(billing_router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "voltflow-api",
        "supabase_configured": bool(
            settings.get("supabase_url") and settings.get("supabase_service_role_key")
        ),
        "stripe_configured": bool(
            settings.get("stripe_secret_key") and settings.get("stripe_webhook_secret")
        ),
    }
