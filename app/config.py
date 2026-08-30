import os
import pathlib

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
BUNDLED_DB = PROJECT_ROOT / "results.db"

# Vercel sets this. Its filesystem is read only, so SQLite has to be opened in
# read-only mode there. The database ships with the repository already seeded
# and computed, which is why the deployment needs no Postgres and no env vars.
ON_VERCEL = bool(os.getenv("VERCEL"))

_explicit = os.getenv("DATABASE_URL")

if _explicit:
    # Any Postgres works. Supabase is one option, not a requirement:
    #   postgresql+psycopg://postgres:pass@localhost:5432/results
    #   postgresql+psycopg://postgres.<ref>:<pass>@aws-0-<region>.pooler.supabase.com:6543/postgres
    DATABASE_URL = _explicit
    READ_ONLY = False
elif ON_VERCEL:
    DATABASE_URL = f"sqlite:///file:{BUNDLED_DB}?mode=ro&uri=true"
    READ_ONLY = True
else:
    DATABASE_URL = f"sqlite:///{BUNDLED_DB}"
    READ_ONLY = False

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:1841,http://127.0.0.1:1841"
).split(",")

APP_NAME = "School Result Processing and GPA Engine"
