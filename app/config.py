import os
from pathlib import Path

from dotenv import load_dotenv

# Local dev only — never override platform env (Railway, etc.)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.is_file():
    load_dotenv(_ENV_PATH, override=False)


def get_settings() -> dict[str, str | None]:
    return {
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY"),
        "stripe_webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET"),
        "stripe_price_id_pro": os.getenv("STRIPE_PRICE_ID_PRO"),
        "voltflow_integration_secret": os.getenv(
            "VOLTFLOW_INTEGRATION_SECRET", "dev-integration-secret"
        ),
        "checkout_success_url": os.getenv(
            "CHECKOUT_SUCCESS_URL", "http://localhost:3000/billing?checkout=success"
        ),
        "checkout_cancel_url": os.getenv(
            "CHECKOUT_CANCEL_URL", "http://localhost:3000/billing?checkout=cancel"
        ),
        "billing_portal_return_url": os.getenv(
            "BILLING_PORTAL_RETURN_URL", "http://localhost:3000/billing"
        ),
        "usage_stub_amount_cents": os.getenv("USAGE_STUB_AMOUNT_CENTS", "50"),
        "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:3000"),
    }
