from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from metrics import PROTOCOL_LABELS, PROTOCOLS, TIERS

COLORS = {
    "no_ai": "#cbd5e1",      # Neutral gray
    "ai_first": "#94a3b8",   # Darker gray
    "human_first": "#2563eb",# Blue accent
    "improved": "#059669",
    "worsened": "#dc2626",
    "neutral": "#cbd5e1",
    "orange": "#ea580c",
}

PLOTLY_TEMPLATE = "plotly_white"


def tufte_layout(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        title={"text": title or "", "x": 0.02, "xanchor": "left", "font": {"size": 18, "color": "#111827"}},
        margin=dict(l=24, r=20, t=52 if title else 24, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Arial, sans-serif", color="#111827", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#e5e7eb", tickfont=dict(color="#475569"))
    fig.update_yaxes(gridcolor="#e5e7eb", zeroline=False, linecolor="#e5e7eb", tickfont=dict(color="#475569"))
    return fig


def bar_by_protocol(summary: pd.DataFrame, metric: str, title: str, lower_is_better: bool = False, height: int = 320) -> go.Figure:
    d = summary.copy()
    d["protocol"] = pd.Categorical(d["protocol"], categories=PROTOCOLS, ordered=True)
    d = d.sort_values("protocol")
    text = d[metric].map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=d["Protocol"],
            y=d[metric],
            marker_color="#64748b",
            text=text,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br>" + metric + ": %{y:.4f}<extra></extra>",
        )
    )
    fig = tufte_layout(fig, height=height, title=title)
    axis_suffix = "lower is better" if lower_is_better else "higher is better"
    fig.update_yaxes(title=f"{metric} ({axis_suffix})")
    return fig


def paired_participant_plot(df: pd.DataFrame, metric: str, title: str, height: int = 340) -> go.Figure:
    wide = df.groupby(["participant_id", "protocol"])[metric].mean().unstack("protocol")
    labels = [PROTOCOL_LABELS[p] for p in PROTOCOLS if p in wide.columns]
    fig = go.Figure()
    x_map = {p: i for i, p in enumerate(PROTOCOLS)}
    for _, row in wide.iterrows():
        xs, ys = [], []
        for p in PROTOCOLS:
            if p in wide.columns and pd.notna(row[p]):
                xs.append(x_map[p])
                ys.append(row[p])
        if len(xs) >= 2:
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="rgba(100,116,139,0.18)", width=1), showlegend=False, hoverinfo="skip"))
    means = df.groupby("protocol")[metric].mean().reindex(PROTOCOLS)
    fig.add_trace(
        go.Scatter(
            x=list(range(len(means))),
            y=means.values,
            mode="markers+lines+text",
            marker=dict(size=13, color=[COLORS[p] for p in means.index], line=dict(color="white", width=2)),
            line=dict(color="#111827", width=2),
            text=[f"{v:.3f}" if pd.notna(v) else "" for v in means.values],
            textposition="top center",
            name="Mean",
            hovertemplate="Mean %{y:.4f}<extra></extra>",
        )
    )
    fig.update_xaxes(tickmode="array", tickvals=list(range(len(labels))), ticktext=labels)
    fig = tufte_layout(fig, height=height, title=title)
    fig.update_yaxes(title=metric)
    return fig


def difficulty_protocol_plot(df: pd.DataFrame, metric: str = "correct", height: int = 340) -> go.Figure:
    if "difficulty_tier" not in df.columns:
        return go.Figure()
    d = (
        df.groupby(["difficulty_tier", "protocol"], observed=True)[metric]
        .mean()
        .reset_index()
    )
    d["Protocol"] = d["protocol"].map(PROTOCOL_LABELS)
    fig = px.line(
        d,
        x="difficulty_tier",
        y=metric,
        color="protocol",
        markers=True,
        color_discrete_map=COLORS,
        category_orders={"difficulty_tier": TIERS, "protocol": PROTOCOLS},
    )
    fig.update_traces(line=dict(width=2.5), marker=dict(size=9), hovertemplate="%{x}<br>%{y:.3f}<extra></extra>")
    fig = tufte_layout(fig, height=height, title="Protocol effects by case difficulty")
    fig.update_xaxes(title="Difficulty tier")
    fig.update_yaxes(title=metric)
    # Cleaner legend labels
    for tr in fig.data:
        tr.name = PROTOCOL_LABELS.get(tr.name, tr.name)
    return fig


def switch_sankey(summary: dict, height: int = 340) -> go.Figure:
    matrix = summary.get("matrix")
    if matrix is None or matrix.empty:
        return go.Figure()
    sc = int(matrix.loc["Initial correct", "Final correct"])
    worsened = int(matrix.loc["Initial correct", "Final wrong"])
    improved = int(matrix.loc["Initial wrong", "Final correct"])
    sw = int(matrix.loc["Initial wrong", "Final wrong"])
    labels = ["Initial correct", "Initial wrong", "Final correct", "Final wrong"]
    source = [0, 0, 1, 1]
    target = [2, 3, 2, 3]
    values = [sc, worsened, improved, sw]
    colors = ["rgba(5,150,105,0.35)", "rgba(220,38,38,0.45)", "rgba(5,150,105,0.65)", "rgba(148,163,184,0.35)"]
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="fixed",
                node=dict(
                    pad=18,
                    thickness=18,
                    line=dict(color="rgba(17,24,39,0.18)", width=0.5),
                    label=labels,
                    color=["#0f766e", "#64748b", "#059669", "#dc2626"],
                ),
                link=dict(source=source, target=target, value=values, color=colors),
            )
        ]
    )
    return tufte_layout(fig, height=height, title="Human-first: initial judgment → final decision")


