from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html

PALETTE = {
    "ink": "#19222f",
    "sand": "#f6f2e8",
    "paper": "#fffdf8",
    "accent": "#d77a2f",
    "teal": "#1f7a8c",
    "red": "#b5473a",
    "gold": "#b6952c",
    "blue": "#4a90d9",
}

PROTOCOL_COLORS = {
    "no_ai": PALETTE["blue"],
    "ai_first": PALETTE["accent"],
    "human_first": PALETTE["teal"],
}

PROTOCOL_LABELS = {
    "no_ai": "No AI",
    "ai_first": "AI First",
    "human_first": "Human First",
}

STATUS_CONFIG: dict[str, dict[str, str]] = {
    "supported": {"bg": "rgba(31,122,140,0.12)", "color": "#155b67", "label": "Supported"},
    "not_supported": {"bg": "rgba(181,71,58,0.12)", "color": "#7b261f", "label": "Not Supported"},
    "underpowered": {"bg": "rgba(182,149,44,0.12)", "color": "#6b560e", "label": "Underpowered"},
    "pending": {"bg": "rgba(107,110,114,0.10)", "color": "#4a4d52", "label": "Pending"},
}

_HYPOTHESES_FALLBACK = [
    {
        "hypothesis": "H1",
        "label": "AI assistance reduces decision cost",
        "metric": "mean_cost",
        "comparison": "no_ai vs ai_first",
        "status": "pending",
        "interpretation": "Awaiting participant data.",
    },
    {
        "hypothesis": "H2",
        "label": "Human-first revision improves outcomes vs no AI",
        "metric": "mean_cost",
        "comparison": "no_ai vs human_first",
        "status": "pending",
        "interpretation": "Awaiting participant data.",
    },
    {
        "hypothesis": "H3",
        "label": "Over-reliance: participants follow AI even when AI is incorrect",
        "metric": "follow_ai_rate when model_correct=0",
        "comparison": "human_first, AI-incorrect cases",
        "status": "pending",
        "interpretation": "Awaiting participant data.",
    },
    {
        "hypothesis": "H4",
        "label": "AI access improves probability calibration",
        "metric": "brier_score",
        "comparison": "no_ai vs ai_first vs human_first",
        "status": "pending",
        "interpretation": "Awaiting participant data.",
    },
    {
        "hypothesis": "H5",
        "label": "AI correctness moderates reliance rate",
        "metric": "follow_ai_rate",
        "comparison": "correct vs incorrect AI cases in human_first",
        "status": "pending",
        "interpretation": "Awaiting participant data.",
    },
]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _awaiting(detail: str = "") -> html.Div:
    children: list = [
        html.Div("Awaiting participant data", className="awaiting-title"),
        html.P(
            "This section will populate after participant exports are collected "
            "and `python run.py` is run.",
            className="awaiting-body",
        ),
    ]
    if detail:
        children.append(html.P(detail, className="awaiting-hint"))
    return html.Div(children, className="awaiting-panel")


def _section_header(title: str, subtitle: str = "") -> html.Div:
    items: list = [html.H2(title, className="section-title")]
    if subtitle:
        items.append(html.P(subtitle, className="section-subtitle"))
    return html.Div(items, className="section-header")


def _fmt(val: Any, fmt: str = ".3f", fallback: str = "—") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return fallback
    try:
        return format(float(val), fmt)
    except Exception:
        return fallback


def _stat_card(label: str, value: str, note: str = "") -> html.Div:
    children: list = [
        html.Div(label, className="stat-label"),
        html.Div(value, className="stat-value"),
    ]
    if note:
        children.append(html.Div(note, className="stat-note"))
    return html.Div(children, className="stat-card")


def _chart_layout(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=30),
        font=dict(family="Iowan Old Style, Palatino Linotype, serif", size=13),
    )
    return fig


def _empty_fig() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def _graph(fig: go.Figure) -> dcc.Graph:
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Tab 1: Executive Findings
# ---------------------------------------------------------------------------

