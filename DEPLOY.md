# Deploying to Vercel

No database server needed. `results.db` ships with the repository already seeded
and computed, and Vercel opens it read only. No environment variables, no
Supabase, no migrations.

## Steps

1. Push this repository to GitHub. Make sure `results.db` is committed:
   `git status` should list it, and `.gitignore` deliberately does not exclude it.
2. vercel.com, **Add New Project**, import the repository.
3. Framework preset: **Other**. Leave the build and output settings empty.
4. Deploy.

That is all. `vercel.json` routes `/api/*` to the FastAPI app and everything
else to `web/`.

## Check

    https://your-app.vercel.app/api/health          -> read_only: true
    https://your-app.vercel.app/api/students?limit=3
    https://your-app.vercel.app/api/reports/checking-lists
    https://your-app.vercel.app/

## What read-only means

`POST /api/results/compute` cannot write, so it returns the count already stored
rather than recomputing. Everything else works: the student list, the per
student trace, and the three checking lists all read from the shipped database.
The engine itself still runs live on every trace request, so nothing about the
grading is precomputed or faked.

## Changing the data

Rebuild the file locally and commit it again:

    python -c "from alembic.config import main; main(argv=['upgrade','head'])"
    python -m seed.seed_data
    python -c "from app.db import SessionLocal; from app import services; print(services.compute_all(SessionLocal()))"

## If you would rather use Postgres

Set `DATABASE_URL` in Vercel's environment variables and it takes priority over
the bundled file. Use a **session pooler** connection string, not a direct one.
Run `alembic upgrade head` and the seed from your own machine first, since
migrations do not run on Vercel.

## Ext JS

`web/ext/` is not committed, so the deployed page pulls Ext from the jsDelivr
mirror declared in `web/index.html`. If that mirror is unavailable the page
shows an explanatory message instead of loading. Committing `web/ext/` fixes it
but see LICENSE-NOTE.md first: Ext JS 7.0 is GPL v3.
