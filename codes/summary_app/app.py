from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from charts import (
    ai_benefit_histogram,
    bar_by_protocol,
    case_outcomes_plot,
    case_scatter,
    difficulty_protocol_plot,
    paired_participant_plot,
    reliance_stacked_bar,
    switch_matrix_heatmap,
    switch_sankey,
    woa_histogram,
)
from components import case_card, finding, hero, load_css, metric_cards, section_kicker, small_note, warning
from data_loader import load_data
from metrics import (
    PROTOCOL_LABELS,
    PROTOCOLS,
    TAU,
    brier_score,
    case_summary,
    format_p,
    human_first_switches,
    pairwise_protocol_tests,
    protocol_summary,
    reliance_decomposition,
    woa_summary,
)

st.set_page_config(
    page_title="Human-AI Decision Explorer",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)
load_css()


def fmt_pct(x: float, digits: int = 1) -> str:
    return "—" if pd.isna(x) else f"{100*x:.{digits}f}%"


def fmt_num(x: float, digits: int = 3) -> str:
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


def get_demo_url() -> str | None:
    # Works both locally and on Streamlit Cloud.
    try:
        if "demo_url" in st.secrets:
            return st.secrets["demo_url"]
        if "summary_app" in st.secrets and "demo_url" in st.secrets["summary_app"]:
            return st.secrets["summary_app"]["demo_url"]
    except Exception:
        pass
    return os.getenv("SUMMARY_APP_DEMO_URL") or os.getenv("EXPERIMENT_DEMO_URL") or "https://capstone-study.streamlit.app/?demo=true"


def get_landing_note() -> str:
    return (
        "Interactive companion to the poster: inspect protocol effects, human-first decision revisions, "
        "reliance behavior, and case-level outcomes without exposing raw participant identities."
    )


app_data = load_data()
trials = app_data.trials
participants = app_data.participants_raw
cases_df = case_summary(trials) if not trials.empty else pd.DataFrame()

with st.sidebar:
    st.markdown("### Human-AI Decision Explorer")
    st.caption("Poster companion app")
    st.caption("Lower cost and Brier score are better. Higher accuracy is better.")

if "page_nav" not in st.session_state:
    st.session_state.page_nav = "Overview"
page = st.session_state.page_nav

with st.expander("Filters", expanded=False):
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        sample_mode = st.selectbox("Sample", ["All completers", "Exclude group_3 carryover check"], index=0)
    with f_col2:
        if "difficulty_tier" in trials.columns and not trials.empty:
            selected_tiers = st.multiselect("Difficulty", ["easy", "medium", "hard"], default=["easy", "medium", "hard"])
        else:
            selected_tiers = []

if app_data.warnings:
    for w in app_data.warnings:
        warning(w)

view = trials.copy()
if sample_mode == "Exclude group_3 carryover check" and "participant_group" in view.columns:
    view = view[view["participant_group"] != "group_3"].copy()
if selected_tiers and "difficulty_tier" in view.columns:
    view = view[view["difficulty_tier"].astype(str).isin(selected_tiers)].copy()

if view.empty:
    hero("Human-AI Decision Explorer", "No analysis data found. Run from the capstone repo root or deploy with artifacts/db_exports available.")
    st.stop()

summary = protocol_summary(view)
switch = human_first_switches(view)
woa = woa_summary(view)
rel = reliance_decomposition(view)

# ─────────────────────────────────────────────────────────────────────────────
# Render Hero (Header)
# ─────────────────────────────────────────────────────────────────────────────
if page == "Overview":
    n_completed = len(app_data.completed_ids)
    n_trials = len(view)
    n_cases = view["case_id"].nunique() if "case_id" in view.columns else np.nan
    hero(
        "Human-AI Decision Explorer",
        get_landing_note(),
        pills=[f"N={n_completed} completers", f"{n_trials:,} scored trials", "3 advice protocols", f"{n_cases} loan cases"],
    )
elif page == "Protocol Comparator":
    hero(
        "Protocol Comparator",
        "Compare the three interaction protocols across cost, accuracy, probability quality, convergence toward AI, and response behavior.",
        pills=[sample_mode, ", ".join(selected_tiers) if selected_tiers else "All difficulty tiers"],
    )