def _hypothesis_card(row: dict) -> html.Div:
    status = str(row.get("status", "pending"))
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["pending"])

    effect_str = _fmt(row.get("effect_size"))
    ci_lo = _fmt(row.get("ci_lower"))
    ci_hi = _fmt(row.get("ci_upper"))
    p_str = _fmt(row.get("p_value"))
    interp = row.get("interpretation", "Awaiting participant data.")

    ci_text = f"[{ci_lo}, {ci_hi}]" if ci_lo != "—" and ci_hi != "—" else "—"

    stats_row = None
    if status not in ("pending",) and effect_str != "—":
        stats_row = html.Div(
            [
                html.Span(f"d = {effect_str}", className="hyp-stat"),
                html.Span(f"95% CI {ci_text}", className="hyp-stat"),
                html.Span(f"p = {p_str}", className="hyp-stat"),
            ],
            className="hyp-stats-row",
        )

    children: list = [
        html.Div(
            [
                html.Span(row["hypothesis"], className="hyp-id"),
                html.Span(
                    cfg["label"],
                    className="hyp-badge",
                    style={"background": cfg["bg"], "color": cfg["color"]},
                ),
            ],
            className="hyp-header",
        ),
        html.Div(row["label"], className="hyp-label"),
    ]
    if stats_row is not None:
        children.append(stats_row)
    children.append(html.Div(interp, className="hyp-interp"))

    return html.Div(children, className=f"hyp-card hyp-{status}")


def _executive_stats_row(bundle: dict) -> html.Div:
    summary = bundle["summary"]
    overview = summary.get("overview", {})
    tables = bundle["tables"]

    n_participants = "—"
    n_trials = "—"

    pc = tables.get("participants_clean")
    tc = tables.get("trials_clean")
    if pc is not None and not pc.empty:
        n_participants = str(len(pc))
    elif summary.get("participant_exports"):
        n_participants = str(summary["participant_exports"].get("completed_participants", "—"))

    if tc is not None and not tc.empty:
        n_trials = str(len(tc))

    n_cases = str(overview.get("final_cases", "—"))
    blocks = str(overview.get("blocks", "—"))

    return html.Div(
        [
            _stat_card("Participants", n_participants, "completed"),
            _stat_card("Scored Trials", n_trials, "across all protocols"),
            _stat_card("Cases", n_cases, "in frozen design"),
            _stat_card("Blocks", blocks, "protocols × groups"),
        ],
        className="stats-row",
    )


def build_executive_tab(bundle: dict) -> html.Div:
    hyp_df = bundle["tables"].get("hypothesis_summary")
    if hyp_df is not None and not hyp_df.empty:
        hyp_cards = [_hypothesis_card(row) for row in hyp_df.to_dict(orient="records")]
    else:
        hyp_cards = [_hypothesis_card(h) for h in _HYPOTHESES_FALLBACK]

    return html.Div(
        [
            _section_header(
                "Executive Findings",
                "Participant characteristics, protocol balance, and hypothesis test results.",
            ),
            _executive_stats_row(bundle),
            html.Div(
                [
                    html.H3("Hypothesis Tests", className="subsection-title"),
                    html.Div(hyp_cards, className="hyp-grid"),
                ],
                className="panel",
            ),
        ],
        className="tab-content",
    )


# ---------------------------------------------------------------------------
# Tab 2: Protocol Comparison
# ---------------------------------------------------------------------------

def _protocol_bar(
    df: pd.DataFrame, col: str, title: str, yaxis_label: str
) -> go.Figure:
    fig = go.Figure()
    for proto in ["no_ai", "ai_first", "human_first"]:
        sub = df[df["protocol"] == proto]
        if sub.empty or col not in sub.columns:
            continue
        val = float(sub[col].iloc[0])
        fig.add_trace(
            go.Bar(
                x=[PROTOCOL_LABELS.get(proto, proto)],
                y=[val],
                name=PROTOCOL_LABELS.get(proto, proto),
                marker_color=PROTOCOL_COLORS.get(proto, "#888"),
                showlegend=False,
            )
        )
    fig.update_layout(title=title, yaxis_title=yaxis_label)
    return _chart_layout(fig)


