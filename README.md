# Destination Change Streamlit App

Files in this package:

- `destination_change_streamlit_app.py` - Streamlit UI entry point
- `destination_change_unified_flow.py` - final backend flow provided by the user
- `requirements.txt` - dependencies for local or Streamlit Cloud deployment

Run locally:

```bash
pip install -r requirements.txt
streamlit run destination_change_streamlit_app.py
```

Upload these 3 inputs in the app:

1. PlanDetailTimeline raw CSV
2. Production Schedule raw CSV
3. DueDateCalc Excel (Data Administrator -> Product Planners --> Expected Expected Delivery Date Calculation)

Then choose Target Week, Current Week, offset mode, optional priority rules, run, and download the Excel output.
