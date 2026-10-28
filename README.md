# IPC-iQ: Infection Prevention Intelligence (local version)

A hospital infection prevention and control (IPC) and antimicrobial stewardship (AMS) app.
It runs on your own computer: a Python (FastAPI) server stores data in a SQLite file and
serves the web app.

> The figures loaded on first run are **synthetic demo data**. Thresholds and clinical
> definitions must be set and approved by the hospital's infection control team before real use.

## Requirements

- Python 3.9 or newer
- VS Code with the Python extension (optional, but makes it one click)

## Run it in VS Code

1. Open this folder in VS Code (**File → Open Folder…**, choose `ipc-iq`).
2. Open a terminal (**Terminal → New Terminal**) and create a virtual environment:

   Windows:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```
   macOS / Linux:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the two dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Start the server, either by pressing **F5** (uses `.vscode/launch.json`) or with:
   ```
   cd backend
   python app.py
   ```
5. Open **http://localhost:8000** in your browser.

On first start the server creates `backend/ipc.db` and loads the demo data.

## Trying it with more than one person

Records must be verified by someone other than the person who entered them. Use the
**Signed in as** box at the bottom right to switch between users (two are created for you,
and you can add more). Other computers on your network can't reach the server by default;
see "Sharing on a network" below.

## Inference, action taken and outcome

On the **Alerts** page each alert now shows:

- **Inference**: a suggested reading of what the data means, drafted by rules from the alert
  type. Use **Confirm inference** to edit it after case review; it is then marked as confirmed.
- **Action taken**: use **Record action taken** to log the type of action, who did it, the date
  and what was done.
- **Outcome**: once the next month's data is in, each action shows whether the same alert is
  still raised ("Still flagged") or not ("Improved"). If an alert comes back after earlier
  action, the earlier actions are listed under it.

All of this is stored with the alert's record and history, so it is part of the audit trail.

## Optional: AI features

The "Draft the agenda", "Write the summary" and "Draft a teaching note" buttons use the
Anthropic API. They stay hidden until you add a key:

1. Put your key in `.env` as `ANTHROPIC_API_KEY=...` (when using F5), or set it in the
   terminal before `python app.py`:
   - Windows PowerShell: `$env:ANTHROPIC_API_KEY="sk-ant-..."`
   - macOS / Linux: `export ANTHROPIC_API_KEY=sk-ant-...`
2. Restart the server.

The key stays on the server; the browser never sees it.

## Resetting the demo data

Stop the server, delete `backend/ipc.db`, and start it again. Or send a POST request to
`http://localhost:8000/api/reset-demo`.

To change the demo data, edit `backend/seed_generator.py`, run `python seed_generator.py`,
then delete `ipc.db` and restart.

## Project layout

```
ipc-iq/
├─ backend/
│  ├─ app.py               FastAPI server: document API, demo seeding, AI proxy, static files
│  ├─ seed_data.json       Demo data loaded on first run
│  └─ seed_generator.py    Regenerates seed_data.json
├─ frontend/
│  ├─ index.html           The whole app (HTML, CSS, JavaScript)
│  └─ local-runtime.js     Connects the app to the local server (database, users, AI, downloads)
├─ requirements.txt
└─ .vscode/launch.json     F5 runs the server
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/collections/{col}` | List documents in a collection |
| GET | `/api/collections/{col}/{id}` | Read one document |
| PUT | `/api/collections/{col}/{id}` | Create or replace a document |
| PATCH | `/api/collections/{col}/{id}` | Merge fields into an existing document |
| POST | `/api/collections/{col}` | Create a document with a new id |
| DELETE | `/api/collections/{col}/{id}` | Delete a document |
| GET | `/api/version` | Change counter the browser polls to pick up other users' edits |
| POST | `/api/ask` | Send a prompt to Claude (needs `ANTHROPIC_API_KEY`) |
| POST | `/api/reset-demo` | Wipe and reload the demo data |

Interactive API docs: http://localhost:8000/docs

## Sharing on a network

`app.py` listens on `127.0.0.1` (this computer only). To let others on the same network use
it, change `host="127.0.0.1"` to `host="0.0.0.0"` at the bottom of `app.py` and open
`http://<your-computer's-IP>:8000` on their devices.

**Do not do this with real patient data.** This local version has no passwords, no role-based
access and no encryption. Those must be added (see the SRS) before it holds real records.

## What this version is and isn't

It is a working prototype for demonstrating workflows and validating calculations with the
clinical team. Before production use it still needs authentication and role-based access,
HTTPS, backups, server-side validation of each record type, and clinical sign-off on the
surveillance definitions and thresholds.
