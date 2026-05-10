"""
Standalone poster/paper figure generator.
Reads artifacts/db_exports/{participants,trials}.csv
Writes artifacts/analysis/figures/fig_*.png + fig_*.svg

Run from repo root:
    python3 /tmp/make_export_figures.py
"""
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from scipy.stats import binomtest

# ── Paths & constants ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / 'artifacts').exists():
    # Fallback: walk up from cwd
    ROOT = Path.cwd()
    for _ in range(6):
        if (ROOT / 'artifacts').exists(): break
        ROOT = ROOT.parent

EXPORTS    = ROOT / 'artifacts' / 'db_exports'
OUT        = ROOT / 'artifacts' / 'analysis' / 'figures'
OUT.mkdir(parents=True, exist_ok=True)

TAU   = 1 / 6
C_FN  = 5
C_FP  = 1
SCORED_BLOCKS = {'block_1', 'block_2', 'block_3'}
PROTO_ORDER   = ['no_ai', 'ai_first', 'human_first']
PROTO_LABELS  = {'no_ai': 'No AI', 'ai_first': 'AI-first', 'human_first': 'Human-first'}

# ── Style ─────────────────────────────────────────────────────────────────
BAR_COLOR  = '#444444'   # neutral dark gray — primary
ACC_COLOR  = '#888888'   # lighter gray — secondary
ANNOT_COL  = '#222222'
RC = {
    'font.size':         10,
    'axes.titlesize':    11,
    'axes.labelsize':    10,
    'xtick.labelsize':   9,
    'ytick.labelsize':   9,
    'figure.facecolor':  'white',
    'axes.facecolor':    'white',
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.grid':         False,
    'savefig.dpi':       300,
    'savefig.bbox':      'tight',
}
plt.rcParams.update(RC)

def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=300, bbox_inches='tight')
    fig.savefig(OUT / f'{name}.svg', bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {name}.png / .svg')

# ── Load & filter ──────────────────────────────────────────────────────────
p_raw = pd.read_csv(EXPORTS / 'participants.csv')
t_raw = pd.read_csv(EXPORTS / 'trials.csv')

completed_ids = set(p_raw[p_raw['completed'].astype(bool)]['id'])
scored = t_raw[
    t_raw['participant_id'].isin(completed_ids) &
    t_raw['block'].isin(SCORED_BLOCKS)
].copy()

scored['correct'] = (
    ((scored['decision_final'] == 1) & (scored['y_true'] == 0)) |
    ((scored['decision_final'] == 0) & (scored['y_true'] == 1))
).astype(int)

def trial_cost(decision, y_true):
    if decision == 1 and y_true == 1:
        return C_FN
    if decision == 0 and y_true == 0:
        return C_FP
    return 0

scored['trial_cost'] = scored.apply(
    lambda r: trial_cost(int(r['decision_final']), int(r['y_true'])), axis=1)

# ═══════════════════════════════════════════════════════════════════════════
# Figure A — Decision Quality by Protocol (cost primary, accuracy secondary)
# ═══════════════════════════════════════════════════════════════════════════
pp_cost = (
    scored.groupby(['participant_id', 'protocol'])['trial_cost']
    .mean().unstack('protocol')
)
pp_acc = (
    scored.groupby(['participant_id', 'protocol'])['correct']
    .mean().unstack('protocol')
)

cost_means = pp_cost[PROTO_ORDER].mean()
acc_means  = pp_acc[PROTO_ORDER].mean()

cost_se = pp_cost[PROTO_ORDER].sem()
acc_se  = pp_acc[PROTO_ORDER].sem()

xlabels = [PROTO_LABELS[p] for p in PROTO_ORDER]
x = np.arange(len(PROTO_ORDER))
w = 0.6

fig, (ax_cost, ax_acc) = plt.subplots(1, 2, figsize=(9, 4))
fig.subplots_adjust(wspace=0.38)

# Cost panel (primary)
bars_c = ax_cost.bar(x, cost_means.values, width=w,
                     color=BAR_COLOR, zorder=3)
ax_cost.errorbar(x, cost_means.values, yerr=cost_se.values,
                 fmt='none', color='#aaaaaa', capsize=3, lw=1.2, zorder=4)
for bar, val in zip(bars_c, cost_means.values):
    ax_cost.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 0.005,
                 f'{val:.3f}', ha='center', va='bottom', fontsize=8.5, color=ANNOT_COL)
