# Ykone Task Dispatch

Internal job dispatching platform for the Ykone creative team.
Manage jobs, debriefs, deadlines and progress from a single monochrome typewriter workspace.

## Run locally

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Data

Jobs are stored in `data/planning.json` and can be seeded/refreshed by importing
`PLANNING ykone.xlsx` from the sidebar.

Brand timelines and archived step stats are stored in `data/timelines.json`.
Timeline progress is calculated from the steps marked as validated. Once all
steps are validated, weekly steps remain visible for seven days, then move to
the Timeline Stats tab and reset for the next cycle. Due cycles are checked
hourly while the dashboard is open and whenever it is opened.
