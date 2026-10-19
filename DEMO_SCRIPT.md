# 5-minute demo script

**Scenario 1: link creation to analytics (about 2.5 min)**
1. Open the home page. Create a link with a long URL and a custom alias.
2. Show a validation error first (same alias again), then fix it.
3. Open the short link in a new tab, then open the dashboard and show the click went up.

**Scenario 2: edge cases and takedown (about 2.5 min)**
1. Open a code that does not exist. Show the clear error page.
2. Show the expired sample link (`/old-offer`) and its history on the dashboard.
3. Click Disable on a live link. Open it again: blocked, but analytics stay.

Close with: "Next steps: login, passwords, CSV import, campaigns, custom domains."

## Test checklist
- [ ] Normal link redirects and the count goes up by 1
- [ ] Duplicate alias shows "already taken"
- [ ] `abc` as URL shows a validation error
- [ ] `/this-code-does-not-exist` shows the error page
- [ ] Click limit 2: third open is blocked
- [ ] Disabled link stops working but keeps its clicks
