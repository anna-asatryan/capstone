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
        margin=dict(l=24, r=20, t=80 if title else 24, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Arial, sans-serif", color="#111827", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True, showgrid=False, zeroline=False, linecolor="#e5e7eb", tickfont=dict(color="#475569"))
    fig.update_yaxes(fixedrange=True, gridcolor="#e5e7eb", zeroline=False, linecolor="#e5e7eb", tickfont=dict(color="#475569"))
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
    display_names = {
        "Beneficial reliance": "Aligned — model action agreed with outcome",
        "Over-reliance": "Aligned — model action disagreed with outcome",
        "Beneficial override": "Deviated — model action disagreed with outcome",
        "Harmful override": "Deviated — model action agreed with outcome",
    }
    cols = ["Beneficial reliance", "Over-reliance", "Beneficial override", "Harmful override"]
    colors = ["#059669", "#dc2626", "#2563eb", "#ea580c"]
    fig = go.Figure()
    for col, color in zip(cols, colors):
        label = display_names[col]
        fig.add_trace(go.Bar(x=rel["Protocol"], y=rel[col], name=label, marker_color=color, hovertemplate=f"{label}<br>%{{y:.1%}}<extra></extra>"))
    fig.update_layout(barmode="stack")
    fig = tufte_layout(fig, height=height, title="Alignment with threshold-implied action")
    fig.update_yaxes(title="Share of AI-probability trials", tickformat=".0%")
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


def case_protocol_delta_heatmap(df: pd.DataFrame, mode: str = "Cost benefit", height: int = 410) -> go.Figure:
    """Case x protocol matrix showing where AI-supported protocols improved over no-AI.

    Positive values are always better:
    - Cost benefit = no-AI mean cost minus protocol mean cost.
    - Accuracy benefit = protocol accuracy minus no-AI accuracy.
    - Approval change = protocol approval rate minus no-AI approval rate.
    """
    if df.empty or "case_id" not in df.columns or "protocol" not in df.columns:
        return go.Figure()

    metric_map = {
        "Cost benefit": {
            "col": "trial_cost",
            "label": "Cost benefit vs No-AI",
            "hover_label": "cost benefit",
            "value_fmt": ".3f",
            "benefit_fn": lambda proto, base: base - proto,
        },
        "Accuracy benefit": {
            "col": "correct",
            "label": "Accuracy benefit vs No-AI",
            "hover_label": "accuracy benefit",
            "value_fmt": ".1%",
            "benefit_fn": lambda proto, base: proto - base,
        },
        "Approval change": {
            "col": "decision_final",
            "label": "Approval-rate change vs No-AI",
            "hover_label": "approval-rate change",
            "value_fmt": ".1%",
            "benefit_fn": lambda proto, base: proto - base,
        },
    }
    spec = metric_map.get(mode, metric_map["Cost benefit"])
    value_col = spec["col"]
    if value_col not in df.columns:
        return go.Figure()

    meta_cols = [c for c in ["case_id", "case_position", "difficulty_tier", "pred_prob", "y_true"] if c in df.columns]
    meta = df[meta_cols].drop_duplicates(subset=["case_id"]).copy()
    if "case_position" not in meta.columns:
        meta["case_position"] = range(1, len(meta) + 1)
    meta = meta.sort_values(["case_position", "case_id"], na_position="last")
    case_ids = meta["case_id"].tolist()
    x_labels = [f"C{int(pos)}" if pd.notna(pos) else f"C{i+1}" for i, pos in enumerate(meta["case_position"])]

    means = df.groupby(["case_id", "protocol"], observed=True)[value_col].mean().unstack("protocol")
    rows = [p for p in ["ai_first", "human_first"] if p in means.columns]
    if "no_ai" not in means.columns or not rows:
        return go.Figure()

    z = []
    custom = []
    text = []
    for proto in rows:
        z_row, c_row, t_row = [], [], []
        for _, m in meta.iterrows():
            cid = m["case_id"]
            base = means.loc[cid, "no_ai"] if cid in means.index and "no_ai" in means.columns else np.nan
            proto_val = means.loc[cid, proto] if cid in means.index and proto in means.columns else np.nan
            val = spec["benefit_fn"](proto_val, base) if pd.notna(proto_val) and pd.notna(base) else np.nan
            z_row.append(val)
            if mode == "Cost benefit":
                t_row.append("" if pd.isna(val) else f"{val:+.2f}")
            else:
                t_row.append("" if pd.isna(val) else f"{val:+.0%}")
            c_row.append([
                cid,
                int(m["case_position"]) if pd.notna(m.get("case_position", np.nan)) else None,
                m.get("difficulty_tier", "—"),
                m.get("pred_prob", np.nan),
                "Default" if m.get("y_true", np.nan) == 1 else "Paid" if m.get("y_true", np.nan) == 0 else "—",
                base,
                proto_val,
                val,
            ])
        z.append(z_row)
        custom.append(c_row)
        text.append(t_row)

    arr = np.asarray(z, dtype=float)
    finite = arr[np.isfinite(arr)]
    vmax = float(np.nanmax(np.abs(finite))) if finite.size else 1.0
    if vmax == 0 or not np.isfinite(vmax):
        vmax = 1.0

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x_labels,
            y=[PROTOCOL_LABELS.get(p, p) for p in rows],
            customdata=custom,
            text=text,
            texttemplate="%{text}",
            textfont={"size": 11},
            zmin=-vmax,
            zmax=vmax,
            colorscale=[[0, "#dc2626"], [0.5, "#f8fafc"], [1, "#059669"]],
            colorbar=dict(title="Benefit", thickness=12, len=0.72),
            hovertemplate=(
                "<b>Case %{customdata[1]}</b> · %{customdata[2]}<br>"
                "Outcome: %{customdata[4]}<br>"
                "AI risk: %{customdata[3]:.3f}<br>"
                "No-AI value: %{customdata[5]:.3f}<br>"
                "Protocol value: %{customdata[6]:.3f}<br>"
                f"{spec['hover_label']}: " + "%{customdata[7]:.3f}<extra></extra>"
            ),
        )
    )
    fig = tufte_layout(fig, height=height, title=f"Where AI helped across the 18 cases — {spec['label']}")
    fig.update_xaxes(title="Loan case", side="bottom", tickangle=0)
    fig.update_yaxes(title="AI-supported protocol")
    fig.add_annotation(
        xref="paper", yref="paper", x=0, y=1.12, showarrow=False, align="left",
        text="Positive cells mean improvement relative to the no-AI baseline for the same case.",
        font=dict(size=12, color="#64748b"),
    )
    return fig


