"""Render the four-way summary figure (SVG) from analyze.py's summary.json.

Every position comes from the grid constants below, so columns, rows and bars stay aligned.
"""
import argparse
import json
from pathlib import Path
import re

ICONS = Path(__file__).resolve().parents[1] / 'figure-icons'
W, H = 1200, 830
LEFT, RIGHT = 48, 1152

# Columns: [start, end] in x.
COL_TOOL = (48, 300)
COL_PASS = (324, 496)
COL_INPUT = (520, 866)
COL_CALLS = (890, RIGHT)
INPUT_MAX, INPUT_SCALE = 100_000, 290      # tokens -> px
CALLS_MAX, CALLS_SCALE = 8, 200            # calls -> px

ROW_TOP, ROW_H = 300, 84
BAR_H, BAR_GAP = 20, 6                      # two bars per row: Claude above, Codex below
AXIS_Y = ROW_TOP + 4 * ROW_H

ARMS = [  # key, name, mode, color
    ('kitsune', 'Kitsune', 'MCP · your Firefox', 'url(#fox)'),
    ('aside', 'Aside', 'CLI REPL · your browser', '#c6dcb0'),
    ('egolite', 'EgoLite', 'CLI · your browser', '#86b9a8'),
    ('playwright', 'Playwright MCP', 'MCP · isolated Firefox', '#e7d9bd'),
]
HARNESSES = [('claude', 'Claude Code · claude-opus-5-5'), ('codex', 'Codex · gpt-6.1-sol')]
ARM_PAD = 4 / 48   # arm icons leave 4/48 of their box empty on each side; offset so the drawing aligns to the grid
INK, CREAM, MUTED, LINE, ALERT, ORANGE = '#09272a', '#fff0d6', '#a5bdb0', '#2f5149', '#ef7a6a', '#ffbb73'


def icon(name, x, y, size, color=None):
    """Inline an icon file's children, scaled from its viewBox into a size x size box at (x, y)."""
    text = (ICONS / f'{name}.svg').read_text()
    view = float(re.search(r'viewBox="0 0 ([\d.]+)', text)[1])
    root = re.search(r'<svg([^>]*)>', text)[1]
    inner = re.sub(r'^.*?<svg[^>]*>|</svg>\s*$', '', text.strip(), flags=re.S)
    # Keep the root's presentation attributes (fill="none", stroke=..., etc.); drop sizing ones.
    attrs = ''.join(f' {k}="{v}"' for k, v in re.findall(r'([\w:-]+)="([^"]*)"', root)
                    if k not in ('xmlns', 'width', 'height', 'viewBox'))
    attrs += f' color="{color}"' if color else ''
    return f'<g transform="translate({x} {y}) scale({size / view:g})"{attrs}>{inner}</g>'


def bar_y(row, i):
    """Top y of bar i (0 Claude, 1 Codex) in a row; the pair is centered on the row."""
    mid = ROW_TOP + row * ROW_H + ROW_H / 2
    return mid - BAR_H - BAR_GAP / 2 + i * (BAR_H + BAR_GAP)


def bar(x, y, width, color, harness):
    if harness == 'claude':
        return f'<rect x="{x}" y="{y:g}" width="{width:.1f}" height="{BAR_H}" rx="4" fill="{color}"/>'
    return (f'<rect x="{x}" y="{y:g}" width="{width:.1f}" height="{BAR_H}" rx="4" fill="{color}" fill-opacity="0.38" '
            f'stroke="{color}" stroke-width="1.5"/>')


def header(x, y, icon_name, label):
    return icon(icon_name, x, y - 17, 22, MUTED) + \
        f'<text x="{x + 30}" y="{y}" fill="{MUTED}" font-size="13" font-weight="700" letter-spacing="1.2">{label}</text>'


