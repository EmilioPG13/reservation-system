---
name: Court Booking
description: A day of padel courts read as one printed railway timetable page. White stock, near-black ink, hairline rules, one signal red.
colors:
  paper: "#ffffff"
  wash: "#f3f4f5"
  ink: "#141414"
  ink-soft: "#55595f"
  rule: "#c9ccd1"
  edge: "#80858c"
  signal: "#d90018"
  signal-wash: "#fdecee"
typography:
  display:
    fontFamily: "Archivo Variable, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Archivo Variable, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Archivo Variable, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1
  body:
    fontFamily: "Archivo Variable, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tabular-nums"
  label:
    fontFamily: "Archivo Variable, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.25
rounded:
  none: "0"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1.125rem"
  cell-height: "3.875rem"
  control-height: "2.75rem"
components:
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0 1.125rem"
    height: "2.75rem"
  button-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  button-plate:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    height: "2.75rem"
  button-plate-hover:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.paper}"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 0.75rem"
    height: "2.75rem"
  grid-head:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    height: "2.75rem"
  grid-court:
    backgroundColor: "{colors.wash}"
    textColor: "{colors.ink}"
    width: "5.75rem"
  grid-cell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "0.375rem 0.375rem 0.375rem 0.5rem"
    height: "3.875rem"
    width: "5.75rem"
  grid-cell-ocupada:
    backgroundColor: "{colors.wash}"
  grid-cell-tuya:
    backgroundColor: "{colors.signal-wash}"
    textColor: "{colors.ink}"
  plate:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    padding: "0.75rem"
---

# Design System: Court Booking

## Overview

**Creative North Star: "Horario Gráfico"**

A day of courts is read as one printed timetable page, in the manner of a Swiss or European railway Fahrplan: strict rows and columns, hairline rules, data and nothing else. White offset-printed stock, near-black ink, grey hairlines and a single signal red. The system refuses the sporty rounded-card booking app and the dashboard of cards; there are no cards here, only ruled boxes.

Everything is square. Depth does not exist: rules, weight, and inversion do the work that shadows and fills do elsewhere. State is never carried by colour alone: every grid cell holds a word plus a mark in a fixed place, and colour only reinforces. Figures and hours are tabular so columns read as columns.

**Key Characteristics:**
- One neutral grotesque (Archivo Variable) in few sizes, hours and figures tabular.
- Hairline-square corners everywhere; no radii, no gradients, no drop shadows.
- Two neutral layers (paper, wash) plus ink; one accent, signal red.
- State is a word plus a fixed-position mark; cell height and column width never depend on content.
- One inverted opaque ink plate per screen for the main action.

## Colors

White stock, near-black ink and a grey ruled structure, with one red that is deliberately scarce.