def build_protocol_tab(bundle: dict) -> html.Div:
    tables = bundle["tables"]
    po = tables.get("protocol_outcomes")
    cal = tables.get("calibration_by_protocol")

    header = _section_header(
        "Protocol Comparison",
        "Decision cost, accuracy, optimality, and probability calibration by AI protocol.",
    )

    if not bundle["has_participant_data"] or po is None or po.empty:
        return html.Div([header, _awaiting()], className="tab-content")

    charts = [
        html.Div([_graph(_protocol_bar(po, "mean_cost", "Mean Decision Cost ($/trial)", "Cost ($)"))], className="panel"),
        html.Div([_graph(_protocol_bar(po, "mean_accuracy", "Decision Accuracy by Protocol", "Accuracy"))], className="panel"),
        html.Div([_graph(_protocol_bar(po, "mean_cost_vs_optimal", "Excess Cost vs Optimal Policy ($/trial)", "$ above optimal"))], className="panel"),
    ]
    if cal is not None and not cal.empty:
        charts.append(html.Div([_graph(_protocol_bar(cal, "brier_score", "Brier Score by Protocol (lower = better)", "Brier Score"))], className="panel"))
        charts.append(html.Div([_graph(_protocol_bar(cal, "mean_absolute_error", "Probability Estimate MAE by Protocol", "MAE"))], className="panel"))

    display_cols = [
        c for c in [
            "protocol", "n_trials", "n_participants", "mean_accuracy",
            "mean_cost", "mean_optimal_cost", "mean_cost_vs_optimal",
        ]
        if c in po.columns
    ]
    table = dash_table.DataTable(
        data=po[display_cols].round(3).to_dict(orient="records"),
        columns=[{"name": c.replace("_", " ").title(), "id": c} for c in display_cols],
        style_table={"overflowX": "auto"},
        style_cell={"padding": "8px 12px", "fontFamily": "Iowan Old Style, serif", "fontSize": "13px"},
        style_header={"fontWeight": "700", "background": "#f6f2e8", "borderBottom": "2px solid #dfd5c2"},
    )

    return html.Div(
        [
            header,
            html.Div(charts, className="panel-grid"),
            html.Div(
                [html.H3("Protocol Summary Table", className="subsection-title"), table],
                className="panel",
            ),
        ],
        className="tab-content",
    )


# ---------------------------------------------------------------------------
# Tab 3: Reliance & Revision
# ---------------------------------------------------------------------------

def _revision_paths_figure(revision_df: pd.DataFrame) -> go.Figure:
    path_labels = {
        "A→A": "Approve → Approve",
        "A→R": "Approve → Reject",
        "R→R": "Reject → Reject",
        "R→A": "Reject → Approve",
    }
    path_colors = {
        "A→A": PALETTE["blue"],
        "A→R": PALETTE["red"],
        "R→R": PALETTE["teal"],
        "R→A": PALETTE["accent"],
    }

    paths = revision_df.get("path", pd.Series([], dtype=str)).tolist()
    rates = revision_df.get("rate", pd.Series([], dtype=float)).tolist()
    ns = revision_df.get("n", pd.Series([], dtype=int)).tolist()
    deltas = revision_df.get("mean_cost_delta", pd.Series([], dtype=float)).tolist()

    hover = [
        f"{path_labels.get(p, p)}<br>n={n}<br>rate={r:.1%}<br>cost delta ${d:+.0f}"
        for p, n, r, d in zip(paths, ns, rates, deltas)
    ]

    fig = go.Figure(
        go.Bar(
            x=[path_labels.get(p, p) for p in paths],
            y=rates,
            marker_color=[path_colors.get(p, "#888") for p in paths],
            hovertext=hover,
            hoverinfo="text",
        )
    )
    fig.update_layout(
        title="Decision Revision Paths (human_first)",
        yaxis_title="Proportion of trials",
        yaxis_tickformat=".0%",
    )
    return _chart_layout(fig)


