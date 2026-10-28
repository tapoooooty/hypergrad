"""Builds the README diagrams as HTML (rendered to PNG with Playwright).

Boxes: (id, x, y, w, h, title, body, style) with style in {"core", "ext", "plain", "warn", "bad"}.
Edges: (from_xy, to_xy, label, label_xy, style) with explicit coordinates, laid out by hand.
"""
import html, json, sys
from pathlib import Path

CSS = """
:root{--paper:#EDF5F1;--card:#F8FCFA;--ink:#0B2420;--rule:#9DBDB3;--muted:#56746C;--mint:#97FCE4;--amber:#C98A12;--red:#C9493A}
*{margin:0;box-sizing:border-box}
body{background:var(--paper);font-family:Inter,sans-serif;color:var(--ink);position:relative;overflow:hidden}
.title{position:absolute;left:56px;top:44px;font:600 26px 'Inter Display';letter-spacing:-.02em}
.cap{position:absolute;left:56px;top:82px;font:400 15px Inter;color:var(--muted);max-width:820px}
.box{position:absolute;border:1.5px solid var(--ink);border-radius:8px;background:var(--card);padding:12px 14px}
.box h3{font:600 15px Inter;letter-spacing:-.005em}
.box p{font:400 13px/1.45 Inter;color:var(--muted);margin-top:4px}
.box.core{background:var(--ink);color:#EAF7F2}.box.core p{color:#9EC2B8}
.box.core h3::before{content:"";display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--mint);margin-right:8px;vertical-align:1px}
.box.ext{border-style:dashed;background:transparent}
.box.warn{border-color:var(--amber)}.box.warn h3{color:var(--amber)}
.box.bad{border-color:var(--red)}.box.bad h3{color:var(--red)}
.group{position:absolute;border:1px solid var(--rule);border-radius:12px}
.group span{position:absolute;top:-10px;left:14px;background:var(--paper);padding:0 6px;font:500 13px Inter;color:var(--muted)}
.lbl{position:absolute;font:400 12.5px Inter;color:var(--muted);background:var(--paper);padding:1px 5px;white-space:nowrap}
.lbl b{color:var(--ink);font-weight:500}
.foot{position:absolute;left:56px;bottom:30px;font:400 13px Inter;color:var(--muted)}
svg{position:absolute;left:0;top:0;pointer-events:none}
"""

def build(spec, out):
    W, H = spec["size"]
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}body{{width:{W}px;height:{H}px}}</style></head><body>"]
    parts.append(f"<div class='title'>{html.escape(spec['title'])}</div><div class='cap'>{spec['caption']}</div>")
    for g in spec.get("groups", []):
        x, y, w, h, t = g
        parts.append(f"<div class='group' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'><span>{html.escape(t)}</span></div>")
    svg = [f"<svg width='{W}' height='{H}'><defs>"]
    for name, col in (("ink", "#0B2420"), ("amber", "#C98A12"), ("red", "#C9493A"), ("rule", "#9DBDB3")):
        svg.append(f"<marker id='a-{name}' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='{col}'/></marker>")
    svg.append("</defs>")
    cols = {"ink": "#0B2420", "amber": "#C98A12", "red": "#C9493A", "rule": "#9DBDB3"}
    for e in spec["edges"]:
        d, style = e["d"], e.get("style", "ink")
        dash = " stroke-dasharray='5 5'" if e.get("dashed") else ""
        mk = "" if e.get("noarrow") else f" marker-end='url(#a-{style})'"
        svg.append(f"<path d='{d}' fill='none' stroke='{cols[style]}' stroke-width='1.5'{dash}{mk}/>")
    svg.append("</svg>")
    parts.append("".join(svg))
    for b in spec["boxes"]:
        x, y, w, h, t, body, style = b
        parts.append(f"<div class='box {style}' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'><h3>{html.escape(t)}</h3><p>{body}</p></div>")
    for e in spec["edges"]:
        if e.get("label"):
            lx, ly = e["at"]
            parts.append(f"<div class='lbl' style='left:{lx}px;top:{ly}px'>{e['label']}</div>")
    if spec.get("foot"):
        parts.append(f"<div class='foot'>{spec['foot']}</div>")
    parts.append("</body></html>")
    Path(out).write_text("".join(parts), encoding="utf-8")

if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    build(spec, sys.argv[2])
