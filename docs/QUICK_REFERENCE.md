# TKD Competition Manager — Event-Day Quick Reference

One-page checklists for all roles during a live tournament.

---

## Administrator

### Pre-competition setup
- [ ] Log in at `/login` → redirected to **Admin Dashboard** (`/admin`)
- [ ] Create rings (**Manage Rings** panel → **Add Ring**)
- [ ] Create Kyorugi divisions (**Kyorugi** tab → **Add Division**)
- [ ] Create Poomsae/Breaking divisions (**Poomsae/Breaking** tab → **Add Division**)
- [ ] Open each division → click **Manage** → division setup page
- [ ] Add competitors (**Add Competitors** → paste names → **Add to Division**)
- [ ] For Poomsae/Breaking: choose format — **📋 Group (Score-Based)** or **🏆 Bracket** (permanent, cannot be changed)
- [ ] Generate bracket for bracket-style divisions → **Generate Bracket**
- [ ] Assign ring:
  - Bracket divisions: **Manage & Schedule Bracket** → **Ring Assignment** → **Save**
  - Group divisions: **Save Assignment** in the Ring Assignment form
- [ ] Schedule match sequence numbers (1–99) in bracket manage page → **Save**
- [ ] Verify `/results` loads correctly
- [ ] Brief ring staff on their URLs

### Live operations
- [ ] Monitor ring progress via scorekeeper and results pages
- [ ] Resolve escalated data issues promptly
- [ ] Avoid regenerating brackets while matches are in progress
- [ ] Track any corrections made during the event

### Closeout
- [ ] All divisions showing `Completed`
- [ ] Final placements verified at `/results`
- [ ] Any incomplete or disputed matches resolved
- [ ] Log out

---

## Ring / Table Staff

### Opening the ring
- [ ] Open `/ring/<ring_id>/scorekeeper?event_type=kyorugi` or `?event_type=poomsae`
- [ ] Confirm the correct tab is active (**Kyorugi** or **Poomsae/Breaking**)
- [ ] First match visible with correct competitor names

### Every kyorugi match
- [ ] Confirm **Chung (Blue)** and **Hong (Red)** names match athletes present
- [ ] Click **Start** → match moves to `In Progress`
- [ ] After match ends, select winner (tap Chung or Hong side)
- [ ] Click **Normal Win** (standard result) or **Disqualification** (DQ result)
- [ ] Confirm match card updates and bracket advances correctly

### Every poomsae bracket match
- [ ] Same flow as kyorugi: **Start** → select winner → **Normal Win** / **Disqualification**

### Poomsae group scoring
- [ ] Enter score for each competitor (0.000 – 10.000)
- [ ] Save — rankings update automatically

### Escalate immediately if
- [ ] Wrong competitor name displayed
- [ ] Result will not save
- [ ] Bracket does not advance after saving
- [ ] Sequence conflict or "Unassigned" match appears
- [ ] Any TBD competitor that should be filled

---

## Volunteers

### Start of shift
- [ ] Confirm on-duty administrator contact
- [ ] Know your assigned area (check-in / ring support / runner)
- [ ] Understand escalation process before competition starts

### During competition
- [ ] Verify athlete names before directing to ring
- [ ] Call up athletes in the order given by ring staff
- [ ] Report no-shows/late arrivals to ring staff immediately
- [ ] Escalate data discrepancies to admin (do not guess or self-correct)

### Do not
- [ ] Enter or edit match results
- [ ] Change bracket structure or sequence numbers
- [ ] Submit competitor information without admin instruction

---

## Status Reference

### Match statuses

| Status | Meaning |
|--------|---------|
| `Pending` | Not yet started; sequence can be assigned |
| `In Progress` | Currently live at the ring |
| `Completed` | Normal win recorded; bracket advanced |
| `Disqualification` | DQ result recorded; bracket advanced |
| `Completed (Bye)` | Auto-assigned when no opponent; hidden from bracket display |

### Poomsae division event statuses

| Status | Meaning |
|--------|---------|
| `Pending` | Division not yet started |
| `In Progress` | Division currently active |
| `Completed` | All scores recorded; results final |

---

## Fast Escalation Template

Use this when reporting an issue to admin:

> **"Ring [X], Division [Y], Match [Z]: [brief issue].  
> Screen shows: [current status / what is displayed].  
> Requested action: [what needs to be corrected]."**

---

## Key URLs

| Page | URL |
|------|-----|
| Landing / Live View | `/` |
| Login | `/login` |
| Admin Dashboard | `/admin` |
| Scorekeeper Console | `/ring/<ring_id>/scorekeeper?event_type=kyorugi` or `?event_type=poomsae` |
| Tournament Results | `/results` |
