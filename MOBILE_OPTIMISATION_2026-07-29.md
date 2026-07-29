# Mobile optimisation — Oliver's mTOR Atlas

**Date:** 29 July 2026
**Scope:** SPA (`index.html`, 8 tabs) + 311 generated static pages + `browse/`
**Verified at:** 320 / 360 / 375 / 390 / 414 / 430 / 768 px, plus 1440 px desktop, in both themes
**Method:** live Chrome, each page loaded in an iframe pinned to an exact CSS-pixel viewport, measured by an instrumented harness (not visual inspection alone)

---

## 1. How this was measured

Chrome enforces a minimum window width and `resize_window` did not reach the
viewport (`innerWidth` stayed 1920), so widths below ~400 px were untestable by
resizing. Instead every page was loaded inside an iframe set to an exact pixel
width; media queries evaluate against the frame, so 320 px is measured, not
simulated.

A harness (`_audit.js`) reported, per page per width:

| Check | Rule |
|---|---|
| Horizontal overflow | `documentElement.scrollWidth > clientWidth`, plus the specific elements whose rect exceeds the viewport |
| Tap targets | every interactive element under 44 × 44 px |
| Type size | any text rendering below the 11 px label floor |
| Overlaps | interactive elements colliding, **clipped to their scroll ancestors** |
| Escaped media | `img`/`svg`/`canvas` wider than their container |
| Contrast | WCAG AA, with **alpha layers composited** before measuring |

The harness itself was corrected four times during the pass — three of its
early "failures" were measurement bugs, not site bugs. Those are listed in §5
because a QA tool that over-reports is as costly as one that under-reports.

---

## 2. Every issue found

### Critical — content unreachable or broken

| # | Issue | Evidence |
|---|---|---|
| 1 | **Pathway tab overflowed the viewport by 604–674 px.** `.rail-left`, `.center`, `.graph-wrap` and `#entityDetail` all computed to 964 px. Cause: grid children default to `min-width:auto`, so the 940 px map SVG stretched every ancestor. | 320 px: 674 px overflow, 24 offending elements |
| 2 | **Timeline overflowed by 1 696–1 751 px.** `computeFit()` runs while `#lineageView` is `display:none`, so `clientWidth` is 0, `baseScale` falls back to 1, and the 1 986 px SVG never re-fits when the tab becomes visible. | 375 px: 1 711 px overflow |
| 3 | **The hamburger menu was off-screen at every mobile width.** `.tabs` is a flex child with `min-width:auto`, so it sized to its full 751 px of content and pushed the button to `right: 813 px`. | Found in the regression pass, after the drawer was built |
| 4 | **311 static pages had no media queries at all** — fixed 760 px wrap, 22 px padding, 4-column study tables with a long "Finding" column. | 0 `@media` rules in every generated page |
| 5 | **Studies table was 668 px wide inside a 349 px container.** | 390 px |

### Serious

| # | Issue |
|---|---|
| 6 | Search input at 12.5 px — below 16 px, so iOS Safari zooms the page on focus and leaves the user at the wrong scroll offset |
| 7 | Full pathway map had **no zoom of any kind** — horizontal scroll only, no fit, no pinch, no focus |
| 8 | Panning the map fired node clicks (no tap-vs-drag discrimination), opening random entity pages |
| 9 | On the Pathway tab the 189-entity rail rendered **before** the map, so a phone user scrolled the entire index to reach the diagram |
| 10 | Author-bio modal: 38 px overlay padding, 118 × 150 portrait and a 96 px timeline indent on a 360 px screen |
| 11 | Evidence Pyramid used a fixed 172 px label column |
| 12 | Tabs were `<div>`s with no `role`, no `tabindex`, no keyboard support — invisible to keyboard and screen-reader users |
| 13 | No skip link; diagrams were unlabelled to assistive tech |
| 14 | `Ask Atlas` button overhung its own flex container by 23 px at 320 px |
| 15 | Deep-search checkbox was a bare 13 × 13 px input |
| 16 | Entity-rail rows 26–29 px tall; author names 34 × 20 px; pagination 71 × 28 px; theme toggle 75 × 27 px |

### Contrast (WCAG AA failures, light theme)

| Token / element | Before | After |
|---|---|---|
| `--tier-c` amber `#C17A2E` (white text) | 3.45 | `#A56827` — 4.56 |
| `--tier-d` grey `#8A8375` (text on white) | 3.76 | `#7C7569` — 4.56 |
| `TYPE_COLOR` Drug `#C17A2E` | 3.45 | `#A56827` — 4.56 |
| `TYPE_COLOR` Biological process `#5B7A9D` | 4.45 | `#5A789B` — 4.57 |
| Pyramid P3 `#5B8FB0` | 3.50 | `#4E7A97` — 4.61 |
| Pyramid NR `#8A7CA8` | 3.80 | `#7D7098` — 4.52 |
| `--rt` registered-trial `#5F8BBF` | 3.54 | `#5278A6` — 4.57 |
| Graph hint `#6e8fa4` | 3.43 | `#5E7A8D` — 4.52 |
| Selected rail count `#a0c8d4` on crimson | 4.18 | `#D5EAF0` — 6.01 |
| Dark theme `--danger` `#c4614a` | 4.30 | `#C76A54` — 4.68 |