### Primary
- **Signal Red** (`signal`, #d90018): the only accent. Owns "Tuya" (the user's own booking: filled red mark, bold word), the selection outline of "Seleccionada", the changed-slot hold ("Nueva" note plus a 2px outline), error text and error borders, the focus-to-confirm hover of the plate button, and the input caret.
- **Signal Wash** (`signal-wash`, #fdecee): the cell fill of "Tuya" only.

### Neutral
- **Paper** (`paper`, #ffffff): page stock, free cells, buttons, fields.
- **Wash** (`wash`, #f3f4f5): the second layer: header band of the grid, court-name column, ocupada cells, actionable-cell hover.
- **Ink** (`ink`, #141414): text, structural rules (1.5px), focus outline (3px), the filled mark of "ocupada", the plate.
- **Ink Soft** (`ink-soft`, #55595f): secondary text, minutes in the hours row, notes, closed and unavailable cells (7:1 on paper).
- **Rule** (`rule`, #c9ccd1): 1px hairlines between cells, disabled button border.
- **Edge** (`edge`, #80858c): control borders and the ruled-through mark (3.6:1 on paper).

### Named Rules
**The Scarce Signal Rule.** Red marks the thing the user is acting on or must notice: their own booking, the live selection, a slot that changed, an error. It is never decoration, never a heading colour, never a fill on chrome.
**The Selection Exception Rule.** Seleccionada's red outline is the one deliberate exception beside Tuya and the changed-slot hold: the selection is the live state the user is acting on. It earns red by that role and sets no precedent for other red outlines.
**The Colour-Reinforces Rule.** A state must be fully legible in greyscale from its word and mark. Colour is added second.

## Typography

**Display Font:** Archivo Variable (with system-ui, sans-serif), width axis used: 100% for text, 90% for headings and cells.
**Body Font:** Archivo Variable, same family.
**Label/Mono Font:** none; tabular figures are switched on globally.

**Character:** A neutral grotesque in few sizes, slightly condensed (90% width) where space is tight or a heading needs to read as timetable lettering. Hierarchy is weight and size, never a second face.

### Hierarchy
- **Display** (700, 1.75rem rising to 2.5rem from the sm breakpoint, line-height 1, tight tracking, 90% width): the date on the day line.
- **Headline** (700, 1.25rem, tight tracking, 90% width): the product name in the top rule.
- **Title** (700, 1.0625rem, line-height 1): hour labels in the grid head, with the minutes set at 0.8125rem, 400, ink-soft.
- **Body** (400 and 600, 0.9375rem, line-height 1.45): UI copy, buttons at 600. Form and message blocks are capped by their container (max-w-sm to max-w-xl).
- **Label** (400, 0.75rem, line-height 1.25, 90% width): grid cell words and notes; court names at 0.8125rem, 700. No letter-spacing, no uppercase.

### Named Rules
**The Few Sizes Rule.** The ramp is 0.75, 0.8125, 0.9375, 1.0625, 1.25, 1.75, 2.5rem. A new surface picks from it; it does not add a size.
**The Tabular Rule.** Hours, dates and counts are set tabular; the hour is large and its minutes quiet.

## Layout

A ruled table inside a page capped at 96rem with 1rem side padding (1.5rem from sm). The grid is a CSS grid: a sticky 5.75rem court column and one minimum 5.75rem column per hour, every row at least 3.875rem tall, so a booker's name or a "Nueva" note never makes the table jump. Columns do not depend on content, so selecting a cell cannot reflow the grid. The scroller has its own container (height up to the viewport minus 15rem, minimum 12rem), snaps horizontally to whole hours with the court column as scroll padding, and the page itself never overflows on a phone. The sticky corner cell carries the visible-range guide ("08-13 h"), recomputed on scroll.

The page rhythm is small and even: gaps of 0.25, 0.5, 0.75 and 1.125rem inside components, 0.75rem to 1.5rem between blocks. The legend sits under the grid as a row of the same marks. Controls are at least 2.75rem tall (44px). The action plate is sticky to the bottom of the viewport and appears only once a cell is active.

## Elevation & Depth

Flat. No drop shadows and no gradients. Depth is conveyed by ruled lines and by two tonal layers (paper and wash); sticky headers rely on the wash fill and a heavier 1.5px ink rule. The only `box-shadow` in the build is `inset` and acts as an outline for the selected cell (3px) and the changed-slot hold (2px), so the outline cannot change cell size. The single gradient is the 2px diagonal rule of the "no disponible" mark.

### Named Rules
**The Flat Page Rule.** Nothing floats off the page. A new element is separated by a rule or a layer change, not by a shadow, blur or lift.

## Shapes

Hairline-square. Radius is 0 on every control, field, cell and container. Borders come in two weights: 1px `rule` hairlines between cells, and 1.5px `ink` rules for the outer frame, the header underline, controls and containers. The top of the page carries a 6px ink rule, the Fahrplan header band. The signature geometry is the 0.8125rem square mark: hollow (libre), filled ink (ocupada), diagonal-ruled (no disponible), filled red (tuya), heavy red-bordered 3px (seleccionada); hidden on cerrada.

## Components

### Buttons
- **Shape:** square, 1.5px ink border, min-height 2.75rem, horizontal padding 1.125rem, weight 600.
- **Default:** paper fill, ink text. Hover inverts to ink fill with paper text (150ms, ease-out). Disabled: rule border, ink-soft text.
- **Plate button:** ink fill, paper text; hover turns signal red. At most one per screen, for the main action. Disabled: wash fill.
- **Focus:** a 3px ink outline offset 2px on everything (paper on the plate).

### Inputs / Fields
- **Style:** paper fill, 1.5px `edge` border, square, 2.75rem tall, 0.75rem side padding, red caret.
- **Focus:** border goes ink with the 3px ink outline at offset 0. **Error:** `aria-invalid` turns the border signal red.

### Navigation
- A top rule: 6px ink rule above, 1.5px below. Product name left in headline type, links as text with a 3px underline (ink when active, transparent otherwise, ink-soft until hover), user name and a "Salir" button right. On a phone the links wrap beneath onto their own row. A skip link jumps to the content.

### Court Grid (signature)
An ARIA grid with one tab stop and arrow-key movement. Header row and court column are wash, sticky, with 1.5px ink rules; cells are ruled paper boxes. Each cell shows its mark above its word (Libre, Ocupada, No disponible, Seleccionada, Tuya, Cerrada). Ocupada cells take wash fill; unavailable and closed take ink-soft text; Tuya takes signal-wash and bold. Actionable cells show wash on hover and a pointer. A slot that changed since the last poll keeps a 2px red outline and a red "Nueva" note until the user acts. In the admin view the booker's name appears as an ink-soft note.

### Action Plate
The whole action band is ink with paper text, sticky to the bottom, with transparent paper-outlined buttons and one paper-filled plate button. It carries the selected cell's court and hour and appears only when a cell is active.

### Notices and containers
Messages are ruled bands (1.5px ink top and bottom) or fully ruled square boxes with 1.5px ink borders and 1.5rem padding; errors swap the rule and the text to signal red.

## Do's and Don'ts

### Do:
- **Do** give every state a word plus a fixed-position mark, and let colour only reinforce it.
- **Do** keep cell height (3.875rem) and column width (5.75rem) independent of content.
- **Do** use ink and the paper/wash layers for structure; separate with 1px `rule` hairlines or 1.5px ink rules.
- **Do** keep one inverted plate for the primary action per screen.
- **Do** use signal red only for Tuya, the selection, the changed-slot hold and errors.
- **Do** keep controls at least 2.75rem tall and use the 3px ink focus outline.

### Don't:
- **Don't** add rounded corners, cards, drop shadows, blur or gradient fills.
- **Don't** introduce a second accent or use red as chrome, heading colour or decoration.
- **Don't** convey state by colour alone, or hide a state word.
- **Don't** make the grid reflow when a cell is selected or a name is added.
- **Don't** add typefaces or sizes outside the ramp above.
