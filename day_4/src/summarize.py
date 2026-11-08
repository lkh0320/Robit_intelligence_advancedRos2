"""s2_matrix.txt 를 조합별로 묶어 표와 그래프를 만든다. raw 는 조합당 측정값 전체다."""
import re
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent.parent / 'report'
LOGS, IMAGES = ROOT / 'logs', ROOT / 'images'
COMBOS = [('fast', 'fast', 'Fast ↔ Fast'),
          ('cyclone', 'cyclone', 'Cyclone ↔ Cyclone'),
          ('fast', 'cyclone', 'Fast → Cyclone'),
          ('cyclone', 'fast', 'Cyclone → Fast'),
          ('fast_udp', 'fast_udp', 'Fast ↔ Fast (UDP 강제)')]


def raw(a, b, d):
    return sorted(float(x) for x in (LOGS / 'raw' / f'{a}_{b}_d{d}.txt').read_text().split())


def pct(v, q):
    return v[int(q * (len(v) - 1))]


text = (LOGS / 's2_matrix.txt').read_text()
rows, med = [], {}
print('| 조합 | 지연 | 표본 | 손실 | 평균 | p50 | p95 | 최대 | 연결(최소~최대) |')
print('|---|---|---|---|---|---|---|---|---|')
for a, b, label in COMBOS:
    for d in (0, 20):
        lines = [l for l in text.splitlines() if l.startswith(f'delay={d}ms ping={a} pong={b} ')]
        lost = sum(100 - int(re.search(r'recv (\d+)/', l).group(1)) for l in lines)
        conn = [float(re.search(r'connect ([\d.]+)s', l).group(1)) for l in lines]
        v = raw(a, b, d)
        med[(label, d)] = pct(v, .5)
        print(f'| {label} | {d}ms | {len(v)} | {lost}/{len(lines) * 100} | {st.mean(v):.2f} | '
              f'{pct(v, .5):.2f} | {pct(v, .95):.2f} | {v[-1]:.2f} | {min(conn):.2f}~{max(conn):.2f}s |')

fp = next(f.fname for f in font_manager.fontManager.ttflist if f.name == 'Noto Sans CJK JP')
plt.rcParams['font.family'] = font_manager.FontProperties(fname=fp).get_name()
labels = [c[2] for c in COMBOS][::-1]
fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150, facecolor='#fcfcfb')
ax.set_facecolor('#fcfcfb')
h = .36
for i, label in enumerate(labels):
    a0, a20 = med[(label, 0)], med[(label, 20)]
    ax.barh(i + h / 2 + .02, a0, h, color='#2a78d6', label='lo 지연 없음' if i == 0 else None)
    ax.barh(i - h / 2 - .02, a20, h, color='#eb6834', label='lo 지연 20ms (왕복 40ms)' if i == 0 else None)
    ax.text(a0 + .5, i + h / 2 + .02, f'{a0:.2f}', va='center', fontsize=9, color='#52514e')
    ax.text(a20 + .5, i - h / 2 - .02, f'{a20:.2f}', va='center', fontsize=9, color='#0b0b0b')
ax.set_yticks(range(len(labels)), labels, fontsize=10, color='#0b0b0b')
ax.set_xlabel('RTT 중앙값 (ms)', color='#52514e')
ax.set_xlim(0, 47)
ax.tick_params(axis='x', colors='#52514e')
ax.tick_params(axis='y', length=0)
ax.grid(axis='x', color='#e5e4e0', lw=.8)
ax.set_axisbelow(True)
for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)
ax.spines['bottom'].set_color('#c3c2b7')
ax.set_title('lo 지연의 영향을 받지 않는 조합은 Fast ↔ Fast 뿐이다', loc='left', fontsize=12, color='#0b0b0b')
ax.legend(frameon=False, ncol=2, loc='upper center', bbox_to_anchor=(.45, -.16), fontsize=9)
fig.tight_layout()
fig.savefig(IMAGES / '02_rtt_chart.png', facecolor=fig.get_facecolor())
