# Local setup guide — Phase 2 pending

This file is intentionally reserved for Phase 2. The user requested Phase 1 only and requires confirmation before setup begins, followed by confirmation at each setup step.

The Phase 1 audit observed Ubuntu 24.04.5 LTS, Python 3.12.3, Node.js 22.23.2, npm 10.9.8 and Docker Compose 5.6.0. Existing PostgreSQL/pgvector and Redis containers use host ports 55432 and 56379. No `.env` file was present at audit time. The frontend builds, and 150 backend tests pass with synthetic dependencies/fixtures in an isolated test database.

No installation, credential collection, provider account setup, public tunnel or application startup was performed as Phase 2 work. Test-only processes used for the audit have exited. Application servers remain stopped.

After confirmation, inspect the current environment again and prepare exact Ubuntu/repository commands. Never put real keys in this document or request them in chat. Confirm whether “Mailin” means the CloudMailin provider implemented by the repository. Explicitly distinguish the existing no-send demo from the requested outbound scenarios, which are missing code rather than missing configuration.

See [implementation-audit.md](implementation-audit.md) and [architecture-explained.md](architecture-explained.md) for Phase 1 findings. This is not a completed setup guide or an instruction to advance to the next phase.
