# Ykone Task Dispatch

Internal job dispatching platform for the Ykone creative team.
Manage jobs, debriefs, deadlines and progress from a single monochrome typewriter workspace.

## Run locally

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Data

When Supabase Storage is configured, jobs and timelines are stored as private
JSON objects named `planning.json` and `timelines.json` in the configured
bucket. Local `data/*.json` files are ignored in that mode and are not migrated
or modified. Without Supabase secrets, the app continues to use local JSON.

To configure Supabase Storage, add this to Streamlit Cloud's **App settings →
Secrets**, or locally to `.streamlit/secrets.toml`:

```toml
[supabase]
url = "https://<project-ref>.supabase.co"
service_key = "<server-side Supabase service key>"
bucket = "ykone_dashboard"
```

Use either the project API URL (`https://<project-ref>.supabase.co`) or the S3
endpoint (`https://<project-ref>.storage.supabase.co/storage/v1/s3`). The app
normalizes the S3 hostname to the project API host for Storage REST requests.
The service key is privileged and must never be committed or shared. Keep the
Streamlit app restricted to authorized users. The bucket must already exist
and be accessible to that key. The app verifies bucket access when a session
starts. If settings are invalid or the bucket is unreachable, the dashboard
stays available in local JSON mode and the status indicator turns red; changes
in local mode will not sync to Supabase. If a Storage read or write fails during
use, the app also switches to local JSON, displays the error, and marks the
connection as disconnected instead of stopping the dashboard.

The Storage bucket is separate from the Postgres database; this setup stores
JSON objects in Storage and does not create database tables.

Timeline progress is calculated from the steps marked as validated. Once all
steps are validated, weekly steps remain visible for seven days, then move to
the Timeline Stats tab and reset for the next cycle. Due cycles are checked
hourly while the dashboard is open and whenever it is opened.
