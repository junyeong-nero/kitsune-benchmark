"""Hand-written defense pages for the hostile-UI capability matrix.

Each page isolates one mechanism that real sites use and that synthetic DOM events may not satisfy. A page calls
`__hostile.done(detail)` only when its own handler accepted the action the way a person's input would be accepted;
the fixture server records that, and `report.js` records every input event the page received with its `isTrusted`.
"""
from __future__ import annotations

# id -> (title, body HTML, script). `__hostile` is defined by /__hostile/report.js, loaded first.
PAGES: dict[str, tuple[str, str, str]] = {
    "trusted-click": ("Confirm order", '<button id="b">Confirm</button>', """
document.getElementById('b').addEventListener('click', e => {
  if (e.isTrusted) __hostile.done({trusted: true}); else __hostile.progress({ignored: 'untrusted click'});
});"""),

    "pointer-sequence": ("Start session", '<button id="b">Start</button>', """
// Like gesture-aware components: a press is pointerdown + pointerup of one pointer, primary button,
// released inside the element. A bare click event is ignored.
const b = document.getElementById('b');
let down = null;
b.addEventListener('pointerdown', e => { if (e.button === 0 && e.isPrimary) down = e.pointerId; });
b.addEventListener('pointerup', e => {
  const r = b.getBoundingClientRect();
  const inside = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
  if (down !== null && e.pointerId === down && inside) __hostile.done({pointerId: e.pointerId});
  else __hostile.progress({rejected: {down, pointerId: e.pointerId, inside}});
  down = null;
});"""),

    "hit-test": ("Checkout", '<div style="margin:120px 0 0 200px"><button id="b">Buy now</button></div>', """
// Click-jacking defenses: the event's coordinates must hit the button.
const b = document.getElementById('b');
b.addEventListener('click', e => {
  const hit = document.elementFromPoint(e.clientX, e.clientY);
  if (hit && b.contains(hit)) __hostile.done({x: e.clientX, y: e.clientY});
  else __hostile.progress({rejected: {x: e.clientX, y: e.clientY, hit: hit && hit.tagName}});
});"""),

    "mousedown-menu": ("File menu", """
<button id="t" aria-haspopup="menu" aria-expanded="false">Menu</button>
<ul id="m" role="menu" hidden><li role="menuitem" tabindex="-1">Open</li><li role="menuitem" tabindex="-1" id="r">Rename</li></ul>""", """
// Opens on mousedown (as many desktop-style menus do); a click alone toggles it open and shut.
const t = document.getElementById('t'), m = document.getElementById('m');
t.addEventListener('mousedown', e => { if (e.button !== 0) return; m.hidden = !m.hidden; t.setAttribute('aria-expanded', String(!m.hidden)); });
document.getElementById('r').addEventListener('mouseup', () => { if (!m.hidden) __hostile.done({item: 'rename'}); });"""),

    "css-hover-menu": ("Site navigation", """
<style>.nav li ul { display: none } .nav li:hover ul { display: block }</style>
<ul class="nav"><li><a href="#">Products</a><ul><li><a href="#pricing" id="p">Pricing</a></li></ul></li></ul>""", """
// The submenu exists only while the real pointer is over "Products" (CSS :hover).
document.getElementById('p').addEventListener('click', e => { e.preventDefault(); __hostile.done({item: 'pricing'}); });"""),

    "hover-intent": ("Gallery", """
<div id="tile" role="group" aria-label="Preview tile" style="width:260px;height:120px;border:1px solid #888;padding:8px">Preview tile
  <button id="o" hidden>Open</button></div>""", """
// Hover intent: the button appears after the pointer has moved over the tile for 400 ms.
const tile = document.getElementById('tile'), o = document.getElementById('o');
let since = null, moves = 0;
tile.addEventListener('mouseenter', () => { since = performance.now(); moves = 0; });
tile.addEventListener('mousemove', () => { moves++; if (since && moves >= 3 && performance.now() - since >= 400) o.hidden = false; });
tile.addEventListener('mouseleave', () => { since = null; o.hidden = true; });
o.addEventListener('click', () => __hostile.done({moves}));"""),

    "controlled-input": ("Profile", """
<label>Display name <input id="n" aria-label="Display name" autocomplete="off"></label><p id="s">Saved: (empty)</p>""", """
// Framework-style controlled input: state changes only on input events; every frame the DOM value is
// re-rendered from state, so a value written without an input event is reverted.
const n = document.getElementById('n'), s = document.getElementById('s');
let state = '';
n.addEventListener('input', () => {
  state = n.value; s.textContent = 'Saved: ' + state; __hostile.progress({value: state});
  if (state === 'Ada Lovelace') __hostile.done({value: state});
});
(function render() { if (n.value !== state) n.value = state; requestAnimationFrame(render); })();"""),

    "beforeinput-editor": ("Note", """
<div id="e" contenteditable="true" role="textbox" aria-label="Note" style="border:1px solid #888;min-height:60px;padding:4px"></div>""", """
// Like ProseMirror/Lexical: the model changes only through beforeinput; DOM edits are reverted to the model.
const e = document.getElementById('e');
let model = '';
const render = () => { if (e.textContent !== model) e.textContent = model; };
e.addEventListener('beforeinput', ev => {
  ev.preventDefault();
  // Composition (IME) input is handled too, as real editors do.
  if (['insertText', 'insertReplacementText', 'insertFromPaste', 'insertCompositionText'].includes(ev.inputType))
    model += ev.data ?? (ev.dataTransfer ? ev.dataTransfer.getData('text/plain') : '');
  else if (ev.inputType === 'deleteContentBackward') model = model.slice(0, -1);
  render(); __hostile.progress({text: model, inputType: ev.inputType, data: ev.data,
    transfer: ev.dataTransfer ? ev.dataTransfer.getData('text/plain') : null});
  if (model.includes('kitsune test')) __hostile.done({text: model});
});
new MutationObserver(render).observe(e, {childList: true, characterData: true, subtree: true});"""),

    "keyboard-shortcut": ("Command palette", '<p>Press Control+K to open the command palette.</p><div id="p" hidden role="dialog" aria-label="Commands">Commands</div>', """
// Shortcut handlers usually test KeyboardEvent.code (layout-independent), not only key.
window.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.code === 'KeyK') { document.getElementById('p').hidden = false; __hostile.done({code: e.code}); }
  else if ((e.ctrlKey || e.metaKey) && (e.key || '').toLowerCase() === 'k') __hostile.progress({rejected: {key: e.key, code: e.code}});
});"""),

    "keyup-search": ("Search", """
<label>Filter <input id="q" aria-label="Filter"></label><ul id="r"><li>kitsune</li><li>kite</li><li>playwright</li></ul>""", """
// Legacy widgets that filter on keyup only.
const q = document.getElementById('q');
q.addEventListener('keyup', () => { __hostile.progress({value: q.value}); if (q.value === 'kit') __hostile.done({value: q.value}); });"""),

    "pointer-capture-drag": ("Brightness", """
<p>Drag the knob to the 80% mark.</p>
<div id="track" style="position:relative;width:400px;height:8px;background:#ccc;margin:40px 0">
  <div id="knob" role="slider" aria-label="Brightness" aria-valuemin="0" aria-valuemax="100" aria-valuenow="10"
       style="position:absolute;left:40px;top:-11px;width:30px;height:30px;border-radius:15px;background:#36c;touch-action:none"></div>
  <span id="mark" role="img" aria-label="80% mark" style="position:absolute;left:290px;top:16px;width:60px;text-align:center">80% mark</span></div>""", """
// A custom slider without keyboard support: pointerdown + setPointerCapture + pointermove + pointerup.
const track = document.getElementById('track'), knob = document.getElementById('knob');
let dragging = false;
knob.addEventListener('pointerdown', e => {
  try { knob.setPointerCapture(e.pointerId); } catch (err) { __hostile.progress({captureFailed: String(err)}); return; }
  dragging = true;
});
knob.addEventListener('pointermove', e => {
  if (!dragging) return;
  const r = track.getBoundingClientRect();
  const v = Math.max(0, Math.min(100, Math.round((e.clientX - r.left) / r.width * 100)));
  knob.style.left = (v / 100 * r.width - 15) + 'px'; knob.setAttribute('aria-valuenow', v);
});
knob.addEventListener('pointerup', () => {
  if (!dragging) return; dragging = false;
  const v = Number(knob.getAttribute('aria-valuenow')); __hostile.progress({value: v});
  if (v >= 75 && v <= 85) __hostile.done({value: v});
});"""),

    "long-press": ("Trash", '<button id="b">Hold to delete</button>', """
// Hold for 600 ms (common on touch-first UIs).
const b = document.getElementById('b'); let t0 = null;
b.addEventListener('pointerdown', () => { t0 = performance.now(); });
b.addEventListener('pointerup', () => { const held = t0 ? performance.now() - t0 : 0; t0 = null;
  if (held >= 600) __hostile.done({held}); else __hostile.progress({held}); });"""),

    "dblclick-only": ("Files", '<table><tr id="row" tabindex="0"><td>Report.pdf</td><td>2 MB</td></tr></table>', """
// File managers open an item on double-click only.
document.getElementById('row').addEventListener('dblclick', () => __hostile.done({opened: 'Report.pdf'}));"""),

    "user-activation": ("Share", '<button id="b">Share</button>', """
// Popups, clipboard writes and fullscreen need transient user activation, which synthetic events do not grant.
document.getElementById('b').addEventListener('click', () => {
  const active = !!(navigator.userActivation && navigator.userActivation.isActive);
  const popup = window.open('about:blank', '_blank', 'width=200,height=200');
  if (popup) popup.close();
  if (active || popup) __hostile.done({active, popup: !!popup}); else __hostile.progress({active, popup: false});
});"""),

    "closed-shadow": ("Newsletter", '<news-signup></news-signup>', """
// A closed shadow root: page scripts and extensions cannot reach inside through shadowRoot.
customElements.define('news-signup', class extends HTMLElement {
  constructor() { super(); const root = this.attachShadow({mode: 'closed'});
    root.innerHTML = '<button>Subscribe</button>';
    root.querySelector('button').addEventListener('click', () => __hostile.done({subscribed: true})); }
});"""),

    "cross-origin-iframe": ("Payment", '<iframe id="f" title="Payment form" style="width:420px;height:140px;border:1px solid #888"></iframe>', """
// The payment button lives in a frame from another origin (localhost vs 127.0.0.1).
const f = document.getElementById('f');
f.src = location.href.replace('//127.0.0.1:', '//localhost:').replace('/c/cross-origin-iframe', '/frame/pay');"""),

    "canvas-button": ("Player", '<canvas id="c" width="300" height="160" role="img" aria-label="Video player" style="border:1px solid #888"></canvas>', """
// No DOM element for the button: the page hit-tests canvas coordinates (the Play button is in the centre).
const c = document.getElementById('c'), g = c.getContext('2d');
g.fillStyle = '#36c'; g.fillRect(110, 55, 80, 50); g.fillStyle = '#fff'; g.font = '20px sans-serif'; g.fillText('Play', 128, 87);
c.addEventListener('click', e => { const r = c.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
  if (x >= 110 && x <= 190 && y >= 55 && y <= 105) __hostile.done({x, y}); else __hostile.progress({missed: {x, y}}); });"""),
}

# The cross-origin frame's own page.
FRAME_PAY = ("Pay", '<button id="p">Pay</button>', "document.getElementById('p').addEventListener('click', () => __hostile.done({paid: true}));")
