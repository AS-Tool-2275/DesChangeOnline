from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from destination_change_unified_flow import (
    PriorityRule,
    fmt_date,
    load_fwk3_from_production,
    normalize_pct,
    normalize_whse,
    parse_user_date,
    process_files,
    saturday_of_current_week,
)

st.set_page_config(
    page_title="Destination Change Unified Flow",
    page_icon="📦",
    layout="wide",
)

st.title("Destination Change Unified Flow")
st.caption("Streamlit version generated from the final unified Python flow.")

with st.expander("Quick guide", expanded=False):
    st.markdown(
        """
        **Upload 3 input files:**
        1. `PlanDetailTimeline.csv` raw export file
        2. `Production Schedule.csv` raw export file
        3. `DueDateCalc.xlsx`

        **Main logic:**
        - `F Wk3` is taken from Production Schedule where `S/F/P = F` only.
        - PlanDetailTimeline is converted from ETA to ETD using the selected warehouse offset mode.
        - The backend logic is preserved from `destination_change_unified_flow.py`, including:
          - `New SI = Original SI Before F Wk3 + F Wk3`
          - `New SI-SS = Original SI-SS Before F Wk3 + F Wk3`
        - The generated Excel output follows the final unified flow writer.
        """
    )

st.header("1) Upload input files")
col1, col2, col3 = st.columns(3)
with col1:
    plan_file = st.file_uploader("PlanDetailTimeline raw CSV", type=["csv"])
with col2:
    production_file = st.file_uploader("Production Schedule raw CSV", type=["csv"])
with col3:
    due_file = st.file_uploader("DueDateCalc Excel", type=["xlsx", "xlsm", "xls"])

st.header("2) Week setup")
def_current = saturday_of_current_week()
def_target = def_current + timedelta(days=14)

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    target_week_input = st.date_input("Target Week / Wk3", value=def_target)
with col2:
    current_week_input = st.date_input("Current Week", value=def_current)
with col3:
    offset_mode = st.selectbox(
        "ETA → ETD offset mode",
        options=["legacy_compatible", "due_date"],
        index=0,
        help="legacy_compatible keeps the current SI-SS_WANEK logic when available. due_date uses ceil(Delivery Days / 7).",
    )

target_week = target_week_input if isinstance(target_week_input, date) else parse_user_date(str(target_week_input))
current_week = current_week_input if isinstance(current_week_input, date) else parse_user_date(str(current_week_input))

st.header("3) Priority rules optional")
st.markdown(
    "Leave blank if there are no priority warehouses. "
    "**Value examples:** `50` = 50%, `0.5` = 50%, `1` = 100%, `100` = 100%."
)

priority_rules = {}
priority_table = pd.DataFrame(columns=["Whse", "Mode", "Value"])

if production_file is not None:
    # Save a temporary copy only to preview available warehouses for the priority UI.
    try:
        with tempfile.TemporaryDirectory() as preview_tmp:
            prod_preview_path = Path(preview_tmp) / production_file.name
            prod_preview_path.write_bytes(production_file.getvalue())
            f_preview, _ = load_fwk3_from_production(str(prod_preview_path), target_week)
            whse_options = sorted(
                f_preview["Whse"].dropna().astype(str).unique().tolist(),
                key=lambda x: (len(x), x),
            )
    except Exception as exc:
        whse_options = []
        st.warning(f"Could not preview warehouse list from Production Schedule yet: {exc}")

    default_rows = pd.DataFrame([
        {"Whse": "", "Mode": "SI", "Value": None},
    ])

    priority_table = st.data_editor(
        default_rows,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Whse": st.column_config.SelectboxColumn(
                "Whse",
                options=[""] + whse_options,
                help="Select a priority warehouse.",
            ),
            "Mode": st.column_config.SelectboxColumn(
                "Mode",
                options=["SI", "SS"],
                help="SI = cover toward SI = 0. SS = target SI / SS percentage.",
            ),
            "Value": st.column_config.NumberColumn(
                "Value",
                help="Examples: 50 = 50%, 0.5 = 50%, 1 = 100%, 100 = 100%.",
            ),
        },
        key="priority_rules_editor",
    )

    for _, row in priority_table.iterrows():
        whse = normalize_whse(row.get("Whse", ""))
        mode = str(row.get("Mode", "")).strip().upper()
        value = row.get("Value")
        if not whse or whse.lower() == "nan":
            continue
        if mode not in {"SI", "SS"}:
            continue
        if pd.isna(value):
            continue
        priority_rules[whse] = PriorityRule(whse=whse, mode=mode, value=normalize_pct(value))
else:
    st.info("Upload Production Schedule first if you want to select priority warehouses from the available list.")

st.header("4) Run and download")
output_name = st.text_input(
    "Output file name",
    value=f"destination_change_unified_{target_week.strftime('%Y%m%d')}.xlsx",
)

ready = plan_file is not None and production_file is not None and due_file is not None
run_clicked = st.button("Run full flow", type="primary", disabled=not ready)

if not ready:
    st.info("Please upload all 3 input files before running.")

if run_clicked:
    try:
        with st.spinner("Processing full Destination Change flow..."):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                plan_path = tmp_path / plan_file.name
                prod_path = tmp_path / production_file.name
                due_path = tmp_path / due_file.name
                output_path = tmp_path / output_name

                plan_path.write_bytes(plan_file.getvalue())
                prod_path.write_bytes(production_file.getvalue())
                due_path.write_bytes(due_file.getvalue())

                final_path = process_files(
                    plan_detail_csv=str(plan_path),
                    production_schedule_csv=str(prod_path),
                    due_date_calc_xlsx=str(due_path),
                    output_path=str(output_path),
                    target_week=target_week,
                    current_week=current_week,
                    priority_rules=priority_rules,
                    offset_mode=offset_mode,
                )
                final_bytes = Path(final_path).read_bytes()

        st.success("Done. Output Excel is ready.")
        st.download_button(
            label="Download Output Excel",
            data=final_bytes,
            file_name=Path(final_path).name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption(
            f"Target Week: {fmt_date(target_week)} | Current Week: {fmt_date(current_week)} | "
            f"Offset mode: {offset_mode} | Priority rules: {len(priority_rules)}"
        )
    except Exception as exc:
        st.error("The app encountered an error while processing the files.")
        st.exception(exc)
