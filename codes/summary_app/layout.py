from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html


PALETTE = {
    "ink": "#19222f",
    "sand": "#f6f2e8",
    "paper": "#fffdf8",
    "accent": "#d77a2f",
    "teal": "#1f7a8c",
    "red": "#b5473a",
    "gold": "#b6952c",
}


def metric_lookup(table: pd.DataFrame | None, name: str) -> str:
    if table is None or table.empty:
        return "n/a"
    match = table.loc[table["metric"] == name, "value"]
    if match.empty:
        return "n/a"
    value = float(match.iloc[0])
    return f"{value:.3f}"


def build_overview_cards(bundle: dict[str, Any]) -> list[html.Div]:
    summary = bundle["summary"]
    metrics = bundle["tables"]["model_metrics"]
    overview = summary.get("overview", {})
    warnings = summary.get("warnings", [])
    manifest = summary.get("selection_manifest", {})
    cards = [
        {"label": "Mode", "value": summary.get("mode", "unknown").upper()},
        {"label": "Final cases", "value": str(overview.get("final_cases", "n/a"))},
        {"label": "Candidate pool", "value": f"{overview.get('candidate_pool_rows', 'n/a')}"},
        {"label": "AUC", "value": metric_lookup(metrics, "auc")},
        {"label": "Brier", "value": metric_lookup(metrics, "brier")},
        {"label": "ECE", "value": metric_lookup(metrics, "ece")},
    ]
    header_cards = [
        html.Div(
            [html.Div(card["label"], className="metric-label"), html.Div(card["value"], className="metric-value")],
            className="metric-card",
        )
        for card in cards
    ]
    metadata = html.Div(
        [
            html.Div(
                [
                    html.Span("Deterministic official path: ", className="meta-key"),
                    html.Span(
                        "yes" if summary.get("mode") == "frozen" else "no, best-effort rebuild",
                        className="meta-value",
                    ),
                ],
                className="meta-line",
            ),
            html.Div(
                [
                    html.Span("Manifest version: ", className="meta-key"),
                    html.Span(str(manifest.get("version", "n/a")), className="meta-value"),
                ],
                className="meta-line",
            ),
            html.Div(
                [
                    html.Span("Exact case match to official frozen set: ", className="meta-key"),
                    html.Span(str(summary.get("exact_case_match_to_official_frozen")), className="meta-value"),
                ],
                className="meta-line",
            ),
        ],
        className="metadata-block",
    )
    warning_block = html.Div(
        [html.Div(item, className="warning-pill") for item in warnings] or [html.Div("No pipeline warnings.", className="ok-pill")],
        className="warning-row",
    )
    return [html.Div(header_cards, className="metric-grid"), metadata, warning_block]


def calibration_figure(calibration: pd.DataFrame | None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            line={"color": "#b9b4aa", "dash": "dash"},
            name="Perfect calibration",
        )
    )
    if calibration is not None and not calibration.empty:
        fig.add_trace(
            go.Scatter(
                x=calibration["mean_pred_prob"],
                y=calibration["observed_rate"],
                mode="lines+markers",
                line={"color": PALETTE["teal"], "width": 3},
                marker={"size": 10, "color": PALETTE["accent"]},
                text=calibration["bin_label"],
                name="Frozen pool",
            )
        )
    fig.update_layout(
        title="Model Calibration",
        xaxis_title="Mean predicted default probability",
        yaxis_title="Observed default rate",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    return fig


def difficulty_figure(difficulty: pd.DataFrame | None) -> go.Figure:
    if difficulty is None or difficulty.empty:
        return go.Figure()
    melted = difficulty.melt(
        id_vars=["difficulty_tier"],
        value_vars=["default_rate", "model_accuracy", "model_optimal_agreement"],
        var_name="metric",
        value_name="value",
    )
    fig = px.bar(
        melted,
        x="difficulty_tier",
        y="value",
        color="metric",
        barmode="group",
        color_discrete_sequence=[PALETTE["accent"], PALETTE["teal"], PALETTE["red"]],
        title="Difficulty-Tier Profiles",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        yaxis_title="Rate",
    )
    return fig


def case_selection_figure(final_cases: pd.DataFrame | None) -> go.Figure:
    if final_cases is None or final_cases.empty:
        return go.Figure()
    working = final_cases.sort_values("case_position").copy()
    working["correct_label"] = working["correct"].map({1: "Model correct", 0: "Model incorrect"})
    fig = px.scatter(
        working,
        x="case_position",
        y="pred_prob",
        color="difficulty_tier",
        symbol="correct_label",
        hover_data=["case_id", "block", "purpose", "model_optimal"],
        color_discrete_sequence=[PALETTE["teal"], PALETTE["gold"], PALETTE["red"]],
        title="Selected Case Set",
    )
    fig.add_hline(y=0.5, line_dash="dash", line_color="#7f7f7f")
    fig.add_hline(y=1 / 6, line_dash="dot", line_color=PALETTE["accent"])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        xaxis_title="Case position",
        yaxis_title="Predicted default probability",
    )
    return fig