def _cost_delta_figure(revision_df: pd.DataFrame) -> go.Figure:
    if "mean_cost_delta" not in revision_df.columns or "path" not in revision_df.columns:
        return _empty_fig()
    revisions = revision_df[revision_df["path"].isin(["A→R", "R→A"])].copy()
    if revisions.empty:
        return _empty_fig()

    path_labels = {"A→R": "Approve → Reject", "R→A": "Reject → Approve"}
    colors = [
        PALETTE["teal"] if d < 0 else PALETTE["red"]
        for d in revisions["mean_cost_delta"]
    ]
    fig = go.Figure(
        go.Bar(
            x=[path_labels.get(p, p) for p in revisions["path"]],
            y=revisions["mean_cost_delta"].tolist(),
            marker_color=colors,
            hovertemplate="%{x}<br>Avg cost delta: $%{y:+.0f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#9a9a9a")
    fig.update_layout(
        title="Cost Impact of Revisions (negative = revision saved money)",
        yaxis_title="Mean cost change ($)",
    )
    return _chart_layout(fig)


def build_reliance_tab(bundle: dict) -> html.Div:
    tables = bundle["tables"]
    rel = tables.get("reliance_summary")
    rev = tables.get("revision_paths")

    header = _section_header(
        "Reliance & Revision",
        "AI follow rates, override rates, and revision path analysis for the human_first protocol.",
    )

    if not bundle["has_participant_data"]:
        return html.Div([header, _awaiting()], className="tab-content")

    children: list = [header]

    if rel is not None and not rel.empty:
        stat_items = []
        for col, label in [
            ("revision_rate", "Overall Revision Rate"),
            ("revised_toward_reject_rate", "Revised → Reject"),
            ("revised_toward_approve_rate", "Revised → Approve"),
        ]:
            if col in rel.columns:
                val = float(rel[col].iloc[0])
                stat_items.append(_stat_card(label, f"{val:.1%}"))
        if stat_items:
            children.append(html.Div(stat_items, className="stats-row"))

    if rev is not None and not rev.empty:
        children.append(
            html.Div(
                [
                    html.Div([_graph(_revision_paths_figure(rev))], className="panel"),
                    html.Div([_graph(_cost_delta_figure(rev))], className="panel"),
                ],
                className="panel-grid",
            )
        )
    else:
        children.append(
            html.Div(
                [html.P("Revision path data not available for this run.", className="empty-state")],
                className="panel",
            )
        )

    return html.Div(children, className="tab-content")


# ---------------------------------------------------------------------------
# Tab 4: Case Explorer
# ---------------------------------------------------------------------------

def build_cases_tab(bundle: dict) -> html.Div:
    tables = bundle["tables"]
    final_cases = tables.get("final_cases")
    case_summary = tables.get("case_level_summary")

    header = _section_header(
        "Case Explorer",
        "Loan features, AI predictions, and participant response statistics for all 18 experimental cases.",
    )

    if final_cases is None or final_cases.empty:
        return html.Div([header, _awaiting("Frozen case design data is missing.")], className="tab-content")

    if case_summary is not None and not case_summary.empty:
        display = case_summary.copy()
    else:
        display = final_cases.copy()

    always_cols = [
        c for c in [
            "case_id", "block", "difficulty_tier", "pred_prob", "y_true",
            "correct", "model_optimal", "purpose", "loan_amnt", "int_rate",
        ]
        if c in display.columns
    ]
    participant_cols = [
        c for c in [
            "n_observations", "approve_rate", "accuracy_rate",
            "mean_prob_estimate", "follow_ai_rate", "override_rate", "mean_cost",
        ]
        if c in display.columns
    ]
    show_cols = always_cols + participant_cols

    display = display[show_cols].copy()
    for col in display.select_dtypes(include="float").columns:
        display[col] = display[col].round(3)

    col_labels = {
        "case_id": "Case", "block": "Block", "difficulty_tier": "Difficulty",
        "pred_prob": "AI Prob", "y_true": "Default", "correct": "AI Correct",
        "model_optimal": "AI Optimal", "purpose": "Purpose",
        "loan_amnt": "Amount ($)", "int_rate": "Rate (%)",
        "n_observations": "N Obs", "approve_rate": "Approve Rate",
        "accuracy_rate": "Accuracy", "mean_prob_estimate": "Mean Est",
        "follow_ai_rate": "Follow AI", "override_rate": "Override",
        "mean_cost": "Mean Cost ($)",
    }

    table = dash_table.DataTable(
        data=display.to_dict(orient="records"),
        columns=[{"name": col_labels.get(c, c), "id": c} for c in show_cols],
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "padding": "8px 10px",
            "fontFamily": "Iowan Old Style, serif",
            "fontSize": "13px",
            "textAlign": "left",
        },
        style_header={
            "fontWeight": "700",
            "background": "#f6f2e8",
            "borderBottom": "2px solid #dfd5c2",
        },
        style_data_conditional=[
            {"if": {"filter_query": "{y_true} = 1"}, "color": PALETTE["red"]},
            {"if": {"filter_query": "{correct} = 0"}, "fontStyle": "italic"},
        ],
        page_size=18,
        tooltip_header={c: {"value": col_labels.get(c, c)} for c in show_cols},
    )

    note = ""
    if not participant_cols:
        note = (
            "Participant columns (Approve Rate, Follow AI, etc.) appear once "
            "participant exports are collected and `python run.py` is run."
        )

    return html.Div(
        [
            header,
            html.Div(
                [table, html.P(note, className="empty-state")] if note else [table],
                className="panel",
            ),
        ],
        className="tab-content",
    )