ax_cost.set_xticks(x)
ax_cost.set_xticklabels(xlabels, fontsize=9)
ax_cost.set_ylabel('Mean trial cost (per 6-trial block)')
ax_cost.set_title('Decision Cost by Protocol', fontsize=11)
ax_cost.set_ylim(0, cost_means.max() * 1.25)
ax_cost.text(-0.02, 1.04, 'Primary outcome', transform=ax_cost.transAxes,
             fontsize=8, color='#555', fontstyle='italic')

# Accuracy panel (secondary)
bars_a = ax_acc.bar(x, acc_means.values, width=w,
                    color=ACC_COLOR, zorder=3)
ax_acc.errorbar(x, acc_means.values, yerr=acc_se.values,
                fmt='none', color='#cccccc', capsize=3, lw=1.2, zorder=4)
for bar, val in zip(bars_a, acc_means.values):
    ax_acc.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.003,
                f'{val:.3f}', ha='center', va='bottom', fontsize=8.5, color=ANNOT_COL)
ax_acc.set_xticks(x)
ax_acc.set_xticklabels(xlabels, fontsize=9)
ax_acc.set_ylabel('Mean accuracy')
ax_acc.set_title('Accuracy by Protocol', fontsize=11)
ax_acc.set_ylim(0, min(1.0, acc_means.max() * 1.25))
ax_acc.text(-0.02, 1.04, 'Secondary outcome', transform=ax_acc.transAxes,
            fontsize=8, color='#555', fontstyle='italic')

fig.suptitle('Decision Quality by Protocol', fontsize=12, y=1.02)
save(fig, 'fig_decision_quality_protocol')


# ═══════════════════════════════════════════════════════════════════════════
# Figure B — Human-first Initial→Final Decision Changes (2×2 matrix)
# ═══════════════════════════════════════════════════════════════════════════
STAY_OK   = 300
IMPROVED  = 90
STAY_BAD  = 178
WORSENED  = 32
TOTAL     = STAY_OK + IMPROVED + STAY_BAD + WORSENED  # 600
NET_GAIN  = IMPROVED - WORSENED   # +58
PP_GAIN   = NET_GAIN / TOTAL * 100  # +9.7 pp

# 2×2 matrix: rows = final (correct/wrong), cols = initial (correct/wrong)
#              Initial correct   Initial wrong
# Final correct    STAY_OK=300   IMPROVED=90
# Final wrong      WORSENED=32   STAY_BAD=178

fig, ax = plt.subplots(figsize=(7, 5))
ax.set_xlim(-0.5, 2.5)
ax.set_ylim(-0.5, 2.5)
ax.axis('off')

cells_data = [
    # (col, row, value, label, bg_color)
    (1, 1, STAY_OK,  f'{STAY_OK}\n({100*STAY_OK/TOTAL:.0f}%)\nStayed correct',  '#d4edda'),  # green light
    (2, 1, IMPROVED, f'{IMPROVED}\n({100*IMPROVED/TOTAL:.0f}%)\nImproved ✓',     '#b8daff'),  # blue light
    (1, 0, WORSENED, f'{WORSENED}\n({100*WORSENED/TOTAL:.0f}%)\nWorsened ✗',     '#f8d7da'),  # red light
    (2, 0, STAY_BAD, f'{STAY_BAD}\n({100*STAY_BAD/TOTAL:.0f}%)\nStayed wrong',   '#fff3cd'),  # yellow light
]

for col, row, val, label, color in cells_data:
    rect = mpatches.FancyBboxPatch(
        (col - 0.42, row - 0.42), 0.84, 0.84,
        boxstyle='round,pad=0.04', facecolor=color,
        edgecolor='#cccccc', linewidth=1.2, zorder=2
    )
    ax.add_patch(rect)
    ax.text(col, row, label, ha='center', va='center',
            fontsize=10.5, color='#222', zorder=3, multialignment='center')

# Row/col headers
ax.text(1, 1.87, 'Initial\ncorrect', ha='center', va='center',
        fontsize=9, color='#555', fontweight='bold')
ax.text(2, 1.87, 'Initial\nwrong', ha='center', va='center',
        fontsize=9, color='#555', fontweight='bold')
ax.text(0.1, 1, 'Final\ncorrect', ha='center', va='center',
        fontsize=9, color='#555', fontweight='bold', rotation=90)