def render(s):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           'aria-labelledby="title desc">',
           '<title id="title">Four-way browser benchmark: 12 local tasks, Claude Code and Codex</title>',
           '<desc id="desc">' + '; '.join(
               f"{name}: passed {s[f'claude/{k}']['pass']}/12 (Claude) and {s[f'codex/{k}']['pass']}/12 (Codex), "
               f"mean input {s[f'claude/{k}']['mean_input_tokens'] / 1000:.0f}k / {s[f'codex/{k}']['mean_input_tokens'] / 1000:.0f}k tokens, "
               f"mean tool calls {s[f'claude/{k}']['mean_tool_calls']:.1f} / {s[f'codex/{k}']['mean_tool_calls']:.1f}"
               for k, name, _, _ in ARMS) + '.</desc>',
           '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#091f23"/><stop offset="1" stop-color="#10483f"/></linearGradient>'
           '<linearGradient id="fox"><stop stop-color="#f58b42"/><stop offset="1" stop-color="#ffc36d"/></linearGradient></defs>',
           f'<rect width="{W}" height="{H}" rx="28" fill="url(#bg)"/>',
           '<g font-family="Arial, Helvetica, sans-serif">']
    # Title block.
    out += [f'<rect x="{LEFT}" y="38" width="372" height="32" rx="16" fill="#173c39" stroke="#46635a"/>',
            '<circle cx="66" cy="54" r="5" fill="#b8d89d"/>',
            '<text x="82" y="59.5" fill="#c9ddba" font-size="14" letter-spacing="2">KITSUNE BENCHMARK / FOUR-WAY</text>',
            f'<text x="{LEFT}" y="122" fill="{CREAM}" font-size="38" font-weight="700">Fewest tool calls. Least input.</text>',
            f'<text x="{LEFT}" y="156" fill="#b5ccc1" font-size="18">12 local web tasks × 4 browser tools × 2 agents · 96 attempts · '
            'graded by what the server received</text>',
            icon('arm-kitsune', RIGHT - 60 * (1 - ARM_PAD), 38 - 60 * ARM_PAD, 60)]
    # Legend, aligned to the bar columns.
    # Legend on the column grid: caption under TASKS PASSED, swatches under the two bar columns.
    for (h, label), x in zip(HARNESSES, (COL_INPUT[0], COL_CALLS[0])):
        out += [bar(x, 196, 36, '#d3ded0', h).replace(f'height="{BAR_H}"', 'height="16"'),
                f'<text x="{x + 46}" y="209" fill="#d3ded0" font-size="15">{label}</text>']
    out.append(f'<text x="{COL_PASS[0]}" y="209" fill="{MUTED}" font-size="15">Top / bottom bar:</text>')
    # Column headers.
    y = ROW_TOP - 22
    out += [f'<text x="{COL_TOOL[0]}" y="{y}" fill="{MUTED}" font-size="13" font-weight="700" letter-spacing="1.2">TOOL</text>',
            header(COL_PASS[0], y, 'metric-success', 'TASKS PASSED'),
            header(COL_INPUT[0], y, 'metric-tokens', 'INPUT TOKENS / ATTEMPT'),
            header(COL_CALLS[0], y, 'metric-tools', 'TOOL CALLS / ATTEMPT')]
    # Grid lines and axis ticks, drawn under the bars.
    ticks = [(COL_INPUT[0] + v / INPUT_MAX * INPUT_SCALE, f'{v // 1000}k') for v in range(0, INPUT_MAX + 1, 25_000)]
    ticks += [(COL_CALLS[0] + v / CALLS_MAX * CALLS_SCALE, str(v)) for v in range(0, CALLS_MAX + 1, 2)]
    out.append(f'<path d="{" ".join(f"M{x:g} {ROW_TOP} V{AXIS_Y}" for x, _ in ticks)}" stroke="{LINE}" stroke-width="1"/>')
    out += [f'<text x="{x:g}" y="{AXIS_Y + 20}" fill="{MUTED}" font-size="13" text-anchor="middle">{t}</text>' for x, t in ticks]
    # Rows.
    for row, (key, name, mode, color) in enumerate(ARMS):
        top = ROW_TOP + row * ROW_H
        mid = top + ROW_H / 2
        if key == 'kitsune':
            out.append(f'<rect x="{LEFT - 16}" y="{top + 4}" width="{RIGHT - LEFT + 32}" height="{ROW_H - 8}" rx="14" '
                       'fill="#f58b42" fill-opacity="0.07" stroke="#f58b42" stroke-opacity="0.35"/>')
        elif row:
            out.append(f'<path d="M{LEFT} {top} H{RIGHT}" stroke="{LINE}" stroke-dasharray="2 4"/>')
        out += [icon(f'arm-{key}', COL_TOOL[0] - 40 * ARM_PAD, mid - 20, 40),
                f'<text x="{COL_TOOL[0] + 56}" y="{mid - 3}" fill="{ORANGE if key == "kitsune" else CREAM}" font-size="20" '
                f'font-weight="700">{name}</text>',
                f'<text x="{COL_TOOL[0] + 56}" y="{mid + 17}" fill="{MUTED}" font-size="13">{mode}</text>']
        for i, (h, _) in enumerate(HARNESSES):
            v = s[f'{h}/{key}']
            y = bar_y(row, i)
            text_y = y + BAR_H / 2 + 5
            missed = v['attempts'] - v['pass']
            chip = '#3b1f1d' if missed else '#173b36'
            out += [f'<rect x="{COL_PASS[0]}" y="{y:g}" width="64" height="{BAR_H}" rx="10" fill="{chip}" '
                    f'stroke="{ALERT if missed else "#46635a"}"/>',
                    f'<text x="{COL_PASS[0] + 32}" y="{text_y:g}" fill="{ALERT if missed else CREAM}" font-size="14" '
                    f'font-weight="700" text-anchor="middle">{v["pass"]}/{v["attempts"]}</text>']
            if missed:
                out.append(f'<text x="{COL_PASS[0] + 74}" y="{text_y:g}" fill="{ALERT}" font-size="12">'
                           f'{fail_note(v)}</text>')
            w = v['mean_input_tokens'] / INPUT_MAX * INPUT_SCALE
            out += [bar(COL_INPUT[0], y, w, color, h),
                    f'<text x="{COL_INPUT[0] + w + 8:.1f}" y="{text_y:g}" fill="{CREAM}" font-size="14" font-weight="700">'
                    f'{v["mean_input_tokens"] / 1000:.0f}k</text>']
            w = v['mean_tool_calls'] / CALLS_MAX * CALLS_SCALE
            out += [bar(COL_CALLS[0], y, w, color, h),
                    f'<text x="{COL_CALLS[0] + w + 8:.1f}" y="{text_y:g}" fill="{CREAM}" font-size="14" font-weight="700">'
                    f'{v["mean_tool_calls"]:.1f}</text>']
    # Findings and caveats.
    box = AXIS_Y + 44
    out += [f'<rect x="{LEFT}" y="{box}" width="{RIGHT - LEFT}" height="64" rx="14" fill="#2a2320" fill-opacity="0.55" stroke="{ALERT}" stroke-opacity="0.6"/>',
            icon('metric-failure', LEFT + 18, box + 20, 24, ALERT),
            f'<text x="{LEFT + 56}" y="{box + 27}" fill="{CREAM}" font-size="15"><tspan font-weight="700">Kitsune missed one task under both agents:</tspan> '
            'a native confirm() dialog blocked the click until it timed out.</text>',
            f'<text x="{LEFT + 56}" y="{box + 49}" fill="#d3ded0" font-size="14">Codex stalled until the 240 s timeout 3 times '
            '(Playwright 2, Kitsune 1) and wrongly reported success twice. Claude Code did neither.</text>']
    notes = ['Means per attempt; input includes cache. CLI tool call = one ./browser script (can batch actions); MCP = one tool call.',
             'One repeat per task. Playwright ran an isolated headless Firefox; the others drove the operator\u2019s browser. 2026-11-19.']
    out += [f'<text x="{LEFT}" y="{box + 96 + 22 * i}" fill="#bfd1c3" font-size="14">{t}</text>' for i, t in enumerate(notes)]
    out += ['</g>', '</svg>']
    return '\n'.join(out) + '\n'


def fail_note(v):
    parts = [f'{v["fail"]} fail'] if v['fail'] else []
    parts += [f'{v["error"]} error'] if v['error'] else []
    return ', '.join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('summary', type=Path, help='summary.json from scripts/analyze.py')
    p.add_argument('out', type=Path)
    args = p.parse_args()
    args.out.write_text(render(json.loads(args.summary.read_text())))


if __name__ == '__main__':
    main()