# ---------------------------------------------------------------------------
# Tab 5: Reproducibility
# ---------------------------------------------------------------------------

def _design_calibration_figure(calibration: pd.DataFrame | None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, 1], y=[0, 1],
            mode="lines",
            line={"color": "#b9b4aa", "dash": "dash"},
            name="Perfect calibration",
        )
    )
    if calibration is not None and not calibration.empty:
        x_col = next((c for c in ["mean_pred_prob", "mean_prob"] if c in calibration.columns), None)
        y_col = next((c for c in ["observed_rate", "observed_default_rate"] if c in calibration.columns), None)
        if x_col and y_col:
            fig.add_trace(
                go.Scatter(
                    x=calibration[x_col], y=calibration[y_col],
                    mode="lines+markers",
                    line={"color": PALETTE["teal"], "width": 3},
                    marker={"size": 10, "color": PALETTE["accent"]},
                    name="ML model (candidate pool)",
                )
            )
    fig.update_layout(
        title="ML Model Calibration (Candidate Pool)",
        xaxis_title="Mean predicted probability",
        yaxis_title="Observed default rate",
    )
    return _chart_layout(fig)


def _difficulty_figure(difficulty: pd.DataFrame | None) -> go.Figure:
    if difficulty is None or difficulty.empty or "difficulty_tier" not in difficulty.columns:
        return _empty_fig()
    value_cols = [c for c in ["default_rate", "model_accuracy", "model_optimal_agreement"] if c in difficulty.columns]
    if not value_cols:
        return _empty_fig()

    fig = go.Figure()
    colors = [PALETTE["accent"], PALETTE["teal"], PALETTE["red"]]
    for i, col in enumerate(value_cols):
        fig.add_trace(
            go.Bar(
                x=difficulty["difficulty_tier"].tolist(),
                y=difficulty[col].tolist(),
                name=col.replace("_", " ").title(),
                marker_color=colors[i % len(colors)],
            )
        )
    fig.update_layout(title="Difficulty Tier Profiles", barmode="group", yaxis_title="Rate")
    return _chart_layout(fig)


def _protocol_rotation_figure(protocol_design: pd.DataFrame | None) -> go.Figure:
    if protocol_design is None or protocol_design.empty:
        return _empty_fig()
    try:
        pivot = protocol_design.pivot(index="participant_group", columns="block", values="protocol")
    except Exception:
        return _empty_fig()
    protocol_order = {"no_ai": 0, "human_first": 1, "ai_first": 2}
    encoded = pivot.replace(protocol_order)
    fig = go.Figure(
        data=go.Heatmap(
            z=encoded.values,
            x=list(encoded.columns),
            y=list(encoded.index),
            text=pivot.values,
            texttemplate="%{text}",
            colorscale=[[0.0, "#f2d5c4"], [0.5, "#f0bf8f"], [1.0, "#c4661f"]],
            showscale=False,
        )
    )
    fig.update_layout(title="Protocol Rotation (Latin Square)")
    return _chart_layout(fig)


