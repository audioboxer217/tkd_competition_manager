# TKD Competition Manager — Administrator Guide

For users managing tournament setup, bracket generation, and live operations.

---

## 1) Login and access

1. Go to `/login`.
2. Sign in with your credentials.
3. After a successful login you are redirected to the **Admin Dashboard** (`/admin`).

> All protected pages require an active session. If your session expires during an HTMX action, the app redirects you back to `/login` automatically.

---

## 2) Recommended setup workflow

Follow this order before competition begins:

1. Create rings
2. Create divisions (select event type: **Kyorugi** or **Poomsae/Breaking**)
3. Open each division's setup page and add competitors
4. For **Poomsae/Breaking** divisions: choose the event format (**📋 Group (Score-Based)** or **🏆 Bracket**)
5. Generate the bracket (bracket-style divisions)
6. Assign each division to a ring
7. Schedule match sequence numbers (bracket divisions)
8. Brief ring staff, then open scorekeeper pages
9. Monitor `/results` throughout the day

---

## 3) Ring management

### Admin Dashboard — Manage Rings panel

Located on the left panel of the **Admin Dashboard**.

| Action | How |
|--------|-----|
| Add a ring | Enter a name (e.g., `Ring 1`) and click **Add Ring** |
| Open scorekeeper for a ring | Click **Score Keeper** next to the ring name |
| Delete a ring | Click **Delete** next to the ring name (confirmation required) |

---

## 4) Division management

### Admin Dashboard — Manage Divisions panel

Located on the right panel of the **Admin Dashboard**.

Use the event tabs to switch between division lists:

- **Kyorugi** tab — sparring divisions
- **Poomsae/Breaking** tab — forms/breaking divisions

| Action | How |
|--------|-----|
| Add a division | Select the correct tab, enter a name, click **Add Division** |
| Open division setup | Click **Manage** next to the division name |
| Delete a division | Click **Delete** next to the division name (confirmation required; deletes all matches, scores, and competitors) |

---

## 5) Division setup page (`/admin/divisions/<id>/setup`)

### Rename the division

Click **Rename** next to the division heading to edit the name inline.

### Add Competitors section (left column)

Paste competitor names — one name per line — into the text area, then click **Add to Division**.

> Deleting a competitor clears all existing bracket matches for that division and forces bracket regeneration.

### Division Roster section (right column)

Shows the current competitor list. Use the position controls to reorder competitors before bracket generation.

### Bracket controls (bottom right, below Division Roster)

The bracket controls section changes based on division type and state.

#### Kyorugi divisions

| State | Controls shown |
|-------|----------------|
| No competitors yet | "Add competitors above, then generate the bracket." |
| Competitors added, no bracket | **Generate Bracket** button |
| Bracket exists | **Manage & Schedule Bracket** link + **Regenerate Bracket** button |

#### Poomsae/Breaking divisions — style not yet chosen

Two buttons are shown (selection is **permanent once made**):

| Button | Meaning |
|--------|---------|
| **📋 Group (Score-Based)** | Judges assign numeric scores; ranked by total |
| **🏆 Bracket** | Head-to-head bracket, same flow as Kyorugi |

#### Poomsae/Breaking — Group format (locked: 📋 Group 🔒)

Shows the **Ring Assignment** form with three fields:

| Field | Description |
|-------|-------------|
| Ring | Select an assigned ring or leave as **Unassigned** |
| Ring Order | Integer 1–99; shared sequence pool with bracket match numbers |
| Status | **Pending**, **In Progress**, or **Completed** |

Click **Save Assignment** to save.

After saving, two action links appear (when competitors are present):

| Link | Destination |
|------|-------------|
| **✏️ Manage Scores** | `/admin/divisions/<id>/score_manage` — enter/update judge scores |
| **🏅 View Results** | `/admin/divisions/<id>/group_results` — read-only ranked results |

#### Poomsae/Breaking — Bracket format (locked: 🏆 Bracket 🔒)

Same bracket controls as Kyorugi:

| State | Controls shown |
|-------|----------------|
| No bracket yet | **Generate Bracket** button |
| Bracket exists | **Manage & Schedule Bracket** link + **Regenerate Bracket** button |

---

## 6) Bracket generation

### Generate Bracket

Available when a division has competitors but no bracket.

- Click **Generate Bracket**.
- The system builds a power-of-two bracket automatically.
- Competitors with no opponent receive a **Completed (Bye)** and advance automatically.
- Requires at least 2 competitors; otherwise an error is shown.

### Regenerate Bracket

Available when a bracket already exists.

- Click **Regenerate Bracket**.
- **Warning:** A confirmation dialog appears. Proceeding deletes **all existing match data** for the division and rebuilds the bracket from scratch.

---

## 7) Bracket management page (`/admin/divisions/<id>/bracket_manage`)

Reached by clicking **Manage & Schedule Bracket** from the division setup page.

### Ring Assignment section

Use the **Ring** dropdown to assign this bracket's division to a ring, then click **Save**.

> If the ring is changed, all match sequence numbers and ring assignments for this division are cleared and must be re-entered.

### Scheduling matches

Each non-bye match card shows a **Seq (e.g. 1)** input while it is `Pending`.

- Enter a sequence number (1–99).
- Click **Save**.
- The system computes the final match number as `(ring_id × 100) + ring_sequence`.
- Duplicate sequence numbers within the same ring and event type are blocked.

---

## 8) Manage Scores page (`/admin/divisions/<id>/score_manage`)

For **Group (Score-Based)** poomsae divisions only.

- Shows all competitors with current score inputs.
- Enter or update a score for each competitor (valid range: 0.000 – 10.000).
- Rankings update automatically after each save.
- Division event status badge (Pending / In Progress / Completed) is displayed at the top.
- Use the **🏅 View Results** link (top right) to open the read-only results page.

---

## 9) Match and division status reference

### Match statuses

| Status | Meaning |
|--------|---------|
| `Pending` | Match not yet started; sequence number can be assigned |
| `In Progress` | Match is live; only one per ring at a time |
| `Completed` | Normal win recorded; bracket advanced |
| `Disqualification` | DQ result recorded; bracket advanced |
| `Completed (Bye)` | Auto-set when one slot has no opponent; hidden from bracket display |

### Poomsae division event statuses

| Status | Meaning |
|--------|---------|
| `Pending` | Division not yet started |
| `In Progress` | Division currently active at the ring |
| `Completed` | All scores recorded; results final |

---

## 10) Live operations and troubleshooting

### Tournament Results

`/results` — public-facing page showing all divisions and their brackets/placements. Tabs: **Kyorugi** / **Poomsae/Breaking**.

### Common issues

| Message / Symptom | Resolution |
|-------------------|------------|
| "Need at least 2 competitors…" | Add more competitors before generating the bracket |
| Cannot submit a result (TBD competitors) | Wait for the feeder match to complete and fill both slots |
| "Sequence already used" error | Choose a different ring sequence number (1–99) |
| "No ring assigned" for bracket | Set the division's ring in the bracket manage page first |
| Poomsae style picker not shown | Style is already locked; it cannot be changed after the first selection |
| Wrong winner already saved | Escalate immediately — do not attempt to override without understanding the full bracket state |

---

## 11) Logout

Click **Logout** (top right of the **Admin Dashboard**) to end your session.