Dark theme was otherwise already compliant (5.5–8.0:1 throughout).

---

## 3. Every fix made

**Foundation** — full breakpoint ladder (1100/900/768/560/430/390/360); `min-width:0`
on every grid and flex child that holds wide content (the root cause of issues
1, 2, 3, 14); `overflow-x:clip` as a net (not `hidden`, which would break
`position:sticky`); 15 px reading floor and 11 px label floor; 16 px form
inputs; safe-area insets; `prefers-reduced-motion`.

**Navigation** — sticky tab rail with snap scrolling and an edge fade; a
hamburger drawer below 768 px built **from the existing `.tab` elements** and
forwarding `.click()` to them, so it cannot drift out of sync with the real
navigation; focus trap, `Esc`, backdrop dismiss, scroll lock, `aria-expanded` /
`aria-controls` / `aria-current`; sub-tab bars became 44 px segmented controls.

**Pathway map (the priority)** — a dependency-free pointer-event controller:

- pinch-to-zoom about the finger midpoint, one-finger pan, double-tap to zoom / restore
- fit-to-screen, `0.15×–6×` clamp, pan clamped so content cannot leave the screen
- **tap-vs-drag discrimination** — >8 px of travel suppresses the click in the capture phase
- toolbar (− / + / Fit / Focus) placed **above** the diagram, all buttons 44 px
- Focus reuses the app's existing Focused mode rather than duplicating it
- `transform`-based scaling (compositing only, no layout), `will-change` scoped to the gesture
- keyboard pan/zoom (arrows, +, −, 0) and `role="application"` labels
- re-attaches after `renderFullMap()` wipes `innerHTML`
- same controller on the Mechanism Explorer; the Timeline keeps its own zoom model and gained pinch plus a fit-on-show fix

**Content** — study/author tables become labelled cards below 560 px; map moved
above the entity rail, rail capped at 46 vh; modals became full-height sheets
with `dvh` and body-scroll lock; bio timeline indent 96 px → 0; Evidence Pyramid
stacked; `@media (hover:none)` removes hover-only affordances.

**Static pages** — fixed once in `build_pages.py` and regenerated all 311:
responsive wrap, fluid headings, `data-l`-labelled card tables, 44 px links and
tags, safe-area padding.

**Performance** — `content-visibility:auto` with `contain-intrinsic-size` on
off-screen blocks; font `preconnect`; `loading="lazy"` + `decoding="async"` on
images (including dynamically inserted ones); `will-change` only during gestures.

**Accessibility** — 44 px targets; `focus-visible` rings; skip link; full tab
`role`/`aria-selected`/arrow-key semantics; expandable study rows exposed as
buttons with `aria-expanded`; `forced-colors` support.

**Desktop escape hatch** — a "Desktop view" control in the footer and drawer
swaps the viewport meta to `width=1440` and persists in `localStorage`.

---

## 4. Components modified

`index.html` — 8 marked, idempotent blocks (`MOBILE-BLOCK:phase1-foundation`
… `phase8b-qa`) plus 6 targeted colour-token edits.
`build_pages.py` — CSS template, table classes, `data-l` labels, tier colours.
311 regenerated pages under `study/`, `gene/`, `drug/`, `disease/`,
`process/`, `outcome/`, `complex/`, `nutrient/`, `organelle/`, `intervention/`, `browse/`.

All `index.html` writes went through a verified injector: whole-file write,
`fsync`, byte-count read-back, and a `node --check` syntax gate on every inline
script — after an early attempt corrupted the file by inserting CSS into a
JavaScript-built `'<style>'` string. That failure was caught and reverted
byte-for-byte via checksum.

---

## 5. Harness corrections (reported for honesty)

Three findings were **measurement errors**, not site defects:

1. A `<tr>` "overlapping" a link inside it — containment, not collision.
2. Contrast scored against `rgba(...)` tints read as opaque, turning a genuine
   7.5:1 pass into a fake 1.69:1 failure.
3. Tabs scrolled out of the rail flagged as overlapping the hamburger — they are
   clipped by `overflow-x:auto` and never painted there.

Also corrected: content inside a pan/zoom surface is now excluded from tap-target
and font-size checks (it reports the zoom level, not a defect), and an `<input>`
inside a `<label>` is measured by the label's box.

---

## 6. Final measured state

Every tab × every width, both themes:

| Width | Overflow | Overlaps | Escaped media | Contrast | Tap targets |
|---|---|---|---|---|---|
| 320 | 0 | 0 | 0 | 0 | 2 (inline) |
| 360 | 0 | 0 | 0 | 0 | 2 (inline) |
| 375 | 0 | 0 | 0 | 0 | 2 (inline) |
| 390 | 0 | 0 | 0 | 0 | 2 (inline) |
| 414 | 0 | 0 | 0 | 0 | 2 (inline) |
| 430 | 0 | 0 | 0 | 0 | 2 (inline) |
| 768 | 0 | 0 | 0 | 0 | 2 (inline) |
| 1440 | 0 | 0 | 0 | 0 | desktop design unchanged |

Static pages (`/gene/mtor/`, `/study/LEE2024/`, `/drug/rapamycin/`,
`/disease/breast-cancer/`, `/browse/`) at 320/360/430: overflow 0, overlaps 0,
escaped media 0, contrast 0, small text 0.

Gesture behaviour verified by synthesised pointer events: pan tracks 1:1
(90 px → 90 px), pinch 2.0× out / 0.4× in, clamp holds at 0.15×–6×, a drag
produces 0 clicks, a tap produces 1.

Desktop at 1440 px: grid `230px 1141px` (original), hamburger `display:none` —
no regression.

---

## 7. Remaining limitations

1. **Two inline links stay under 44 px wide** — the word "relevant" inside a stat
   label, and author names in a table cell. Both are ≥44 px tall. WCAG 2.5.8
   exempts links inline in a block of text; widening them would break the
   sentence they sit in.
2. **SVG interiors are only comfortable when zoomed.** Map node labels are
   8–12 px at natural size; at fit scale (~0.3×) they are decorative. This is
   inherent to a 1 080 × 1 323 diagram on a 390 px screen — the gesture layer is
   the mitigation, not a workaround.
3. **Disabled pagination buttons sit at ~3.3:1.** WCAG 1.4.3 exempts disabled
   controls; lifted from 1.99:1 so they read as disabled rather than broken.
4. **A 3 px sliver of content passes under the sticky tab bar during scroll.**
   The bar is opaque, and anchors clear it via `scroll-margin-top:76px`.
5. **Not tested on physical hardware.** Gestures were verified with synthesised
   pointer events at exact viewports; iOS Safari momentum scrolling, real pinch
   inertia and Android browser quirks warrant a hands-on pass before launch.
6. **`overflow-x:clip` is a safety net.** All root causes were fixed and the
   net is not load-bearing today, but future wide content would be silently
   clipped rather than loudly overflowing.

---

## 7b. Post-deployment fix — invisible active tab on touch devices

Reported from a real phone after the first deploy: on a selected section the tab
bar showed a blank gap where the current tab should be.

**Cause — a regression I introduced in Phase 4.** The rule was:

```css
@media (hover:none){ .tab:hover{background:none;} }
```

`.tab:hover` and `.tab.active` both have specificity (0,2,0), and the Phase 4
block sits later in the stylesheet, so the hover reset won. On a touch device
`(hover:none)` matches, and a tapped element *stays* in `:hover` — so the
selected tab lost `background:var(--teal)` while keeping
`color:var(--on-teal)` (white). Result: white text on white, with only the
crimson bottom border still visible.

**Why the QA sweep missed it.** Desktop Chrome never matches `(hover:none)`, so
the rule was inert in the test rig at every one of the seven widths.

**Fix.**

```css
.tab:not(.active):hover{background:none;}          /* scoped               */
.tabs .tab.active,.tabs .tab.active:hover,
.tabs .tab.active:focus,.tabs .tab.active:active{  /* + explicit guard     */
  background:var(--teal)!important;color:var(--on-teal)!important;
  border-bottom-color:var(--teal)!important;}
```

**Verification.** The `(hover:none)` block's `conditionText` was rewritten to
`all` at runtime and the tab hovered with a real pointer — reproducing the exact
phone condition. Before the fix the tab rendered fully invisible (matching the
reported screenshot); after it, crimson with white text.

**Same trap audited elsewhere.** `.mx-node:hover rect` (0,2,1) would likewise
have clobbered `.mx-node.mx-pop rect` (0,2,1) on touch; scoped to
`.mx-node:not(.mx-pop):hover`. The remaining `:hover` rules I added
(`.apz-btn`, `.dtoggle`, `.mnav-*`) have no competing state rule.

**Lesson for future passes:** any `@media (hover:none)` reset must be tested
with the condition forced on, and must never target a bare class that also
carries a state modifier of equal specificity.

---

## 8. Production readiness

The mobile version is **production-ready**, with one qualification: item 5
above. Every measurable defect in the brief — horizontal scrolling, clipped
content, overlapping elements, overflowing text, tiny tap targets, unusable
tables, oversized modals, unreadable diagrams, inaccessible menus, broken
responsive layouts, escaped images — is at zero across all seven target widths
and both themes, and desktop is unchanged. What remains is device-lab
confirmation of touch feel, which no amount of viewport emulation can settle.