def build_reproducibility_tab(bundle: dict) -> html.Div:
    summary = bundle["summary"]
    tables = bundle["tables"]
    warnings = summary.get("warnings", [])
    manifest = summary.get("selection_manifest", {})
    overview = summary.get("overview", {})

    checks = [
        ("Final cases", str(overview.get("final_cases", "—")), overview.get("final_cases") == 18),
        ("Practice cases", str(overview.get("practice_cases", "—")), overview.get("practice_cases") == 2),
        ("Blocks", str(overview.get("blocks", "—")), overview.get("blocks") == 3),
        (
            "Exact case match",
            str(summary.get("exact_case_match_to_official_frozen", "—")),
            summary.get("exact_case_match_to_official_frozen") is True,
        ),
    ]
    check_rows = [
        html.Div(
            [
                html.Span("✓" if ok else "·", className=f"check-icon {'check-ok' if ok else 'check-pending'}"),
                html.Span(label + ": ", className="check-label"),
                html.Span(value, className="check-value"),
            ],
            className="check-row",
        )
        for label, value, ok in checks
    ]

    git = summary.get("git_commit") or "—"
    short_git = git[:12] if git != "—" else "—"

    manifest_rows = []
    for key, val in manifest.items():
        if not isinstance(val, dict):
            manifest_rows.append(
                html.Div(
                    [html.Span(key + ": ", className="meta-key"), html.Span(str(val), className="meta-value")],
                    className="meta-line",
                )
            )

    warning_items = [html.Div(w, className="warning-pill") for w in warnings]
    warning_block = (
        html.Div(warning_items, className="warning-row")
        if warning_items
        else html.Div([html.Div("No pipeline warnings.", className="ok-pill")], className="warning-row")
    )

    design_figures = [
        _design_calibration_figure(tables.get("calibration_bins")),
        _difficulty_figure(tables.get("difficulty_summary")),
        _protocol_rotation_figure(tables.get("protocol_design")),
    ]

    return html.Div(
        [
            _section_header(
                "Reproducibility",
                "Frozen design validation, artifact provenance, and experiment structure.",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Design Validation", className="subsection-title"),
                            html.Div(check_rows, className="check-list"),
                        ],
                        className="panel",
                    ),
                    html.Div(
                        [
                            html.H3("Pipeline Metadata", className="subsection-title"),
                            html.Div(
                                [
                                    html.Div([html.Span("Mode: ", className="meta-key"), html.Span(summary.get("mode", "—"), className="meta-value")], className="meta-line"),
                                    html.Div([html.Span("Git commit: ", className="meta-key"), html.Span(short_git, className="meta-value")], className="meta-line"),
                                    html.Div([html.Span("Analysis dir: ", className="meta-key"), html.Span(summary.get("analysis_dir", "—"), className="meta-value")], className="meta-line"),
                                ]
                            ),
                            html.H4("Selection Manifest", style={"marginTop": "16px", "marginBottom": "8px"}),
                            html.Div(manifest_rows) if manifest_rows else html.P("No manifest data.", className="empty-state"),
                        ],
                        className="panel",
                    ),
                    html.Div(
                        [
                            html.H3("Pipeline Warnings", className="subsection-title"),
                            warning_block,
                        ],
                        className="panel",
                    ),
                ],
                className="repro-grid",
            ),
            html.H3("Design Appendix", className="subsection-title", style={"marginTop": "28px"}),
            html.Div(
                [html.Div([_graph(fig)], className="panel") for fig in design_figures],
                className="panel-grid",
            ),
        ],
        className="tab-content",
    )


# ---------------------------------------------------------------------------
# Root layout
# ---------------------------------------------------------------------------

def build_layout(bundle: dict) -> html.Div:
    data_note = "" if bundle["has_participant_data"] else " — Awaiting participant exports"

    tabs = dcc.Tabs(
        [
            dcc.Tab(
                label="Executive Findings",
                children=[build_executive_tab(bundle)],
                className="tab-btn",
                selected_className="tab-btn-selected",
            ),
            dcc.Tab(
                label="Protocol Comparison",
                children=[build_protocol_tab(bundle)],
                className="tab-btn",
                selected_className="tab-btn-selected",
            ),
            dcc.Tab(
                label="Reliance & Revision",
                children=[build_reliance_tab(bundle)],
                className="tab-btn",
                selected_className="tab-btn-selected",
            ),
            dcc.Tab(
                label="Case Explorer",
                children=[build_cases_tab(bundle)],
                className="tab-btn",
                selected_className="tab-btn-selected",
            ),
            dcc.Tab(
                label="Reproducibility",
                children=[build_reproducibility_tab(bundle)],
                className="tab-btn",
                selected_className="tab-btn-selected",
            ),
        ],
        className="tab-strip",
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Loan Decision Study", className="eyebrow"),
                    html.H1("Results Explorer" + data_note, className="hero-title"),
                    html.P(
                        "Interactive companion to the paper. Loads from artifacts/analysis/latest/.",
                        className="hero-copy",
                    ),
                ],
                className="hero",
            ),
            tabs,
        ],
        className="app-shell",
    )