def risk_threshold_strip(cases: pd.DataFrame, height: int = 190) -> go.Figure:
    """Compact case map: 18 loan cases against the cost-sensitive AI threshold."""
    if cases.empty or "pred_prob" not in cases.columns:
        return go.Figure()
    d = cases.copy()
    if "case_position" not in d.columns:
        d["case_position"] = range(1, len(d) + 1)
    d = d.sort_values(["pred_prob", "case_position"], na_position="last")
    d["Outcome"] = np.where(d.get("y_true", np.nan) == 1, "Default", "Paid")
    d["Case"] = d["case_position"].map(lambda x: f"Case {int(x)}" if pd.notna(x) else "Case")
    fig = px.scatter(
        d,
        x="pred_prob",
        y=["Cases"] * len(d),
        color="difficulty_tier" if "difficulty_tier" in d.columns else None,
        symbol="Outcome" if "Outcome" in d.columns else None,
        hover_data={
            "case_id": True,
            "case_position": True,
            "pred_prob": ":.3f",
            "y_true": True if "y_true" in d.columns else False,
            "mean_cost": ":.3f" if "mean_cost" in d.columns else False,
            "accuracy": ":.3f" if "accuracy" in d.columns else False,
        },
        category_orders={"difficulty_tier": TIERS},
        color_discrete_map={"easy": "#059669", "medium": "#ea580c", "hard": "#dc2626"},
    )
    fig.update_traces(marker=dict(size=13, line=dict(color="white", width=1.4)), hovertemplate=None)
    fig.add_vline(x=1/6, line_dash="dash", line_color="#111827", annotation_text="τ = 1/6", annotation_position="top")
    fig = tufte_layout(fig, height=height, title="Case risk map: AI probability vs decision threshold")
    fig.update_xaxes(title="AI-predicted default probability", range=[0, max(0.75, float(d["pred_prob"].max()) + 0.04)])
    fig.update_yaxes(title="", showticklabels=False)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1))
    return fig

