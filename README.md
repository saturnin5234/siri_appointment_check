# SIRI appointment watcher

Polls the SIRI (Scandic CleverQ) booking site's JSON API every ~5 minutes from
GitHub Actions and sends a phone push notification via [ntfy.sh](https://ntfy.sh)
when a day earlier than the current appointment (`CURRENT_APPOINTMENT` in
`.github/workflows/check.yml`) opens up. It only **notifies**; booking is manual.

Python standard library only, so there is no `requirements.txt`.

`state.json` (committed by the workflow only when it changes) remembers which days
were already announced and whether a "session expired" alert was sent.

## Required secrets (names only)

Repository -> Settings -> Secrets and variables -> Actions:

- `SESSION_COOKIE`: only the value after `_scandic_session=`, no quotes or spaces
- `BOOKING_SESSION_KEY`
- `NOT_PUBLIC_TOKEN`
- `NTFY_TOPIC`

The first three come from the `available_days` request in Chrome DevTools ->
Network -> "Copy as cURL" on the appointment page.

## When the session expires

You get a one-time "SIRI checker needs attention" push (HTTP 403 "No booking
session found"). Copy fresh values from the booking page as above, then run in
your own terminal (each prompts with hidden input):

```
gh secret set SESSION_COOKIE --repo saturnin5234/siri_appointment_check
gh secret set BOOKING_SESSION_KEY --repo saturnin5234/siri_appointment_check
gh secret set NOT_PUBLIC_TOKEN --repo saturnin5234/siri_appointment_check
```

Test with: `gh workflow run "Check SIRI appointments"`.
Note: the bot commits `state.json`, so run `git pull --rebase` before local pushes.