elif page == "Human-First Revision":
    hero(
        "Human-First Revision Explorer",
        "This is the cleanest within-trial evidence: participants first made an unaided judgment, then saw AI advice, then finalized their response.",
        pills=["Initial judgment → AI advice → final decision", f"N={switch.get('n', 0)} human-first trials"],
    )
elif page == "Reliance Explorer":
    hero(
        "Reliance Explorer",
        "Inspect how participants used AI advice: whether they followed recommendations, overrode them, or revised probability estimates toward the model.",
        pills=["WOA available only in human-first", "Zero-inflated reliance pattern"],
    )
elif page == "Case Explorer":
    hero(
        "Case Explorer",
        "Move from aggregate effects to individual loan cases. Inspect whether protocol effects are broad or driven by particular stimuli.",
        pills=[f"{view['case_id'].nunique()} cases in current filter", "τ = 1/6 cost-sensitive threshold"],
    )
elif page == "Platform Demo":
    hero(
        "Platform Demo / Preview",
        "The behavioral platform is the instrument used to collect decisions. For poster viewers, link only to a safe demo that does not write to the real study database.",
        pills=["Demo mode", "No real participant rows", "3 sample trials only"],
    )

# ─────────────────────────────────────────────────────────────────────────────
# Render Navigation
# ─────────────────────────────────────────────────────────────────────────────
try:
    nav_sel = st.pills("Navigate", ["Overview", "Protocol Comparator", "Human-First Revision", "Reliance Explorer", "Case Explorer", "Platform Demo"], default=page, key="nav_widget", label_visibility="collapsed")
except AttributeError:
    nav_sel = st.radio("Navigate", ["Overview", "Protocol Comparator", "Human-First Revision", "Reliance Explorer", "Case Explorer", "Platform Demo"], index=["Overview", "Protocol Comparator", "Human-First Revision", "Reliance Explorer", "Case Explorer", "Platform Demo"].index(page), horizontal=True, key="nav_widget", label_visibility="collapsed")

if nav_sel and nav_sel != page:
    st.session_state.page_nav = nav_sel
    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Overview