def switch_matrix_heatmap(summary: dict, height: int = 320) -> go.Figure:
    matrix = summary.get("matrix")
    if matrix is None or matrix.empty:
        return go.Figure()
    z = matrix.values
    text = [[f"{int(v)}<br>{100*v/np.sum(z):.1f}%" for v in row] for row in z]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=matrix.columns,
            y=matrix.index,
            colorscale=[[0, "#f8fafc"], [0.45, "#ccfbf1"], [1, "#0f766e"]],
            text=text,
            texttemplate="%{text}",
            hovertemplate="%{y} → %{x}<br>%{z} trials<extra></extra>",
            showscale=False,
        )
    )
    return tufte_layout(fig, height=height, title="Decision revision matrix")


def woa_histogram(df: pd.DataFrame, adjusters_only: bool = False, height: int = 340) -> go.Figure:
    d = df.dropna(subset=["woa"]).copy()
    if adjusters_only:
        d = d[d["woa"].abs() >= 0.01]
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=d["woa"],
            nbinsx=32,
            marker_color="#0f766e",
            opacity=0.88,
            hovertemplate="WOA bin: %{x}<br>Trials: %{y}<extra></extra>",
        )
    )
    if len(d):
        fig.add_vline(x=0, line_dash="dash", line_width=1, line_color="#111827", annotation_text="ignore AI", annotation_position="top left")
        fig.add_vline(x=d["woa"].mean(), line_width=2, line_color="#ea580c", annotation_text=f"mean {d['woa'].mean():.2f}", annotation_position="top right")
        fig.add_vline(x=d["woa"].median(), line_width=2, line_color="#2563eb", annotation_text=f"median {d['woa'].median():.2f}", annotation_position="bottom right")
    fig = tufte_layout(fig, height=height, title="Weight of Advice distribution")
    fig.update_xaxes(title="WOA: movement from initial estimate toward AI prediction")
    fig.update_yaxes(title="Trials")
    return fig


def reliance_stacked_bar(rel: pd.DataFrame, height: int = 340) -> go.Figure:
    if rel.empty:
        return go.Figure()
    cols = ["Beneficial reliance", "Over-reliance", "Beneficial override", "Harmful override"]
    colors = ["#059669", "#dc2626", "#2563eb", "#ea580c"]
    fig = go.Figure()
    for col, color in zip(cols, colors):
        fig.add_trace(go.Bar(x=rel["Protocol"], y=rel[col], name=col, marker_color=color, hovertemplate=f"{col}<br>%{{y:.1%}}<extra></extra>"))
    fig.update_layout(barmode="stack")
    fig = tufte_layout(fig, height=height, title="Reliance decomposition across AI trials")
    fig.update_yaxes(title="Share of AI-condition trials", tickformat=".0%")
    return fig


def ai_benefit_histogram(df: pd.DataFrame, height: int = 320) -> go.Figure:
    if "ai_benefit_accuracy" not in df.columns:
        return go.Figure()
    d = df.dropna(subset=["ai_benefit_accuracy"])
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=d["ai_benefit_accuracy"], nbinsx=22, marker_color="#2563eb", opacity=0.82))
    fig.add_vline(x=0, line_dash="dash", line_color="#111827", annotation_text="no benefit")
    fig.add_vline(x=0.20, line_dash="dash", line_color="#059669", annotation_text="large benefit")
    fig = tufte_layout(fig, height=height, title="Individual heterogeneity in AI benefit")
    fig.update_xaxes(title="AI benefit = mean AI-condition accuracy − no-AI accuracy")
    fig.update_yaxes(title="Participants")
    return fig


def case_outcomes_plot(df: pd.DataFrame, case_id, metric: str = "trial_cost", height: int = 320) -> go.Figure:
    d = df[df["case_id"].astype(str) == str(case_id)].copy()
    if d.empty:
        return go.Figure()
    s = d.groupby("protocol")[metric].mean().reindex(PROTOCOLS).reset_index()
    s["Protocol"] = s["protocol"].map(PROTOCOL_LABELS)
    fig = go.Figure(go.Bar(x=s["Protocol"], y=s[metric], marker_color="#64748b", text=[f"{v:.2f}" for v in s[metric]], textposition="outside"))
    fig = tufte_layout(fig, height=height, title="Selected case outcomes by protocol")
    fig.update_yaxes(title=metric)
    return fig


def case_scatter(cases: pd.DataFrame, height: int = 340) -> go.Figure:
    if cases.empty:
        return go.Figure()
    d = cases.copy()
    d["Outcome"] = np.where(d["y_true"] == 1, "Defaulted", "Paid")
    fig = px.scatter(
        d,
        x="pred_prob",
        y="mean_cost",
        color="difficulty_tier",
        size="n_trials",
        hover_data=["case_id", "accuracy", "approve_rate", "y_true"],
        category_orders={"difficulty_tier": TIERS},
        color_discrete_map={"easy": "#059669", "medium": "#ea580c", "hard": "#dc2626"},
    )
    fig.add_vline(x=1/6, line_dash="dash", line_color="#111827", annotation_text="τ = 1/6", annotation_position="top")
    fig = tufte_layout(fig, height=height, title="Case map: AI risk vs observed human cost")
    fig.update_xaxes(title="AI predicted default probability")
    fig.update_yaxes(title="Mean human decision cost")
    return fig