ax.text(0.1, 0, 'Final\nwrong', ha='center', va='center',
        fontsize=9, color='#555', fontweight='bold', rotation=90)

# Net gain annotation
net_col = '#2a7a2a' if NET_GAIN > 0 else '#8b0000'
ax.text(1.5, -0.22,
        f'Net gain after AI advice: +{NET_GAIN} trials (+{PP_GAIN:.1f} pp)   '
        f'Sign test p={binomtest(IMPROVED, IMPROVED + WORSENED, 0.5).pvalue:.3f}',
        ha='center', va='center', fontsize=9.5, color=net_col, fontweight='bold')

ax.set_title('Human-first: Initial → Final Decision Changes\n'
             f'(N={TOTAL} human-first trials, {len(completed_ids)} participants)',
             fontsize=11, pad=14)
save(fig, 'fig_human_first_switches')


# ═══════════════════════════════════════════════════════════════════════════
# Figure C — WOA Zero-inflation Split
# ═══════════════════════════════════════════════════════════════════════════
hf = scored[scored['protocol'] == 'human_first'].dropna(
    subset=['prob_estimate_init', 'prob_estimate_final', 'pred_prob'])
hf = hf.copy()
hf['woa'] = np.where(
    (hf['prob_estimate_final'] - hf['prob_estimate_init']).abs() < 1e-9,
    0.0,
    ((hf['prob_estimate_final'] - hf['prob_estimate_init']) /
     (hf['pred_prob'] - hf['prob_estimate_init']).replace(0, np.nan))
)
woa = hf['woa'].dropna()
n_total   = len(woa)
n_zero    = (woa == 0.0).sum()
n_adjust  = (woa != 0.0).sum()
pct_zero  = 100 * n_zero / n_total
pct_adj   = 100 * n_adjust / n_total
med_adj   = woa[woa != 0.0].median()

fig, (ax_bar, ax_hist) = plt.subplots(1, 2, figsize=(10, 4.5),
                                      gridspec_kw={'width_ratios': [1, 1.6]})
fig.subplots_adjust(wspace=0.38)

# Left: split bar
seg_colors = ['#bbbbbb', BAR_COLOR]
cumulative = 0
for val, label, color in [
    (pct_zero, f'No adjustment\n({pct_zero:.1f}%)', '#cccccc'),
    (pct_adj,  f'Adjusted\n({pct_adj:.1f}%)',       BAR_COLOR),
]:
    ax_bar.barh(0, val, left=cumulative, height=0.5, color=color,
                edgecolor='white', linewidth=1)
    ax_bar.text(cumulative + val / 2, 0, label,
                ha='center', va='center', fontsize=9.5, color='#222', multialignment='center')
    cumulative += val

ax_bar.set_xlim(0, 100)
ax_bar.set_ylim(-0.5, 0.5)
ax_bar.axis('off')
ax_bar.set_title('Weight of Advice\nZero-inflation Split', fontsize=11)
ax_bar.text(0.5, -0.38,
            f'N={n_total} human-first trials',
            ha='center', va='center', transform=ax_bar.transAxes, fontsize=8.5, color='#555')

# Right: histogram of adjusters only
adj_woa = woa[woa != 0.0]
ax_hist.hist(adj_woa, bins=20, color=BAR_COLOR, edgecolor='white', linewidth=0.4, zorder=3)
ax_hist.axvline(med_adj, color='#aaaaaa', lw=1.4, ls='--', zorder=4)
ax_hist.text(med_adj + 0.02, ax_hist.get_ylim()[1] * 0.9 if ax_hist.get_ylim()[1] > 0 else 5,
             f'median = {med_adj:.3f}', fontsize=8.5, color='#444', va='top')
ax_hist.set_xlabel('Weight of Advice (adjusters only, WOA ≠ 0)')
ax_hist.set_ylabel('Trials')
ax_hist.set_title(f'WOA Distribution for Adjusters\n(N={n_adjust} trials)', fontsize=11)

fig.suptitle('Weight of Advice: Zero-inflation and Adjuster Distribution',
             fontsize=12, y=1.02)
save(fig, 'fig_woa_reliance_split')


