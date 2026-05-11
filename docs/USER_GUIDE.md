# TM1 PAW Tree — User Guide

## Overview

PAW Tree is a governance tool for IBM Planning Analytics Workspace. It gives administrators visibility into all PAW books — their structure, TM1 connections, usage history, and ownership — in a single interface.

---

## Interface Layout

```
┌─────────────────────────────────────────────────────┐
│  Logo  TM1 Workbook Tree   [stats]  [Refresh]  [🌙] │  ← Topbar
├──────────────────────────────────────────────────────┤
│  Tree │ Dashboard │ Activity                         │  ← Tab strip
├──────────────────────────────────────────────────────┤
│  [Search…]  [Group filter]                           │  ← Toolbar
├───────────────────────────┬──────────────────────────┤
│                           │                          │
│   Folder/Book Tree        │   Detail Drawer          │
│                           │   (opens on click)       │
│                           │                          │
└───────────────────────────┴──────────────────────────┘
```

---

## Tree Tab

### Navigating the Tree

- Click a **folder** to expand/collapse it. Click the folder name to open the detail drawer.
- Click a **book** to open its detail drawer.
- Books show a **page count** and the **cubes** referenced once tabs are loaded.
- A **🔒 lock icon** with an owner name indicates a private book.

### Book Icons

| Icon | Type | Description |
|------|------|-------------|
| Lined document | Dashboard | Classic PAW tabbed book |
| Grid/tile | Workbench | New PAW Workbench experience |

### Search

Type in the search box to filter by book name, folder name, or cube name. Results highlight matching books across all folders.

### Group Filter

Select a group from the dropdown to overlay that group's folder permissions on the tree. Books in folders where the group has no access are visually de-emphasised.

### Refresh Button

Click **Refresh** in the topbar to re-fetch the full tree from PAW. The button spins while loading and shows the last refresh time on completion.

---

## Book Detail Drawer

Click any book to open its detail panel on the right.

### Metadata Section

Shows book type, visibility (shared/private), owner, path, created/modified dates, last opened date, state, and permissions.

### Pages Section

Lists all tabs (pages) in the book. Each page card shows:
- Page name and number
- Number of TM1 views on the page
- Cube and view name(s) — expand a card to see full detail

Pages are loaded on demand when you first open a drawer. Subsequent opens use the cached data.

### Filtering by Cube/View

When a cube and view are selected in the toolbar (from the TM1 filter dropdowns), the drawer switches to show only the pages that use that specific view, plus the MDX definition of that view.

---

## Dashboard Tab

Provides a statistical overview of all PAW content:

- **Total books, folders, private books**
- **Orphaned books** — books with no recorded opens in the last 90 days, or never opened. These are candidates for archiving or deletion.
- **Private book inventory** — all private books by user, with creation and last-opened dates.

---

## Activity Tab

Tracks real PAW book usage over time using background polling.

### How It Works

Every N minutes (configurable), the server calls the PAW API and checks each book's `used_date`. When a book's date changes, it records a **hit** under a **session** for that user. Opens within 2 hours are grouped into the same session.

> Activity only reflects opens detectable via the PAW API's `used_date` field. Because PAW routes all connections through a shared admin account, user attribution depends on PAW's own `used_by` metadata.

### Controls

| Control | Description |
|---------|-------------|
| **On/Off toggle** | Enable or disable background polling |
| **Poll every** | Set the polling interval (5 / 15 / 30 / 60 min) |
| **Retain** | How many days of history to keep (30–365 days) |
| **Refresh** | Reload the stats display from the database |
| **Poll now** | Trigger an immediate poll of PAW |

### Stats Displayed

- **Sessions** — distinct usage sessions detected (grouped by 2-hour activity window)
- **Book opens** — total individual book open events recorded
- **Top books** — most-opened books with unique user counts
- **User activity** — sessions and book opens per user
- **Daily activity** — sessions per day over the last 30 days
- **Recent sessions** — last 20 sessions with books opened

### First Run

On first start, the activity store seeds a baseline snapshot without recording any hits. Activity is only recorded from that point forward when `used_date` changes.

---

## Administration

### Startup

```bash
cd ~/apps/tm1_paw_tree
source venv/bin/activate
python3 app.py
```

Server runs on port **8082** by default.

### Production (Gunicorn)

```bash
gunicorn -w 4 -b 0.0.0.0:8082 app:app
```

### Activity Database

The SQLite activity database is stored at `activity/activity.db`. It is excluded from version control. To reset activity history, stop the server and delete the file — it will be recreated on next startup.

### Logs

The server logs to stdout. Key log lines:

```
Activity poll: 10 books, 1 new sessions, 3 new hits
PAW tree built successfully
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Tree shows "Failed to load" | PAW or Authentik unreachable | Check `.env` credentials and network access to PAW/Authentik |
| Book drawer shows no pages | Book content inaccessible or book has no TM1 widgets | Expected for text-only books |
| Activity shows all books opened | Old database from before lazy-load fix | Delete `activity/activity.db` and restart |
| Changes in PAW not showing after refresh | PAW server-side cache | Click Refresh — the app now sends `Cache-Control: no-cache` headers |
