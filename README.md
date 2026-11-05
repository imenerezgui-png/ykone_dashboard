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

Brand timelines and their steps are stored separately in `data/timelines.json`.
Timeline progress is calculated from the steps marked as validated.
