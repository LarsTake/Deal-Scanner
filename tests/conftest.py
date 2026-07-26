import os

# The developer machine may run the installed app in Supabase production mode.
# Unit tests always use an isolated in-memory database and development identity.
os.environ["DEAL_SCANNER_ENVIRONMENT"] = "development"
os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"
