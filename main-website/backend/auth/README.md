# Auth service (identity provider)

Owns registration, login and JWT issuance for the whole platform. Game backends
(rummy, later poker) **verify** these tokens using the same `SECRET_KEY`, so a single
login works everywhere.

A production-ready reference implementation of this exact flow already exists in
`rummy/backend/app/routers/auth.py` + `app/core/security.py`. When extracting auth into
its own deployable service, lift those modules here and have the game backends depend on
the shared signing key rather than re-issuing tokens.

Responsibilities to add as the platform grows: refresh tokens, device/session
management, 2FA, OAuth social login, and password reset.
