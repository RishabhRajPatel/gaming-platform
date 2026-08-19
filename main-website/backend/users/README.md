# Users service (profiles & compliance)

Cross-game user data that shouldn't live inside any single game:

- Profile: display name, avatar, locale, preferences.
- Compliance: KYC status (see `User.kyc_status` in the rummy models), 18+ verification,
  state/geo eligibility for real-money play.
- Responsible play: deposit limits, self-exclusion, session-time reminders.

These fields are already modelled on the shared `users` table
(`rummy/backend/app/models/user.py`). This service is where the write/verify workflows
for them belong once auth and users are split out of the rummy backend.
