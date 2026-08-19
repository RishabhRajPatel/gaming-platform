# Main Website — Backend

The shared platform surface that sits in front of every game module (currently **rummy**;
poker will be added later as a sibling). It owns cross-game concerns so individual games
don't each reimplement them:

- **auth/** — the single identity provider (register, login, JWT issuance, sessions).
  The rummy backend validates the same JWTs, so one login works across the platform.
- **users/** — user profiles, KYC status, responsible-play limits, preferences.
- **gateway/** — the public API gateway / reverse proxy. Terminates auth, applies rate
  limits, and routes `/rummy/*` to the rummy backend (and later `/poker/*` to poker).

For local development you can run the rummy backend directly; the gateway becomes
important once there is more than one game service to fan out to.

```
main-website/backend/
├── auth/        # identity provider (shared JWT signing key with game services)
├── users/       # profile + compliance service
└── gateway/     # edge routing, rate limiting, CORS, auth termination
```
