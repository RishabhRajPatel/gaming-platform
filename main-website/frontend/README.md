# Main Website — Frontend

The marketing + account surface for the platform. The in-game experience lives in
`rummy/frontend`; this app covers everything around it:

```
src/
├── home/       # landing / marketing
├── login/      # shared login (calls the auth service)
├── register/   # sign up + 18+ gate
├── profile/    # account, KYC, wallet, responsible-play settings
└── lobby/      # game selection -> deep-links into rummy/frontend
```

Recommended stack mirrors the rummy frontend (React + Vite + TypeScript + Tailwind) so
components and the design system can be shared via a future `packages/ui` workspace.
