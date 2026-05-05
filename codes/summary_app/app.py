from __future__ import annotations

import os
import base64
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_DIR = Path(__file__).parent
HAI_IMAGE = APP_DIR / "assets" / "hai1.png"

from charts import (
    ai_benefit_histogram,
    bar_by_protocol,
    case_outcomes_plot,
    case_protocol_delta_heatmap,
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
        "Interactive poster companion for a behavioral experiment on when AI advice should appear "
        "during cost-sensitive loan decision-making."
    )


NAV_ITEMS = [
    "Overview",
    "Protocol Comparator",
    "Human-First Revision",
    "Reliance Explorer",
    "Case Explorer",
]


def with_demo_flag(url: str) -> str:
    """Ensure the experiment link opens in safe demo mode."""
    if "?" in url:
        return url if "demo=true" in url else f"{url}&demo=true"
    return f"{url}?demo=true"


def render_overview_css() -> None:
    st.markdown(
        """
        <style>
        .overview-demo-card {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 16px;
            padding: 1.05rem 1.15rem;
            background: linear-gradient(135deg, rgba(20, 184, 166, 0.10), rgba(99, 102, 241, 0.08));
            margin: 0.4rem 0 1.05rem 0;
        }
        .overview-demo-title {
            font-size: 1.05rem;
            font-weight: 750;
            margin-bottom: 0.35rem;
        }
        .overview-demo-text {
            font-size: 0.94rem;
            line-height: 1.45;
            margin-bottom: 0.55rem;
        }
        .overview-muted {
            color: rgba(49, 51, 63, 0.68);
            font-size: 0.82rem;
        }

        .workflow-hero {
            margin: 0.85rem 0 1.15rem 0;
            padding: 1.05rem;
            border: 1px solid rgba(15, 23, 42, 0.13);
            border-radius: 18px;
            box-shadow: 0 14px 35px rgba(15, 23, 42, 0.07);
            overflow: hidden;
            background-color: #f8fafc;
        }
        .workflow-kicker {
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            color: #0f766e;
            margin-bottom: 0.8rem;
        }
        .workflow-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
        }
        .workflow-card {
            min-height: 148px;
            padding: 1.05rem;
            border-radius: 14px;
            border: 1px solid rgba(15, 23, 42, 0.13);
            background: rgba(255, 255, 255, 0.80);
            backdrop-filter: blur(5px);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .workflow-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.55rem;
        }
        .workflow-main {
            font-size: 0.92rem;
            color: #111827;
            line-height: 1.45;
            margin-bottom: 0.75rem;
        }
        .workflow-note {
            font-size: 0.78rem;
            color: #64748b;
            line-height: 1.4;
        }
        .concept-note {
            margin: -0.15rem 0 1.15rem 0;
            padding: 0.78rem 0.95rem;
            border-left: 4px solid #0f766e;
            background: rgba(15, 118, 110, 0.06);
            border-radius: 0.55rem;
            font-size: 0.98rem;
            line-height: 1.45;
        }
        @media (max-width: 900px) {
            .workflow-grid {
                grid-template-columns: 1fr;
            }
            .workflow-card {
                min-height: unset;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_demo_callout() -> None:
    """Place the platform demo where scanners will actually see it: the Overview."""
    demo_url = get_demo_url()
    left, right = st.columns([2.4, 1])
    with left:
        with st.container(border=True):
            st.markdown("#### Experience the decision task")
            st.write(
                "Try the same loan-review interface used in the experiment. "
                "The safe preview shows the three workflows without writing responses "
                "to the production study database."
            )
            st.caption("Independent Review · AI-Assisted Review · Sequential Review")
    with right:
        st.write("")
        st.write("")
        if demo_url:
            st.link_button(
                "Launch 3-minute demo",
                with_demo_flag(demo_url),
                type="primary",
                use_container_width=True,
            )
        else:
            warning("Demo link not configured yet.")

app_data = load_data()
trials = app_data.trials
participants = app_data.participants_raw
cases_df = case_summary(trials) if not trials.empty else pd.DataFrame()

with st.sidebar:
    st.markdown("### Human-AI Decision Explorer")
    st.caption("Poster companion app")
    st.caption("Lower cost and Brier score are better. Higher accuracy is better.")
    st.divider()
    st.markdown("### Filters")
    sample_mode = st.selectbox("Sample", ["All completers", "Exclude group_3 carryover check"], index=0)
    if "difficulty_tier" in trials.columns and not trials.empty:
        selected_tiers = st.multiselect("Difficulty", ["easy", "medium", "hard"], default=["easy", "medium", "hard"])
    else:
        selected_tiers = []

if "page_nav" not in st.session_state or st.session_state.page_nav not in NAV_ITEMS:
    st.session_state.page_nav = "Overview"
page = st.session_state.page_nav

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
        pills=[f"N={n_completed} completers", f"{n_trials:,} scored trials", "3 interaction protocols", f"{n_cases} loan cases"],
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
        "This is the cleanest within-trial evidence: participants first made an unaided judgment, then saw the AI-predicted default probability, then finalized their response.",
        pills=["Initial judgment → AI probability → final decision", f"N={switch.get('n', 0)} human-first trials"],
    )
elif page == "Reliance Explorer":
    hero(
        "Reliance Explorer",
        "Inspect how participants revised probability estimates toward the AI prediction and whether final decisions aligned with the threshold-implied action.",
        pills=["WOA available only in human-first", "Zero-inflated adjustment pattern"],
    )
elif page == "Case Explorer":
    hero(
        "Case Explorer",
        "Move from aggregate effects to individual loan cases. Inspect whether protocol effects are broad or driven by particular stimuli.",
        pills=[f"{view['case_id'].nunique()} cases in current filter", "τ = 1/6 cost-sensitive threshold"],
    )

# ─────────────────────────────────────────────────────────────────────────────
# Render Navigation
# ─────────────────────────────────────────────────────────────────────────────
try:
    nav_sel = st.pills("Navigate", NAV_ITEMS, default=page, key="nav_widget", label_visibility="collapsed")
except AttributeError:
    nav_sel = st.radio("Navigate", NAV_ITEMS, index=NAV_ITEMS.index(page), horizontal=True, key="nav_widget", label_visibility="collapsed")

if nav_sel and nav_sel != page:
    st.session_state.page_nav = nav_sel
    st.rerun()

def image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def render_protocol_workflow_background() -> None:
    """Render equal-height workflow cards inside a single tile with the image as a bottom visual band."""
    if HAI_IMAGE.exists():
        bg64 = image_to_base64(HAI_IMAGE)
        image_markup = f"<img class='workflow-bottom-image' src='data:image/png;base64,{bg64}' alt='Human and AI hands nearly touching' />"
    else:
        image_markup = ""

bg64 = image_to_base64(HAI_IMAGE) if HAI_IMAGE.exists() else ""

components.html(
    f'''
    <div class="workflow-wrap">
        <div class="workflow-hero">
            <div class="workflow-content">
                <div class="workflow-topline">STUDY WORKFLOWS</div>

                <div class="workflow-headline">Decision support, not decision replacement.</div>

                <div class="workflow-subtitle">
                    AI-supported decisions improved performance, but better outcomes still depend on active human judgment.
                    These workflows test whether the timing of AI advice changes decision quality and reliance.
                </div>

                <div class="workflow-grid">
                    <div class="workflow-card">
                        <div>
                            <div class="workflow-label">01</div>
                            <div class="workflow-title">Independent Review</div>
                            <div class="workflow-main">Human decides without AI support.</div>
                        </div>
                        <div class="workflow-note">Baseline condition for unaided decision quality.</div>
                    </div>

                    <div class="workflow-card">
                        <div>
                            <div class="workflow-label">02</div>
                            <div class="workflow-title">AI-Assisted Review</div>
                            <div class="workflow-main">AI default probability is shown before the judgment.</div>
                        </div>
                        <div class="workflow-note">Tests early advice exposure and possible anchoring.</div>
                    </div>

                    <div class="workflow-card">
                        <div>
                            <div class="workflow-label">03</div>
                            <div class="workflow-title">Sequential Review</div>
                            <div class="workflow-main">Human judges first, sees AI, then finalizes.</div>
                        </div>
                        <div class="workflow-note">Tests whether deliberation before advice improves revision quality.</div>
                    </div>
                </div>
            </div>

            <div class="workflow-art">
                <img
                    src="data:image/png;base64,{bg64}"
                    alt="Human and AI"
                    class="workflow-art-img"
                />
                <div class="workflow-art-fade"></div>
            </div>
        </div>
    </div>

    <style>
        html, body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #0f172a;
        }}

        .workflow-wrap {{
            box-sizing: border-box;
            width: 100%;
            padding: 0;
        }}

        .workflow-hero {{
            box-sizing: border-box;
            width: 100%;
            border: 1px solid rgba(15, 23, 42, 0.14);
            border-radius: 18px;
            box-shadow: 0 14px 35px rgba(15, 23, 42, 0.07);
            overflow: hidden;
            background: linear-gradient(180deg, #f8fbfb 0%, #eef5f4 100%);
        }}

        .workflow-content {{
            padding: 22px 22px 0 22px;
            position: relative;
            z-index: 2;
        }}

        .workflow-topline {{
            font-size: 11px;
            line-height: 1;
            font-weight: 800;
            letter-spacing: 0.13em;
            color: #0f766e;
            margin-bottom: 10px;
        }}

        .workflow-headline {{
            max-width: 720px;
            font-size: 22px;
            line-height: 1.15;
            font-weight: 850;
            margin-bottom: 8px;
        }}

        .workflow-subtitle {{
            max-width: 820px;
            font-size: 14px;
            line-height: 1.45;
            color: #334155;
            margin-bottom: 18px;
        }}

        .workflow-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            align-items: stretch;
        }}

        .workflow-card {{
            box-sizing: border-box;
            min-height: 145px;
            height: 100%;
            padding: 16px;
            border-radius: 15px;
            border: 1px solid rgba(15, 23, 42, 0.13);
            background: rgba(255, 255, 255, 0.92);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .workflow-label {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            height: 22px;
            min-width: 30px;
            padding: 0 8px;
            border-radius: 999px;
            background: rgba(15, 118, 110, 0.10);
            color: #0f766e;
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 9px;
        }}

        .workflow-title {{
            font-size: 18px;
            line-height: 1.15;
            font-weight: 850;
            margin-bottom: 8px;
        }}

        .workflow-main {{
            font-size: 14px;
            line-height: 1.4;
            color: #111827;
        }}

        .workflow-note {{
            margin-top: 14px;
            font-size: 12px;
            line-height: 1.35;
            color: #64748b;
        }}

        .workflow-art {{
            position: relative;
            width: calc(100% + 44px);
            height: 150px;
            margin: 10px -22px 0 -22px;
            overflow: hidden;
            background: #eef5f4;
        }}

        .workflow-art-img {{
            width: 100%;
            height: 100%;
            display: block;
            object-fit: cover;
            object-position: center 45%;
            opacity: 0.88;
            transform: scale(1.04);
        }}

        .workflow-art-fade {{
            position: absolute;
            inset: 0;
            background:
                linear-gradient(
                    to bottom,
                rgba(238, 245, 244, 1.00) 0%,
                rgba(238, 245, 244, 0.78) 18%,
                rgba(238, 245, 244, 0.30) 43%,
                rgba(238, 245, 244, 0.06) 74%,
                rgba(238, 245, 244, 0.00) 100%
            ),
            linear-gradient(
                to right,
                rgba(238, 245, 244, 0.90) 0%,
                rgba(238, 245, 244, 0.10) 13%,
                rgba(238, 245, 244, 0.00) 28%,
                rgba(238, 245, 244, 0.00) 72%,
            rgba(238, 245, 244, 0.10) 87%,
            rgba(238, 245, 244, 0.90) 100%
        );
    pointer-events: none;
    }}

        @media (max-width: 760px) {{
            .workflow-content {{
                padding: 16px 16px 0 16px;
            }}

            .workflow-grid {{
                grid-template-columns: 1fr;
            }}

            .workflow-card {{
                min-height: 118px;
            }}

            .workflow-art {{
                height: 100px;
            }}
        }}
    </style>
    ''',
    height=450,
    scrolling=False,
)

# ─────────────────────────────────────────────────────────────────────────────
# Overview
# ─────────────────────────────────────────────────────────────────────────────
if page == "Overview":
    render_overview_css()

    no_ai_cost = summary.loc[summary["protocol"] == "no_ai", "Mean cost"].squeeze() if "no_ai" in set(summary["protocol"]) else np.nan
    hf_cost = summary.loc[summary["protocol"] == "human_first", "Mean cost"].squeeze() if "human_first" in set(summary["protocol"]) else np.nan
    no_ai_acc = summary.loc[summary["protocol"] == "no_ai", "Accuracy"].squeeze() if "no_ai" in set(summary["protocol"]) else np.nan
    hf_acc = summary.loc[summary["protocol"] == "human_first", "Accuracy"].squeeze() if "human_first" in set(summary["protocol"]) else np.nan
    adjusted_pct = 1.0 - woa.get("zero_pct", np.nan) if woa.get("n", 0) and pd.notna(woa.get("zero_pct", np.nan)) else np.nan

    render_demo_callout()

    render_protocol_workflow_background()



    metric_cards(
        [
            {"label": "Decision cost", "value": f"no_ai {fmt_num(no_ai_cost)} → human_first {fmt_num(hf_cost)}", "note": "Mean trial cost; lower is better."},
            {"label": "Accuracy", "value": f"no_ai {fmt_num(no_ai_acc)} → human_first {fmt_num(hf_acc)}", "note": "Mean correctness across scored trials."},
            {"label": "Sequential corrections", "value": f"{switch.get('improved', 0)} improved vs {switch.get('worsened', 0)} worsened", "note": "Initial to final decision in human-first trials."},
            {"label": "Probability adjustment", "value": fmt_pct(adjusted_pct), "note": "Human-first trials with nonzero probability movement."},
        ]
    )

    finding(
        "AI-supported decisions reduced cost and improved accuracy relative to no-AI; "
        "human-first showed the strongest numerical pattern, but the timing contrast against AI-first was not statistically decisive."
    )

    col1, col2 = st.columns([1.1, 1])
    with col1:
        overview_metric = st.segmented_control(
            "Show",
            ["Decision cost", "Accuracy"],
            default="Decision cost",
            key="overview_bar_metric",
        )
        if overview_metric == "Accuracy":
            st.plotly_chart(
                bar_by_protocol(summary, "Accuracy", "Accuracy by protocol", lower_is_better=False),
                use_container_width=True,
                config={"displayModeBar": False},
                key="plot_overview_accuracy",
            )
            small_note("What to notice: both AI-supported protocols should be read against the no-AI baseline; higher accuracy is better.")
        else:
            st.plotly_chart(
                bar_by_protocol(summary, "Mean cost", "Decision cost by protocol", lower_is_better=True),
                use_container_width=True,
                config={"displayModeBar": False},
                key="plot_overview_cost",
            )
            small_note("What to notice: both AI-supported protocols should be read against the no-AI baseline; lower cost is better.")
    with col2:
        st.plotly_chart(
            switch_sankey(switch),
            use_container_width=True,
            config={"displayModeBar": False},
            key="plot_overview_sankey",
        )
        small_note("What to notice: sequential review directly shows whether AI exposure corrected or worsened initial judgments.")

    # ── Case × Protocol delta heatmap ─────────────────────────────────────────
    section_kicker("Where AI helped — case-by-case")
    heatmap_mode = st.segmented_control(
        "Show benefit as",
        ["Cost benefit", "Accuracy benefit", "Approval change"],
        default="Cost benefit",
        key="overview_heatmap_mode",
    )
    st.plotly_chart(
        case_protocol_delta_heatmap(view, mode=heatmap_mode or "Cost benefit"),
        use_container_width=True,
        config={"displayModeBar": False},
        key="plot_overview_delta_heatmap",
    )
    small_note(
        "Green = AI-supported protocol outperformed no-AI for that case. "
        "Red = no-AI was better. White = no difference. "
        "Switch the toggle above to inspect cost, accuracy, or approval-rate change."
    )

    small_note(
        "Use the sidebar filters for carryover sensitivity checks and difficulty-specific results. Use the top navigation for deeper protocol, reliance, and case-level analysis."
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

        finding("WOA did not differ meaningfully by whether the threshold-implied action agreed with the realized outcome.")

        adjusters_only = st.toggle("Show adjusters only", value=False)
        d_woa = woa["data"].copy()
        ai_correct_filter = st.selectbox("Threshold-implied action outcome agreement", ["All", "Action agreed with outcome", "Action disagreed with outcome"])
        if ai_correct_filter == "Action agreed with outcome":
            d_woa = d_woa[d_woa["ai_correct"] == 1]
        elif ai_correct_filter == "Action disagreed with outcome":
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
        small_note("Threshold-implied action outcome agreement is determined ex post from the realized loan outcome. It is useful behaviorally but should not be confused with probability calibration.")

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
            {"label": "AI-predicted default risk", "value": fmt_num(csum.get("pred_prob")), "note": f"Cost threshold τ={TAU:.3f}."},
            {"label": "True outcome", "value": "Default" if csum.get("y_true") == 1 else "Paid", "note": "Observed outcome for this historical loan."},
            {"label": "Threshold-implied action", "value": "Approve" if csum.get("optimal_dec") == 1 else "Reject", "note": "Derived from τ=1/6; not necessarily displayed as a binary recommendation."},
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
