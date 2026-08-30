# Third-Party Material and AI Disclosure

List material frameworks, libraries, starters, templates, UI kits, fonts, icons and assets used in this repository.

| Name | Version or source URL | Licence | Used for |
|---|---|---|---|
| FastAPI | >=0.115 | MIT | REST API backend framework |
| Uvicorn | >=0.34 | BSD-3-Clause | ASGI web server |
| SQLAlchemy | >=2.0.36 | MIT | Database ORM and SQL toolkit |
| Alembic | >=1.14 | MIT | Database schema migrations |
| python-dotenv | >=1.0 | BSD-3-Clause | Environment variable configuration |
| pytest | >=8.3 | MIT | Automated testing suite |
| httpx | >=0.28 | BSD-3-Clause | HTTP testing client |
| Ext JS GPL | 7.0.0 (Sencha / jsDelivr) | GPL-3.0 | UI data grid and checking list dashboard |

## AI tools

List each AI tool in `evaluation-manifest.json`, what it was used for and how the output was verified. Write `None` if no AI tool was used.

| Tool | Used for | How output was verified |
|---|---|---|
| Gemini / Antigravity | Architecture scaffolding, rule engine logic, test cases, and documentation | Verified via automated test suite (`pytest tests/`), edge-case CLI traces (`report.py`), and public JSON fixture test harness (`harness.py`) |

## Original-work statement

Everything not declared in this file or `EVENT.md` was created by the registered team during the event window.