# ─────────────────────────────────────────────────────────────────────────────
if page == "Overview":

    no_ai_cost = summary.loc[summary["protocol"] == "no_ai", "Mean cost"].squeeze() if "no_ai" in set(summary["protocol"]) else np.nan
    hf_cost = summary.loc[summary["protocol"] == "human_first", "Mean cost"].squeeze() if "human_first" in set(summary["protocol"]) else np.nan
    no_ai_acc = summary.loc[summary["protocol"] == "no_ai", "Accuracy"].squeeze() if "no_ai" in set(summary["protocol"]) else np.nan
    hf_acc = summary.loc[summary["protocol"] == "human_first", "Accuracy"].squeeze() if "human_first" in set(summary["protocol"]) else np.nan

    metric_cards(
        [
            {"label": "Cost reduction", "value": f"no_ai {fmt_num(no_ai_cost)} → human_first {fmt_num(hf_cost)}", "note": "Mean trial cost"},
            {"label": "Accuracy", "value": f"no_ai {fmt_num(no_ai_acc)} → human_first {fmt_num(hf_acc)}", "note": "Mean accuracy"},
            {"label": "Human-first switch", "value": f"{switch.get('improved', 0)} improved vs {switch.get('worsened', 0)} worsened", "note": "Initial to final decision"},
            {"label": "WOA", "value": f"{fmt_pct(woa.get('zero_pct', np.nan))} no adjustment", "note": "Weight of advice"},
        ]
    )

    finding(
        "AI-supported decisions reduced cost and improved accuracy relative to no-AI; the direct AI-first vs human-first timing contrast was directional but not decisive."
    )

    col1, col2 = st.columns([1.15, 1])
    with col1:
        st.plotly_chart(bar_by_protocol(summary, "Mean cost", "Decision cost by protocol", lower_is_better=True), use_container_width=True, config={"displayModeBar": False}, key="plot_overview_cost")
    with col2:
        st.plotly_chart(bar_by_protocol(summary, "Accuracy", "Accuracy by protocol", lower_is_better=False), use_container_width=True, config={"displayModeBar": False}, key="plot_overview_accuracy")

    col3, col4 = st.columns([1, 1])
    with col3:
        st.plotly_chart(switch_sankey(switch), use_container_width=True, config={"displayModeBar": False}, key="plot_overview_sankey")
    with col4:
        if woa.get("n", 0):
            metric_cards(
                [
                    {"label": "WOA trials", "value": f"{woa['n']}", "note": "Human-first trials where AI moved the information set."},
                    {"label": "No adjustment", "value": fmt_pct(woa["zero_pct"]), "note": "Exact WOA = 0."},
                    {"label": "Adjusters", "value": f"{woa['adjuster_n']}", "note": f"Median WOA among adjusters: {woa['adjuster_median']:.3f}."},
                    {"label": "AI threshold", "value": f"τ={TAU:.3f}", "note": "Cost-sensitive approve/reject cutoff."},
                ]
            )
        st.plotly_chart(difficulty_protocol_plot(view, "correct"), use_container_width=True, config={"displayModeBar": False}, key="plot_overview_diff")

    small_note(
        "This app intentionally emphasizes interactive detail rather than repeating the poster. "
        "Use the sidebar to inspect carryover sensitivity and difficulty-specific results."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Protocol Comparator
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Protocol Comparator":

    metric_options = {
        "Mean cost": ("trial_cost", "Mean cost", True),
        "Accuracy": ("correct", "Accuracy", False),
        "Brier score": (None, "Brier", True),
        "Probability distance from AI": ("prob_dist", "AI distance", True),
        "Approval rate": ("decision_final", "Approval rate", False),
        "Excess cost": ("cost_excess", "Excess cost", True),
    }
    selected_metric = st.segmented_control("Metric", list(metric_options.keys()), default="Mean cost")
    metric_col, summary_col, lower_better = metric_options[selected_metric]

    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.plotly_chart(bar_by_protocol(summary, summary_col, f"{selected_metric} by protocol", lower_is_better=lower_better), use_container_width=True, config={"displayModeBar": False}, key=f"plot_comp_bar_{selected_metric}")
    with col2:
        if metric_col:
            st.plotly_chart(paired_participant_plot(view, metric_col, f"Participant-level paired view: {selected_metric}"), use_container_width=True, config={"displayModeBar": False}, key=f"plot_comp_paired_{selected_metric}")
        else:
            st.plotly_chart(bar_by_protocol(summary, summary_col, f"{selected_metric} by protocol", lower_is_better=True), use_container_width=True, config={"displayModeBar": False}, key=f"plot_comp_bar_alt_{selected_metric}")

    section_kicker("Pairwise participant-level tests")
    if metric_col:
        tests = pairwise_protocol_tests(view, metric_col)
        tests_display = tests.copy()
        tests_display["Mean diff"] = tests_display["Mean diff"].map(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        tests_display["t"] = tests_display["t"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
        tests_display["p"] = tests_display["p"].map(format_p)
        st.dataframe(tests_display, use_container_width=True, hide_index=True)
    else:
        small_note("Brier score is computed at protocol level; paired participant-level tests are omitted here to avoid sparse per-participant probability-quality claims.")

    section_kicker("Protocol summary table")
    show = summary.copy()
    for c in ["Accuracy", "Mean cost", "Excess cost", "Brier", "AI distance", "Approval rate", "Median RT (s)"]:
        if c in show:
            show[c] = show[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
    st.dataframe(show.drop(columns=["protocol"], errors="ignore"), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# Human-First Revision
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Human-First Revision":
    if not switch.get("n"):
        warning("No human-first initial/final decision data are available.")
        st.stop()

    metric_cards(
        [
            {"label": "Improved", "value": f"{switch.get('improved', 0)}", "note": "Initial wrong → final correct."},
            {"label": "Worsened", "value": f"{switch.get('worsened', 0)}", "note": "Initial correct → final wrong."},
            {"label": "Net gain", "value": f"+{switch.get('net_gain', 0)}", "note": "Improved minus worsened trials."},
            {"label": "Sign test", "value": format_p(switch.get("sign_p", np.nan)), "note": "Among trials that changed correctness."},
        ]
    )
    finding(f"**{switch.get('improved', 0)} improved vs {switch.get('worsened', 0)} worsened.** Net gain: +{switch.get('net_gain', 0)} corrected trials.")

    col1, col2 = st.columns([1.15, 1])
    with col1:
        st.plotly_chart(switch_sankey(switch, height=445), use_container_width=True, config={"displayModeBar": False}, key="plot_hf_sankey")
    with col2:
        st.plotly_chart(switch_matrix_heatmap(switch, height=445), use_container_width=True, config={"displayModeBar": False}, key="plot_hf_heatmap")

    section_kicker("Revision paths")
    summary_switch = switch["summary"].copy()
    summary_switch["Percent"] = summary_switch["Percent"].map(lambda x: f"{100*x:.1f}%")
    st.dataframe(summary_switch, use_container_width=True, hide_index=True)

    if "difficulty_tier" in switch.get("data", pd.DataFrame()).columns:
        section_kicker("Revision by difficulty")
        h = switch["data"].copy()
        h["path"] = np.select(
            [
                (h["correct_init"] == 1) & (h["correct_final"] == 1),
                (h["correct_init"] == 0) & (h["correct_final"] == 1),
                (h["correct_init"] == 0) & (h["correct_final"] == 0),
                (h["correct_init"] == 1) & (h["correct_final"] == 0),
            ],
            ["Stayed correct", "Improved", "Stayed wrong", "Worsened"],
            default="Other",
        )
        path_tab = pd.crosstab(h["difficulty_tier"], h["path"], normalize="index").reset_index()
        st.dataframe(path_tab, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# Reliance Explorer
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Reliance Explorer":
    if not woa.get("n"):
        warning("WOA data are unavailable because initial probability estimates were not found.")
    else:
        adjusted_pct = 1.0 - woa.get("zero_pct", 0) if pd.notna(woa.get("zero_pct")) else np.nan
        metric_cards(
            [
                {"label": "No adjustment", "value": fmt_pct(woa.get("zero_pct", np.nan)), "note": f"{woa.get('zero_n', 0)} exact-zero WOA trials."},
                {"label": "Adjusted", "value": fmt_pct(adjusted_pct), "note": "Moved toward AI."},
                {"label": "Adjuster median", "value": fmt_num(woa.get("adjuster_median")), "note": "Conditional on adjustment."},
            ]
        )

        finding("WOA did not differ meaningfully when AI was correct vs wrong.")

        adjusters_only = st.toggle("Show adjusters only", value=False)
        d_woa = woa["data"].copy()
        ai_correct_filter = st.selectbox("AI correctness filter", ["All", "AI correct", "AI wrong"])
        if ai_correct_filter == "AI correct":
            d_woa = d_woa[d_woa["ai_correct"] == 1]
        elif ai_correct_filter == "AI wrong":
            d_woa = d_woa[d_woa["ai_correct"] == 0]
        st.plotly_chart(woa_histogram(d_woa, adjusters_only=adjusters_only), use_container_width=True, config={"displayModeBar": False}, key="plot_reliance_woa")

    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.plotly_chart(reliance_stacked_bar(rel), use_container_width=True, config={"displayModeBar": False}, key="plot_reliance_stacked")
    with col2:
        if not rel.empty:
            rel_show = rel.drop(columns=["protocol"], errors="ignore").copy()
            for c in rel_show.columns:
                if c != "Protocol":
                    rel_show[c] = rel_show[c].map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
            st.dataframe(rel_show, use_container_width=True, hide_index=True)
        small_note("AI correctness here is defined ex post from the observed case outcome. It is useful behaviorally but should not be confused with probability calibration.")

    # Optional participant benefit if available.
    benefit_path = app_data.root / "artifacts" / "analysis" / "tables" / "ai_benefit_heterogeneity.csv"
    if benefit_path.exists():
        benefit = pd.read_csv(benefit_path)
        if "ai_benefit_accuracy" in benefit.columns:
            st.plotly_chart(ai_benefit_histogram(benefit), use_container_width=True, config={"displayModeBar": False}, key="plot_reliance_benefit")
            small_note("Participant subgroups are descriptive because they are defined using the AI-benefit outcome itself.")

# ─────────────────────────────────────────────────────────────────────────────
# Case Explorer
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Case Explorer":
    cases_current = case_summary(view)
    if cases_current.empty:
        warning("No case-level summary could be generated.")
        st.stop()

    st.plotly_chart(case_scatter(cases_current), use_container_width=True, config={"displayModeBar": False}, key="plot_case_scatter")

    labels = []
    for _, r in cases_current.iterrows():
        pos = int(r["case_position"]) if pd.notna(r.get("case_position")) else r["case_id"]
        tier = r.get("difficulty_tier", "unknown")
        pp = r.get("pred_prob", np.nan)
        labels.append(f"Case {pos} · {tier} · p={pp:.3f}" if pd.notna(pp) else f"Case {pos} · {tier}")
    selected_label = st.selectbox("Select a case", labels)
    selected_idx = labels.index(selected_label)
    selected_case = cases_current.iloc[selected_idx]["case_id"]
    csum = cases_current.iloc[selected_idx]

    metric_cards(
        [
            {"label": "AI default risk", "value": fmt_num(csum.get("pred_prob")), "note": f"Cost threshold τ={TAU:.3f}."},
            {"label": "True outcome", "value": "Default" if csum.get("y_true") == 1 else "Paid", "note": "Observed outcome for this historical loan."},
            {"label": "Optimal decision", "value": "Approve" if csum.get("optimal_dec") == 1 else "Reject", "note": "Based on τ = C_FP/(C_FP+C_FN)."},
            {"label": "Mean case cost", "value": fmt_num(csum.get("mean_cost")), "note": "Across current filter."},
        ]
    )

    col1, col2 = st.columns([1.1, 1])
    with col1:
        selected_metric = st.selectbox("Case metric", ["trial_cost", "correct", "decision_final", "prob_dist"], format_func={"trial_cost": "Cost", "correct": "Accuracy", "decision_final": "Approval rate", "prob_dist": "AI distance"}.get)
        st.plotly_chart(case_outcomes_plot(view, selected_case, metric=selected_metric), use_container_width=True, config={"displayModeBar": False}, key="plot_case_outcomes")
    with col2:
        case_rows = view[view["case_id"].astype(str) == str(selected_case)]
        proto_tab = case_rows.groupby("protocol").agg(
            Trials=("decision_final", "count"),
            Accuracy=("correct", "mean"),
            Cost=("trial_cost", "mean"),
            Approval=("decision_final", "mean"),
            AI_distance=("prob_dist", "mean"),
        ).reindex(PROTOCOLS).reset_index()
        proto_tab["Protocol"] = proto_tab["protocol"].map(PROTOCOL_LABELS)
        for col in ["Accuracy", "Cost", "Approval", "AI_distance"]:
            proto_tab[col] = proto_tab[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        with st.expander("View Case Outcomes Table"):
            st.dataframe(proto_tab[["Protocol", "Trials", "Accuracy", "Cost", "Approval", "AI_distance"]], use_container_width=True, hide_index=True)

    # Display case metadata if available.
    if not app_data.cases.empty and "case_id" in app_data.cases.columns:
        case_meta = app_data.cases[app_data.cases["case_id"].astype(str) == str(selected_case)]
        if not case_meta.empty:
            section_kicker("Loan case metadata")
            meta = case_meta.iloc[0]
            useful_cols = [c for c in ["loan_amnt", "term", "int_rate", "dti", "revol_util", "home_ownership", "purpose", "log_annual_inc", "credit_history_years", "difficulty_tier", "pred_prob", "y_true"] if c in meta.index]
            if useful_cols:
                with st.expander("View Case Metadata Table"):
                    st.dataframe(pd.DataFrame({"Field": useful_cols, "Value": [meta[c] for c in useful_cols]}), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# Platform Demo
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Platform Demo":
    demo_url = get_demo_url()
    if demo_url:
        if "?" in demo_url:
            if "demo=true" not in demo_url:
                demo_url += "&demo=true"
        else:
            demo_url += "?demo=true"
            
        st.markdown(
            "This link opens a **3-minute safe preview** of the decision platform. "
            "It skips onboarding and data collection so you can safely try the three protocol conditions "
            "(Independent Review, AI-Assisted Review, and Sequential Review) without contaminating the production database."
        )
        st.link_button("Try the 3-minute demo", demo_url, type="primary", use_container_width=False)
        finding("Poster viewers scanning the QR code should be directed to this demo URL, rather than the real experiment link.")
    else:
        warning("Demo link not configured yet.")

    st.subheader("Why this companion app exists")
    st.markdown(
        """
        The poster gives the compressed research story. This app gives judges a way to inspect evidence behind the story: protocol comparisons, human-first revisions, reliance distributions, and individual loan cases.
        """
    )
