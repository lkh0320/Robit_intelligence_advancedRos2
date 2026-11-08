"""두 PC 측정 raw 를 표와 그래프로 만든다."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent.parent / 'report'
RAW, IMAGES = ROOT / 'logs' / 'raw_two_pc', ROOT / 'images'
COMBOS = [('fast', 'fast', 'Fast ↔ Fast'), ('fast', 'cyclone', 'Fast → Cyclone'),
          ('cyclone', 'fast', 'Cyclone → Fast'), ('cyclone', 'cyclone', 'Cyclone ↔ Cyclone')]
CONDS = [('none', '지연/손실 없음', '#2a78d6'), ('delay_20ms', '지연 20ms', '#eb6834'),
         ('loss_5%', '손실 5%', '#1baf7a')]


def pct(v, q):
    return v[int(q * (len(v) - 1))]


stat = {}
print('| 조합 | netem | 손실 | 평균 | p50 | p95 | 최대 | 회차별 p50 |')
print('|---|---|---|---|---|---|---|---|')
for a, b, label in COMBOS:
    for c, cname, _ in CONDS:
        v = [float(x) for x in (RAW / f'{a}_{b}_{c}.txt').read_text().split()]
        runs = [sorted(v[i:i + 100]) for i in range(0, 300, 100)]
        s = sorted(v)
        stat[(label, c)] = (pct(s, .5), pct(s, .95))
        print(f'| {label} | {cname} | {300 - len(v)}/300 | {sum(v) / len(v):.2f} | {pct(s, .5):.2f} | '
              f'{pct(s, .95):.2f} | {s[-1]:.2f} | {" / ".join(f"{pct(r, .5):.1f}" for r in runs)} |')

fp = next(f.fname for f in font_manager.fontManager.ttflist if f.name == 'Noto Sans CJK JP')
plt.rcParams['font.family'] = font_manager.FontProperties(fname=fp).get_name()
fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), dpi=150, facecolor='#fcfcfb', sharey=True)
labels = [c[2] for c in COMBOS][::-1]
h = .26
for k, (ax, title) in enumerate(zip(axes, ('RTT p50 (ms)', 'RTT p95 (ms)'))):
    ax.set_facecolor('#fcfcfb')
    top = max(v[k] for v in stat.values())
    for i, label in enumerate(labels):
        for j, (c, cname, color) in enumerate(CONDS):
            y = i + (1 - j) * (h + .02)
            val = stat[(label, c)][k]
            ax.barh(y, val, h, color=color, label=cname if i == 0 else None)
            ax.text(val + top * .015, y, f'{val:.1f}', va='center', fontsize=8, color='#52514e')
    ax.set_title(title, loc='left', fontsize=11, color='#0b0b0b')
    ax.set_xlim(0, top * 1.15)
    ax.set_yticks(range(len(labels)), labels, fontsize=10, color='#0b0b0b')
    ax.tick_params(axis='x', colors='#52514e')
    ax.tick_params(axis='y', length=0)
    ax.grid(axis='x', color='#e5e4e0', lw=.8)
    ax.set_axisbelow(True)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color('#c3c2b7')
handles, names = axes[0].get_legend_handles_labels()
fig.legend(handles, names, frameon=False, ncol=3, loc='lower center', fontsize=9)
fig.tight_layout(rect=(0, .07, 1, 1))
fig.savefig(IMAGES / '09_two_pc_rtt_chart.png', facecolor=fig.get_facecolor())
