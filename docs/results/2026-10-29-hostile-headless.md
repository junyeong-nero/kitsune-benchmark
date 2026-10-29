# Hostile-UI capability matrix, synthetic input (2026-10-29)

[Track](../hostile.md) · [Catalog](../../tasks/hostile/catalog.json)

**No model calls.** These are scripted tool strategies on 26 components: 17 defense pages and 9 real UI libraries.
Success is reported by each component's own handler.

**Setup:**

- **Kitsune:** `v0.7.0-26-g57c56a7` (main with #319, #318, #313, #316 and #330), clean pinned worktree, default
  capabilities. Its revision was checked before and after the run.
- **Playwright MCP:** `0.0.83`, `--isolated --headless`.
- **Browser:** private Firefox 1553, headless on both targets. `--trusted` was not used, so this is synthetic input
  only.

**Components solved by at least one strategy: Playwright 23/26, Kitsune 18/26.**

| | Components |
| --- | --- |
| Playwright only | `trusted-click`, `css-hover-menu`, `pointer-capture-drag`, `cross-origin-iframe`, `canvas-button`, `lib-radix-select` |
| Kitsune only | `closed-shadow` |
| Neither | `hover-intent`, `long-press` |

## Matrix

| Component | Mechanism | Strategy | playwright | kitsune |
| --- | --- | --- | --- | --- |
| trusted-click | Handler ignores events with isTrusted false | click | ✅ | ❌ not_accepted |
| pointer-sequence | Needs pointerdown + pointerup of one primary pointer released inside the element; ignores click | click | ✅ | ✅ |
| hit-test | elementFromPoint(clientX, clientY) must be the button | click | ✅ | ✅ |
| mousedown-menu | Menu opens on mousedown, item selected on mouseup | click_then_click | ✅ | ✅ |
| css-hover-menu | Submenu shown only by CSS :hover of the real pointer | hover_then_click | ✅ | ❌ target_not_found |
| css-hover-menu | Submenu shown only by CSS :hover of the real pointer | click_then_click | ✅ | ❌ target_not_found |
| hover-intent | Button appears after mousemove over the tile for 400 ms | hover_then_click | ❌ target_not_found | ❌ target_not_found |
| controlled-input | State changes only on input events; value written without one is reverted | type | ✅ | ✅ |
| controlled-input | State changes only on input events; value written without one is reverted | type_slowly | ✅ | ✅ |
| controlled-input | State changes only on input events; value written without one is reverted | fill_form | ✅ | ✅ |
| beforeinput-editor | contenteditable model changes only through beforeinput; DOM edits reverted | type | ✅ | ✅ |
| beforeinput-editor | contenteditable model changes only through beforeinput; DOM edits reverted | type_slowly | ✅ | ✅ |
| beforeinput-editor | contenteditable model changes only through beforeinput; DOM edits reverted | click_then_keys | ✅ | ✅ |
| keyboard-shortcut | Shortcut handler tests KeyboardEvent.code | press_shortcut | ✅ | ✅ |
| keyup-search | Filters on keyup only | type | ❌ not_accepted | ❌ not_accepted |
| keyup-search | Filters on keyup only | type_slowly | ✅ | ✅ |
| keyup-search | Filters on keyup only | fill_form | ❌ not_accepted | ❌ not_accepted |
| pointer-capture-drag | Custom slider: pointerdown + setPointerCapture + pointermove, no keyboard | drag | ✅ | ❌ target_not_found |
| pointer-capture-drag | Custom slider: pointerdown + setPointerCapture + pointermove, no keyboard | slider_fill | ❌ tool_error | ❌ tool_error |
| long-press | pointerdown held for 600 ms | click | ❌ not_accepted | ❌ not_accepted |
| dblclick-only | Opens on dblclick only | double_click | ✅ | ✅ |
| dblclick-only | Opens on dblclick only | click | ❌ not_accepted | ❌ not_accepted |
| user-activation | window.open needs transient user activation | click | ✅ | ✅ |
| closed-shadow | Button inside a closed shadow root | click | ❌ target_not_found | ✅ |
| cross-origin-iframe | Button in a cross-origin iframe | click | ✅ | ❌ target_not_found |
| canvas-button | Canvas hit-testing at the centre; no DOM element for the button | click | ✅ | ❌ target_not_found |
| lib-react-input | React controlled input (onChange) | type | ✅ | ✅ |
| lib-react-input | React controlled input (onChange) | type_slowly | ✅ | ✅ |
| lib-react-input | React controlled input (onChange) | fill_form | ✅ | ✅ |
| lib-react-select | Searchable combobox on mousedown and keyboard | click_then_click | ✅ | ✅ |
| lib-react-select | Searchable combobox on mousedown and keyboard | type_then_enter | ✅ | ✅ |
| lib-react-select | Searchable combobox on mousedown and keyboard | type_then_click_option | ✅ | ✅ |
| lib-react-select | Searchable combobox on mousedown and keyboard | select_option | ❌ tool_error | ❌ tool_error |
| lib-radix-dropdown | Trigger opens on pointerdown, items select on pointerup/click | click_then_click | ✅ | ✅ |
| lib-radix-dropdown | Trigger opens on pointerdown, items select on pointerup/click | hover_then_click | ❌ target_not_found | ❌ target_not_found |
| lib-radix-select | Custom listbox, pointer selection and typeahead | click_then_click | ✅ | ❌ not_accepted |
| lib-radix-select | Custom listbox, pointer selection and typeahead | select_option | ❌ tool_error | ❌ tool_error |
| lib-radix-slider | Pointer capture on the track, arrow/page keys on the thumb | slider_fill | ❌ tool_error | ✅ |
| lib-radix-slider | Pointer capture on the track, arrow/page keys on the thumb | slider_keys | ✅ | ✅ |
| lib-dndkit-sortable | Pointer sensor with 5 px activation, keyboard sensor | drag | ❌ not_accepted | ✅ |
| lib-dndkit-sortable | Pointer sensor with 5 px activation, keyboard sensor | sortable_keys | ✅ | ✅ |
| lib-tiptap | Editor state through beforeinput/keydown | type | ✅ | ✅ |
| lib-tiptap | Editor state through beforeinput/keydown | type_slowly | ✅ | ✅ |
| lib-tiptap | Editor state through beforeinput/keydown | click_then_keys | ✅ | ✅ |
| lib-codemirror | Editor state through its own input handling | type | ✅ | ✅ |
| lib-codemirror | Editor state through its own input handling | type_slowly | ✅ | ✅ |
| lib-codemirror | Editor state through its own input handling | click_then_keys | ✅ | ✅ |
| lib-daypicker | Calendar grid with its own focus model | click | ✅ | ✅ |

The outcome labels mean:

- `target_not_found`: the server's snapshot exposed no ref for that element.
- `not_accepted`: the tools ran, but the component did not accept the input.
- `tool_error`: the tool refused the call.

## Findings for Kitsune (synthetic input)

Event counts come from each page's `report.js`.

1. **`isTrusted`-gated handlers ignore Kitsune's default input.**
   - `trusted-click` received `pointerdown`, `mousedown`, `pointerup`, `mouseup` and `click`, all `:synthetic`.
   - Playwright's input arrives `:trusted`, through Juggler.
   - Kitsune's remedy is `browser_trusted_click` (OS input). It is not measured here; it is the `--trusted --headed`
     mode.
2. **CSS `:hover` menus never open.** A synthetic hover cannot set `:hover`, so "Pricing" never appears in the
   snapshot. Kitsune's guide documents this; the matrix confirms it. Playwright's hover moves the real (browser-level)
   pointer.
3. **Non-interactive hover and drop targets get no ref.** A `div role="group"` hover tile and a `span role="img"`
   drop mark appear only as `text "…"` lines, so `browser_hover` and `browser_drag` cannot target them. Playwright
   gives both a ref.
4. **A `<canvas role="img" aria-label="Video player">` is missing from the snapshot**, so canvas UIs (players, maps,
   games) cannot be targeted. Playwright lists it as `img "Video player"`, and its centre click hits the canvas's
   Play button.
5. **Cross-origin iframe content is not observable.** Kitsune lists the frame with `content=cross_origin`, an explicit
   limit. Playwright exposes its button (`ref=f5e4`) and clicks it. This affects embedded payment and sign-in widgets.
6. **Radix Select ignores Kitsune's option click.**
   - The menu opens, and the option has a ref.
   - Kitsune sends `pointerdown`/`pointerup`/`click` (`pointerType: mouse`) with **no `pointermove` before the
     press**. Playwright moves the pointer to the target first.
   - Hypothesis: Radix ignores a `pointerup` when the pointer has not moved since the menu opened. Moving the pointer
     to the target before pressing, as a person's pointer does, would likely fix this and similar widgets.

## Where Kitsune is ahead

- **Closed shadow root:** Kitsune exposes and clicks the button; Playwright's snapshot does not include it.
- **dnd-kit sortable `browser_drag`:** Kitsune's drag is accepted (5 px activation). Playwright's drag sends
  `pointerdown` but no `pointerup` the sensor accepts.
- **Radix Slider `fill_form` with type `slider`:** accepted on Kitsune (#318). Playwright refuses a non-input slider.

## Both fail

| Component | Why |
| --- | --- |
| `hover-intent` | Needs sustained pointer movement for 400 ms |
| `long-press` | There is no hold primitive (held 1–2 ms) |
| `keyup-search` with `type`/`fill_form` | A fill sends no `keyup`; `type_slowly` works on both |
| Custom selects with `select_option` | That tool targets native `<select>` by design; click strategies work |
| `pointer-capture-drag` with `slider_fill` | Not an input; Kitsune's arrow keys reach a slider without a keyboard handler |

## Fixture fixes made before this run (fairness)

- **`dblclick-only` targets:** now accept `row`, `cell` or `button`. Playwright names the cell, and Kitsune names the
  focusable row as a button.
- **Drop mark:** its centre was moved to exactly 80% of the drag track.
- **`beforeinput-editor`:** also accepts `insertCompositionText` and `dataTransfer` text, as ProseMirror and Lexical
  do. Playwright's `fill` on contenteditable arrives as composition input.

## Next

- Run `--trusted --headed` to see which of findings 1–6 `browser_trusted_click` resolves. It moves the real pointer,
  so it needs an idle machine.
- File Kitsune issues for findings 3–6. Findings 1 and 2 are known and documented limits of synthetic input.
- Raw evidence (private): `artifacts/hostile/runs/headless-57c56a7/`.