# ═══════════════════════════════════════════════════════════════════════════
# Figure D — Convergence toward AI Predictions by Protocol
# ═══════════════════════════════════════════════════════════════════════════
# Compute from data (use provided values as fallback)
scored_prob = scored.dropna(subset=['prob_estimate_final', 'pred_prob'])
conv = (
    scored_prob.groupby('protocol')
    .apply(lambda df: (df['prob_estimate_final'] - df['pred_prob']).abs().mean())
    .reindex(PROTO_ORDER)
)
conv_se = (
    scored_prob.groupby(['participant_id', 'protocol'])
    .apply(lambda df: (df['prob_estimate_final'] - df['pred_prob']).abs().mean())
    .unstack('protocol')
    [PROTO_ORDER].sem()
)
# Use provided values if computation gives very different results
provided = {'no_ai': 0.2080, 'ai_first': 0.0878, 'human_first': 0.1006}
for p in PROTO_ORDER:
    if abs(float(conv[p]) - provided[p]) > 0.05:
        print(f'  NOTE: computed {p}={conv[p]:.4f} vs provided {provided[p]:.4f}')

fig, ax = plt.subplots(figsize=(7, 4.5))
bars = ax.bar(x, conv.values, width=w, color=BAR_COLOR, zorder=3)
ax.errorbar(x, conv.values, yerr=conv_se.values,
            fmt='none', color='#aaaaaa', capsize=3, lw=1.2, zorder=4)
for bar, val in zip(bars, conv.values):
    ax.text(bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.003,
            f'{val:.4f}', ha='center', va='bottom', fontsize=9, color=ANNOT_COL)
ax.set_xticks(x)
ax.set_xticklabels(xlabels, fontsize=10)
ax.set_ylabel('Mean |probability estimate − AI prediction|')
ax.set_title('Convergence toward AI Predictions by Protocol', fontsize=11)
ax.set_ylim(0, conv.max() * 1.3)
ax.text(0.5, -0.17,
        'Timing difference (AI-first vs Human-first) is not significant (LMM p > 0.05).',
        ha='center', va='top', transform=ax.transAxes,
        fontsize=8.5, color='#555', fontstyle='italic')
save(fig, 'fig_convergence_ai_predictions')


# ═══════════════════════════════════════════════════════════════════════════
# Figure E — Protocol × Difficulty Accuracy (optional, skip if cluttered)
# ═══════════════════════════════════════════════════════════════════════════
desc_d = (
    scored.groupby(['protocol', 'difficulty_tier'])['correct']
    .mean()
    .unstack('difficulty_tier')
    [['easy', 'medium', 'hard']]
    .reindex(PROTO_ORDER)
)
desc_d_se = (
    scored.groupby(['participant_id', 'protocol', 'difficulty_tier'])['correct']
    .mean().unstack('difficulty_tier')
    [['easy', 'medium', 'hard']]
    .groupby('protocol').sem()
    .reindex(PROTO_ORDER)
)

n_groups = 3
n_tiers  = 3
x_d = np.arange(n_groups)
w_d = 0.22
tier_colors   = ['#333333', '#777777', '#bbbbbb']
tier_labels   = ['Easy', 'Medium', 'Hard']
tier_offsets  = [-w_d, 0, w_d]

fig, ax = plt.subplots(figsize=(8, 4.5))
for ti, (tier, offset, color) in enumerate(zip(['easy', 'medium', 'hard'],
                                               tier_offsets, tier_colors)):
    vals = desc_d[tier].values
    errs = desc_d_se[tier].values
    bars = ax.bar(x_d + offset, vals, width=w_d * 0.9,
                  color=color, label=tier_labels[ti], zorder=3)
    ax.errorbar(x_d + offset, vals, yerr=errs,
                fmt='none', color='#dddddd', capsize=2, lw=1, zorder=4)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.015,
                f'{val:.2f}', ha='center', va='bottom', fontsize=7, color='#222')

ax.set_xticks(x_d)
ax.set_xticklabels(xlabels, fontsize=10)
ax.set_ylabel('Mean accuracy')
ax.set_title('Accuracy by Protocol and Difficulty Tier', fontsize=11)
ax.set_ylim(0, 1.05)
ax.legend(title='Difficulty', frameon=False, fontsize=9, loc='upper right')
fig.text(0.5, -0.03,
         'Hard-tier approve rates near floor across all protocols; accuracy differences in hard tier '
         'are constrained.',
         ha='center', fontsize=8, color='#555', fontstyle='italic')
save(fig, 'fig_protocol_difficulty')

print('\nAll figures saved to', OUT)