def protocol_figure(protocol_design: pd.DataFrame | None) -> go.Figure:
    if protocol_design is None or protocol_design.empty:
        return go.Figure()
    pivot = protocol_design.pivot(index="participant_group", columns="block", values="protocol")
    protocol_order = {"no_ai": 0, "human_first": 1, "ai_first": 2}
    encoded = pivot.replace(protocol_order)
    fig = go.Figure(
        data=go.Heatmap(
            z=encoded.values,
            x=list(encoded.columns),
            y=list(encoded.index),
            text=pivot.values,
            texttemplate="%{text}",
            colorscale=[
                [0.0, "#f2d5c4"],
                [0.5, "#f0bf8f"],
                [1.0, "#c4661f"],
            ],
            showscale=False,
        )
    )
    fig.update_layout(
        title="Protocol Rotation",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    return fig


def case_cost_figure(case_costs: pd.DataFrame | None) -> go.Figure:
    if case_costs is None or case_costs.empty:
        return go.Figure()
    fig = px.bar(
        case_costs,
        x="strategy",
        y="avg_cost_per_case",
        color="strategy",
        color_discrete_sequence=[PALETTE["red"], PALETTE["gold"], PALETTE["teal"], PALETTE["accent"]],
        title="Cost Benchmarks on the 18-Case Set",
    )
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        xaxis_title="Strategy",
        yaxis_title="Average cost per case",
    )
    return fig


def participant_protocol_figure(table: pd.DataFrame | None) -> go.Figure | None:
    if table is None or table.empty:
        return None
    fig = px.bar(
        table.melt(id_vars=["protocol"], value_vars=["mean_accuracy", "mean_cost"]),
        x="protocol",
        y="value",
        color="variable",
        barmode="group",
        color_discrete_sequence=[PALETTE["teal"], PALETTE["red"]],
        title="Participant Export Summary",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    return fig


def reliance_figure(table: pd.DataFrame | None) -> go.Figure | None:
    if table is None or table.empty:
        return None
    fig = px.bar(
        table,
        x="protocol",
        y="revision_rate",
        color="protocol",
        color_discrete_sequence=[PALETTE["accent"], PALETTE["teal"], PALETTE["red"]],
        title="Human-First Revision Rate",
    )
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    return fig


def graph_card(title: str, figure: go.Figure | None, empty_message: str) -> html.Div:
    if figure is None or len(figure.data) == 0:
        return html.Div([html.H3(title), html.P(empty_message, className="empty-state")], className="panel")
    return html.Div([dcc.Graph(figure=figure, config={"displayModeBar": False})], className="panel")


def build_layout(bundle: dict[str, Any]) -> html.Div:
    overview_cards = build_overview_cards(bundle)
    figures = {
        "calibration": calibration_figure(bundle["tables"]["calibration_bins"]),
        "difficulty": difficulty_figure(bundle["tables"]["difficulty_summary"]),
        "selection": case_selection_figure(bundle["tables"]["final_cases"]),
        "protocol": protocol_figure(bundle["tables"]["protocol_design"]),
        "cost": case_cost_figure(bundle["tables"]["case_costs"]),
        "participant_protocol": participant_protocol_figure(bundle["tables"]["participant_protocol_summary"]),
        "reliance": reliance_figure(bundle["tables"]["participant_reliance_summary"]),
    }
    return html.Div(
        [
            html.Div(
                [
                    html.Div("Capstone Reproduction", className="eyebrow"),
                    html.H1("Summary Visualization App", className="hero-title"),
                    html.P(
                        "A poster-ready view of the frozen case design, calibration, protocol structure, and any bundled participant exports.",
                        className="hero-copy",
                    ),
                ],
                className="hero",
            ),
            html.Div(overview_cards, className="overview-shell"),
            html.Div(
                [
                    graph_card("Calibration", figures["calibration"], "Calibration data not found."),
                    graph_card("Difficulty", figures["difficulty"], "Difficulty summary not found."),
                    graph_card("Case Selection", figures["selection"], "Final case table not found."),
                    graph_card("Protocol Rotation", figures["protocol"], "Protocol design table not found."),
                    graph_card("Cost Benchmarks", figures["cost"], "Cost summary not found."),
                    graph_card(
                        "Participant Protocol Summary",
                        figures["participant_protocol"],
                        "No frozen participant export is bundled yet, so protocol outcome summaries are unavailable.",
                    ),
                    graph_card(
                        "Reliance Summary",
                        figures["reliance"],
                        "No frozen human-first trial export is bundled yet, so revision-rate summaries are unavailable.",
                    ),
                ],
                className="panel-grid",
            ),
        ],
        className="app-shell",
    )
