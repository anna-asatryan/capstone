from __future__ import annotations

import os
import base64
import textwrap
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

st.markdown(
    """
    <style>
    @media (max-width: 760px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-bottom: 7rem !important;
            padding-top: 1rem !important;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        h1 {
            font-size: 1.8rem !important;
            line-height: 1.15 !important;
        }
        h2, h3 {
            line-height: 1.2 !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)



def fmt_pct(x: float, digits: int = 1) -> str:
    return "—" if pd.isna(x) else f"{100*x:.{digits}f}%"


def fmt_num(x: float, digits: int = 3) -> str:
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


PLOTLY_PHONE_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "responsive": True,
}


def phone_safe_fig(fig, height: int | None = None):
    """Disable pan/zoom gestures and reduce mobile layout problems for Plotly figures."""
    try:
        fig.update_layout(dragmode=False)
        if height is not None:
            fig.update_layout(height=height)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        # Put legends below charts instead of on top of titles/plots on phones.
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="left",
                x=0,
                font=dict(size=10),
            ),
            margin=dict(l=48, r=18, t=62, b=78),
        )
    except Exception:
        pass
    return fig


def plotly_chart_safe(fig, *, key: str, height: int | None = None) -> None:
    st.plotly_chart(
        phone_safe_fig(fig, height=height),
        use_container_width=True,
        config=PLOTLY_PHONE_CONFIG,
        key=key,
    )


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



def render_overview_toc() -> None:
    """Compact table of contents for conference viewers scanning on phones."""
    section_kicker("Explore the evidence")
    cards = [
        ("Protocol Comparator", "Compare cost, accuracy, Brier score, approval rate, and paired participant-level differences."),
        ("Human-First Revision", "Inspect how unaided initial judgments changed after participants saw the AI probability."),
        ("Reliance Explorer", "Check probability movement toward AI and alignment with the threshold-implied action."),
        ("Case Explorer", "Move from averages to individual loan cases, including the case-by-protocol heatmap."),
    ]
    for page_name, description in cards:
        with st.container(border=True):
            left, right = st.columns([3.0, 1.0])
            with left:
                st.markdown(f"#### {page_name}")
                st.caption(description)
            with right:
                if st.button("Open", key=f"toc_{page_name}", use_container_width=True):
                    st.session_state.page_nav = page_name
                    st.rerun()

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


def render_protocol_workflow_phone_safe() -> None:
    """Compact responsive workflow section with a merged bottom image band."""
    bg_style = ""
    if HAI_IMAGE.exists():
        bg64 = image_to_base64(HAI_IMAGE)
        bg_style = f"background-image: url('data:image/png;base64,{bg64}');"

    st.markdown(
        """
        <style>
        .wf-shell {
            position: relative;
            overflow: hidden;
            margin: 0.55rem 0 1rem 0;
            border: 1px solid rgba(15, 23, 42, 0.12);
            border-radius: 18px;
            background: linear-gradient(180deg, #f8fbfb 0%, #eef5f4 100%);
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        }
        .wf-content {
            position: relative;
            z-index: 2;
            padding: 1rem 1rem 0 1rem;
        }
        .wf-kicker {
            font-size: 0.68rem;
            line-height: 1;
            font-weight: 800;
            letter-spacing: 0.13em;
            color: #0f766e;
            margin-bottom: 0.5rem;
        }
        .wf-title {
            font-size: 1.15rem;
            line-height: 1.15;
            font-weight: 850;
            color: #0f172a;
            margin-bottom: 0.45rem;
        }
        .wf-subtitle {
            font-size: 0.88rem;
            line-height: 1.45;
            color: #334155;
            margin-bottom: 0.8rem;
            max-width: 860px;
        }
        .wf-cards {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            position: relative;
            z-index: 3;
        }
        .wf-card {
            min-height: 112px;
            padding: 0.8rem 0.85rem;
            border-radius: 14px;
            border: 1px solid rgba(15, 23, 42, 0.10);
            background: rgba(255, 255, 255, 0.92);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-sizing: border-box;
        }
        .wf-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 28px;
            height: 20px;
            padding: 0 8px;
            border-radius: 999px;
            background: rgba(15, 118, 110, 0.10);
            color: #0f766e;
            font-size: 0.68rem;
            font-weight: 800;
            margin-bottom: 0.45rem;
        }
        .wf-card-title {
            font-size: 0.98rem;
            line-height: 1.18;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.35rem;
        }
        .wf-card-main {
            font-size: 0.84rem;
            line-height: 1.34;
            color: #111827;
            margin-bottom: 0.55rem;
        }
        .wf-card-note {
            font-size: 0.74rem;
            line-height: 1.3;
            color: #64748b;
        }
        .wf-band {
            position: relative;
            width: 100%;
            height: 118px;
            margin-top: -8px;
            background-color: #eef5f4;
            background-size: cover;
            background-position: center 54%;
            background-repeat: no-repeat;
            opacity: 1;
        }
        .wf-band-fade {
            position: absolute;
            inset: 0;
            background:
                linear-gradient(
                    to bottom,
                    rgba(238, 245, 244, 1.00) 0%,
                    rgba(238, 245, 244, 0.84) 14%,
                    rgba(238, 245, 244, 0.38) 42%,
                    rgba(238, 245, 244, 0.08) 72%,
                    rgba(238, 245, 244, 0.00) 100%
                ),
                linear-gradient(
                    to right,
                    rgba(238, 245, 244, 0.75) 0%,
                    rgba(238, 245, 244, 0.08) 15%,
                    rgba(238, 245, 244, 0.00) 32%,
                    rgba(238, 245, 244, 0.00) 68%,
                    rgba(238, 245, 244, 0.08) 85%,
                    rgba(238, 245, 244, 0.75) 100%
                );
        }
        @media (max-width: 760px) {
            .wf-shell {
                margin: 0.45rem 0 0.85rem 0;
            }
            .wf-content {
                padding: 0.85rem 0.85rem 0 0.85rem;
            }
            .wf-kicker {
                font-size: 0.64rem;
                margin-bottom: 0.42rem;
            }
            .wf-title {
                font-size: 1.02rem;
            }
            .wf-subtitle {
                font-size: 0.80rem;
                line-height: 1.38;
                margin-bottom: 0.65rem;
            }
            .wf-cards {
                display: flex;
                gap: 0.6rem;
                overflow-x: auto;
                overflow-y: hidden;
                padding: 0 0 0.2rem 0;
                scroll-snap-type: x proximity;
                -webkit-overflow-scrolling: touch;
            }
            .wf-cards::-webkit-scrollbar {
                display: none;
            }
            .wf-card {
                flex: 0 0 78%;
                min-width: 220px;
                min-height: 96px;
                scroll-snap-align: start;
                padding: 0.72rem;
            }
            .wf-card-title {
                font-size: 0.92rem;
            }
            .wf-card-main {
                font-size: 0.80rem;
                margin-bottom: 0.4rem;
            }
            .wf-card-note {
                font-size: 0.70rem;
            }
            .wf-band {
                height: 92px;
                background-position: center 58%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    html = textwrap.dedent(
        f"""
        <div class="wf-shell">
            <div class="wf-content">
                <div class="wf-kicker">STUDY WORKFLOWS</div>
                <div class="wf-title">Decision support, not decision replacement.</div>
                <div class="wf-subtitle">
                    AI-supported decisions improved performance, but better outcomes still depend on active human judgment.
                    The study compares three ways of timing AI advice.
                </div>

                <div class="wf-cards">
                    <div class="wf-card">
                        <div>
                            <div class="wf-badge">01</div>
                            <div class="wf-card-title">Independent Review</div>
                            <div class="wf-card-main">Human decides without AI support.</div>
                        </div>
                        <div class="wf-card-note">Baseline condition for unaided decision quality.</div>
                    </div>

                    <div class="wf-card">
                        <div>
                            <div class="wf-badge">02</div>
                            <div class="wf-card-title">AI-Assisted Review</div>
                            <div class="wf-card-main">AI default probability is shown before the judgment.</div>
                        </div>
                        <div class="wf-card-note">Tests early advice exposure and possible anchoring.</div>
                    </div>

                    <div class="wf-card">
                        <div>
                            <div class="wf-badge">03</div>
                            <div class="wf-card-title">Sequential Review</div>
                            <div class="wf-card-main">Human judges first, sees AI, then finalizes.</div>
                        </div>
                        <div class="wf-card-note">Tests whether deliberation before advice improves revision quality.</div>
                    </div>
                </div>
            </div>

            <div class="wf-band" style="{bg_style}">
                <div class="wf-band-fade"></div>
            </div>
        </div>
        """
    )

    # st.markdown can render nested indented HTML as a code block. st.html renders it as HTML.
    if hasattr(st, "html"):
        st.html(html)
    else:
        components.html(html, height=360, scrolling=False)
    if not HAI_IMAGE.exists():
        st.caption("Human–AI image not found. Expected: assets/hai1.png")


def case_protocol_delta_heatmap_vertical(trials: pd.DataFrame, mode: str = "Cost benefit"):
    """Phone-safe case × protocol heatmap: cases as rows, AI protocols as columns."""
    import plotly.graph_objects as go

    required = {"case_id", "protocol"}
    if trials.empty or not required.issubset(trials.columns):
        return go.Figure()

    d = trials.copy()
    if "case_position" not in d.columns:
        d["case_position"] = d["case_id"].astype(str)

    if mode == "Accuracy benefit":
        value_col = "correct"
        title_metric = "Accuracy benefit"
        subtitle = "Protocol accuracy minus no-AI accuracy"
    elif mode == "Approval change":
        value_col = "decision_final"
        title_metric = "Approval change"
        subtitle = "Protocol approval rate minus no-AI approval rate"
    else:
        value_col = "trial_cost"
        title_metric = "Cost benefit"
        subtitle = "No-AI cost minus protocol cost"

    if value_col not in d.columns:
        return go.Figure()

    agg = (
        d.groupby(["case_id", "case_position", "protocol"], dropna=False)
        .agg(value=(value_col, "mean"), n=(value_col, "count"))
        .reset_index()
    )

    optional_cols = [c for c in ["difficulty_tier", "pred_prob", "y_true"] if c in d.columns]
    if optional_cols:
        meta = d.groupby(["case_id"], dropna=False)[optional_cols].first().reset_index()
        agg = agg.merge(meta, on="case_id", how="left")

    base = agg[agg["protocol"] == "no_ai"][["case_id", "value"]].rename(columns={"value": "no_ai_value"})
    comp = agg[agg["protocol"].isin(["ai_first", "human_first"])].merge(base, on="case_id", how="left")

    if mode == "Cost benefit":
        comp["benefit"] = comp["no_ai_value"] - comp["value"]
    else:
        comp["benefit"] = comp["value"] - comp["no_ai_value"]

    comp["Protocol"] = comp["protocol"].map({"ai_first": "AI-first", "human_first": "Human-first"})
    comp["case_position_num"] = pd.to_numeric(comp["case_position"], errors="coerce")

    case_order_df = (
        comp[["case_id", "case_position", "case_position_num"]]
        .drop_duplicates()
        .sort_values(["case_position_num", "case_position"], na_position="last")
    )

    case_labels = []
    for _, r in case_order_df.iterrows():
        if pd.notna(r["case_position_num"]):
            case_labels.append(f"C{int(r['case_position_num'])}")
        else:
            case_labels.append(f"C{str(r['case_position'])}")

    comp["Case"] = comp["case_id"].astype(str).map(dict(zip(case_order_df["case_id"].astype(str), case_labels)))

    y_order = case_labels
    x_order = ["AI-first", "Human-first"]

    pivot = (
        comp.pivot_table(index="Case", columns="Protocol", values="benefit", aggfunc="mean")
        .reindex(index=y_order, columns=x_order)
    )

    hover = []
    for case in y_order:
        row = []
        for proto in x_order:
            rr = comp[(comp["Case"] == case) & (comp["Protocol"] == proto)]
            if rr.empty:
                row.append("No data<extra></extra>")
                continue
            r = rr.iloc[0]
            difficulty = r.get("difficulty_tier", "—")
            pred_prob = r.get("pred_prob", np.nan)
            y_true = r.get("y_true", "—")
            pred_txt = "—" if pd.isna(pred_prob) else f"{pred_prob:.3f}"
            outcome_txt = "Default" if y_true == 1 else "Paid" if y_true == 0 else "—"
            row.append(
                f"<b>{case}</b><br>"
                f"Protocol: {proto}<br>"
                f"Difficulty: {difficulty}<br>"
                f"AI risk: {pred_txt}<br>"
                f"Outcome: {outcome_txt}<br>"
                f"No-AI value: {r['no_ai_value']:.3f}<br>"
                f"Protocol value: {r['value']:.3f}<br>"
                f"Benefit: {r['benefit']:.3f}<extra></extra>"
            )
        hover.append(row)

    z = pivot.values
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=x_order,
            y=y_order,
            text=np.round(z, 2),
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate=hover,
            colorscale=[
                [0.00, "#dc2626"],
                [0.45, "#fee2e2"],
                [0.50, "#f8fafc"],
                [0.55, "#ccfbf1"],
                [1.00, "#0f766e"],
            ],
            zmid=0,
            colorbar=dict(title="Benefit", len=0.70, thickness=10),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"Where AI helped — {title_metric}<br><sup>{subtitle}</sup>",
            x=0.02,
            xanchor="left",
            font=dict(size=16),
        ),
        height=720,
        margin=dict(l=52, r=12, t=76, b=42),
        xaxis=dict(title="", side="top", tickfont=dict(size=12)),
        yaxis=dict(title="Loan case", autorange="reversed", tickfont=dict(size=11)),
    )
    return fig

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

    render_protocol_workflow_phone_safe()
    render_demo_callout()

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

    render_overview_toc()

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

    plotly_chart_safe(
        bar_by_protocol(summary, summary_col, f"{selected_metric} by protocol", lower_is_better=lower_better),
        key=f"plot_comp_bar_{selected_metric}",
    )

    if metric_col:
        plotly_chart_safe(
            paired_participant_plot(view, metric_col, f"Participant-level paired view: {selected_metric}"),
            key=f"plot_comp_paired_{selected_metric}",
        )
        section_kicker("Pairwise participant-level tests")
        tests = pairwise_protocol_tests(view, metric_col)
        tests_display = tests.copy()
        tests_display["Mean diff"] = tests_display["Mean diff"].map(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        tests_display["t"] = tests_display["t"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
        tests_display["p"] = tests_display["p"].map(format_p)
        st.dataframe(tests_display, use_container_width=True, hide_index=True)
    else:
        small_note("Brier score is shown once because it is computed at protocol level; paired participant-level tests are omitted to avoid sparse probability-quality claims.")

    section_kicker("Protocol summary table")
    show = summary.copy()
    for c in ["Accuracy", "Mean cost", "Excess cost", "Brier", "AI distance", "Approval rate", "Median RT (s)"]:
        if c in show:
            show[c] = show[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
    st.dataframe(show.drop(columns=["protocol"], errors="ignore"), use_container_width=True, hide_index=True)

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
        plotly_chart_safe(switch_sankey(switch, height=445), key="plot_hf_sankey", height=445)
    with col2:
        plotly_chart_safe(switch_matrix_heatmap(switch, height=445), key="plot_hf_heatmap", height=445)

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
        plotly_chart_safe(woa_histogram(d_woa, adjusters_only=adjusters_only), key="plot_reliance_woa")

    col1, col2 = st.columns([1.1, 1])
    with col1:
        plotly_chart_safe(reliance_stacked_bar(rel), key="plot_reliance_stacked")
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
            plotly_chart_safe(ai_benefit_histogram(benefit), key="plot_reliance_benefit")
            small_note("Participant subgroups are descriptive because they are defined using the AI-benefit outcome itself.")

# ─────────────────────────────────────────────────────────────────────────────
# Case Explorer
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Case Explorer":
    cases_current = case_summary(view)
    if cases_current.empty:
        warning("No case-level summary could be generated.")
        st.stop()

    plotly_chart_safe(case_scatter(cases_current), key="plot_case_scatter")


    section_kicker("Where AI helped — case-by-case")
    heatmap_mode = st.segmented_control(
        "Show benefit as",
        ["Cost benefit", "Accuracy benefit", "Approval change"],
        default="Cost benefit",
        key="case_heatmap_mode",
    )
    plotly_chart_safe(
        case_protocol_delta_heatmap_vertical(cases_current.merge(view, on="case_id", how="right") if False else view, mode=heatmap_mode or "Cost benefit"),
        key="plot_case_delta_heatmap_vertical",
        height=720,
    )
    small_note(
        "Green = AI-supported protocol outperformed no-AI for that case. Red = no-AI was better. White = no difference."
    )

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
        plotly_chart_safe(case_outcomes_plot(view, selected_case, metric=selected_metric), key="plot_case_outcomes")
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
