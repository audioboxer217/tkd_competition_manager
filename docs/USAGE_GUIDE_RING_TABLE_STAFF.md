# TKD Competition Manager — Ring/Table Staff Guide

For scorekeepers and ring operators running live competition at an assigned ring.

---

## 1) Login and Open your scorekeeper screen
- Go to /admin or click **Admin Login** on the top-right of the main page.
- Sign in with your credentials.
- After a successful login you are redirected to the Admin Dashboard (/admin).
- Click the **Score Keeper** button for your Ring
- The page title shows **Scorekeeper Console** followed by your ring name and current event type.

---

## 2) Event tabs

At the top of the page are two tabs:

| Tab | Use for |
|-----|---------|
| **Kyorugi** | Sparring bracket matches |
| **Poomsae/Breaking** | Forms/breaking bracket matches and group score events |

Click the correct tab for the current event type. The active tab is highlighted.

---

## 3) Kyorugi match flow

Each match is shown as a card on screen. Work through them in match-number order.

### Step 1 — Identify the competitors

Each match card shows two sides:

- **Chung (Blue)**
- **Hong (Red)**

Confirm that the names shown match the athletes physically present at the ring before starting.

### Step 2 — Start the match

Click **Start** to set the match to `In Progress`.

> Only one match per ring can be `In Progress` at a time. If another match is already in progress, complete it first.

### Step 3 — Record the result

After the match ends, **select the winner** by tapping/clicking their side (Chung or Hong), then click the appropriate result button:

| Button | When to use |
|--------|------------|
| **Normal Win** | Standard victory (points, superiority, golden point, etc.) |
| **Disqualification** | One competitor is disqualified (gam-jeom, medical stoppage, etc.) |

> **Normal Win** and **Disqualification** are only enabled after a winner is selected. If neither button is clickable, make sure a winner side is highlighted first.

### Step 4 — Confirm advancement

After saving, verify that:
- The match card disappears (or updates its status).
- The next match in the bracket reflects the correct advancing athlete.

If the bracket does not advance correctly, **do not start the next match** — escalate to admin.

---

## 4) Poomsae/Breaking match flow

The **Poomsae/Breaking** tab shows all poomsae-type events assigned to your ring, ordered by their ring sequence number.

### Poomsae bracket matches

These look and behave exactly like Kyorugi match cards (Chung/Hong labels, Start → Normal Win / Disqualification flow).

### Poomsae group (score-based) divisions

These appear as score-entry tables, one per group division assigned to your ring. For each competitor:

1. Click **Start** to set the group to `In Progress`.
2. Enter or update the score (valid range: **0.000 – 10.000**).
3. Save each score — rankings update automatically.
4. Click **Complete** to set the group to `Completed`.

Division status is controlled either during division setup (via the ring assignment form in the admin interface) or by the scorekeeper using the **Reset**, **Start**, and **Complete** buttons; there is no separate status control on the admin score manage page.

---

## 5) Validation rules — when buttons are disabled

| Condition | Effect |
|-----------|--------|
| Either competitor is **TBD** (feeder match not yet complete) | Both **Normal Win** and **Disqualification** are permanently disabled for that card |
| No winner selected (neither Chung nor Hong highlighted) | Both **Normal Win** and **Disqualification** remain disabled |
| Another match in this ring is already `In Progress` | Do not start a new match until the current one is completed |

If you encounter a match that cannot be started or completed due to any of these conditions, escalate to the administrator.

---

## 6) When to escalate to admin

Stop and contact the on-duty administrator immediately if:

- The wrong competitor name is displayed on screen
- A match result will not save (error message appears)
- The bracket does not advance correctly after saving a result
- A match appears to have the wrong winner already saved
- A ring sequence conflict or "Unassigned" match number appears
- The division or ring assignment looks incorrect

**Escalation format:**
> "Ring [X], Division [Y], Match [Z]: [brief description of the issue]. Screen shows: [current status]. Needs admin action."

---

## 7) Ring open checklist

- [ ] Open the correct scorekeeper page (check ring number and event type tab)
- [ ] First match is visible and competitors look correct
- [ ] Only one match set to `In Progress` at a time
- [ ] Winner is selected before clicking **Normal Win** or **Disqualification**
- [ ] After each save, confirm the next match or bracket progression looks correct
