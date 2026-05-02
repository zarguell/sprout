# Design System for Sprout

## 1. Visual Theme & Atmosphere

Sprout's design system is a **warm, organic plant care dashboard** inspired by the Starbucks retail aesthetic but adapted for a home gardening context. The canvas uses a warm cream (`#f2f0eb`) that evokes natural materials — garden pots, soil, and sunlight — while the signature **Sprout Green** (`#00754A`) anchors primary actions and key moments. The greens come in three calibrated shades (Primary, Dark, Light) each mapped to a specific surface role.

Typography carries the approachable, confident voice. **Inter** (Google Fonts) serves as the primary typeface — a humanist sans-serif with excellent readability and a warm, friendly character. The system uses tight `-0.01em` letter-spacing for a confident, modern feel without being severe. Unlike Starbucks' three-typeface system, Sprout uses a single typeface throughout for simplicity and consistency.

The surfaces breathe through rounded geometry. Every button is a 50px full-pill. Cards take a 12px rounded-rectangle. The floating "Add Plant" button — a 56px circular button in Sprout Green (`#00754A`) — is the product's signature depth move: it floats bottom-right with a layered shadow stack and compresses via `scale(0.95)` on press. Elevations are restrained — card shadows stay at a whispered `0.14/0.24` alpha. The whole system feels like clean garden signage: legible, warm, and never shouting.

**Key Characteristics:**
- Three-tier green brand system (Primary / Dark / Light) each mapped to a distinct surface role
- Amber/gold accent for overdue/warning states instead of harsh red — warmer, plant-appropriate
- Warm-neutral canvas (`#f2f0eb`) instead of cold white — references natural garden materials
- Single typeface (Inter) with tight `-0.01em` letter-spacing for consistency and simplicity
- Full-pill buttons (`50px` radius) universal, `scale(0.95)` active press the signature micro-interaction
- Floating "Add Plant" circular CTA (`56px`, Sprout Green fill, layered shadow stack) — the product's signature elevation element
- Plant photo cards designed as hero images — full-bleed or soft-shadow cards that let the plant photography shine
- 12px card radius + whisper-soft shadows keep content cards flat-plus-hint-of-lift
- Rem-based spacing scale anchored at 1.6rem (~16px) = `--space-3`, stepping to 6.4rem (~64px)

**Color-block page rhythm:** Cream canvas → White content cards → Light green wash for overdue indicators → Sprout Green CTAs and primary actions — a natural, organic flow that mirrors the plant care experience.

## 2. Color Palette & Roles

### Primary Greens

- **Sprout Green** (`#00754A`): The primary brand green. Used on primary filled CTAs (Water, Fertilize, Add Plant), the floating action button, and as the main brand signal.
- **Sprout Green Dark** (`#006241`): A deeper forest green for headings, section titles, and moments requiring more visual weight. Used similar to Starbucks Green on h1 headings.
- **Sprout Green Light** (`#d4e9e2`): A pale mint wash for light green utility surfaces, success states, and subtle background tints.

### Accent & Warning

- **Amber** (`#f59e0b`): Primary warning/overdue accent. Used for overdue task badges (amber ≥1 day overdue), warning states, and "needs attention" indicators. Warmer and more plant-appropriate than harsh red.
- **Amber Light** (`#fef3c7`): Light amber background for overdue task row highlights.
- **Red** (`#dc2626`): Reserved for destructive actions (delete plant, delete photo) and critical errors only. Not used for overdue states.

### Surface & Background

- **White** (`#ffffff`): Primary card and modal surface.
- **Neutral Warm** (`#f2f0eb`): The warm cream **primary page canvas**. References natural garden materials — terracotta, soil, sunlight.
- **Neutral Cool** (`#f9f9f9`): Subtle cool-gray surface for dropdown menus, form-card wraps, and quiet utility containers.
- **Ceramic** (`#edebe9`): A slightly warmer/darker cream for zone separators and soft page-section washes.

### Neutrals & Text

- **Text Black** (`rgba(0, 0, 0, 0.87)`): Primary heading and body text color on light surfaces. Not pure black — an 87%-opacity black that reads warmer.
- **Text Black Soft** (`rgba(0, 0, 0, 0.58)`): Secondary/metadata text on light surfaces (plant species, timestamps, task notes).
- **Text White** (`rgba(255, 255, 255, 1)`): Primary heading/body text on dark green surfaces.
- **Text White Soft** (`rgba(255, 255, 255, 0.70)`): Secondary text on dark-green surfaces.

### Semantic

- **Success Light** (`#d4e9e2` at 33% opacity): Form valid-field tint background, task completed success state.
- **Error Light** (`rgba(220, 38, 38, 0.05)`): Invalid-field tint on forms, destructive action confirmation.

### Black / White Alpha Ladders

Two parallel translucent scales for overlay and secondary-text use:
- `rgba(0,0,0,0.06)` through `rgba(0,0,0,0.90)` in 10% steps — for dark overlays on light surfaces
- `rgba(255,255,255,0.10)` through `rgba(255,255,255,0.90)` in 10% steps — for light overlays on dark surfaces

### Gradient System

No structural gradient tokens. Surface hierarchy is solid-color-block throughout — the system relies on its cream/green surface palette rather than gradients.

## 3. Typography Rules

### Font Family

- **Primary:** `Inter, "Helvetica Neue", Helvetica, Arial, sans-serif` — Google Fonts humanist sans-serif with excellent readability and warm character
- **Monospace:** `"SF Mono", "Monaco", "Inconsolata", "Fira Mono", "Droid Sans Mono", "Source Code Pro", monospace` — for timestamps, dates, and code-like data

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|----------------|-------|
| Display | 3.6rem / 58px | 600 | 1.2 | -0.01em | Largest hero display (rare) |
| H1 | 24px | 600 | 36px | -0.01em | Sprout-Green-Dark primary heading |
| H2 | 24px | 400 | 36px | -0.01em | Regular-weight section title in Text Black |
| H3 | 20px | 600 | 28px | -0.01em | Subsection heading |
| Body Large | 19px | 400 | 33px (~1.75) | -0.01em | Hero intro copy |
| Body | 1.6rem / 16px | 400 | 1.5 (24px) | -0.01em | Default body copy |
| Small | 1.4rem / ~14px | 400–600 | 1.5 | -0.01em | Button label, metadata, form labels |
| Micro | 1.3rem / ~13px | 400 | 1.5 | -0.01em | Caption micro-copy, timestamps |

**Letter-spacing tokens:**
- `letterSpacingNormal`: `-0.01em` (default — tight, characteristic)
- `letterSpacingLoose`: `0.1em` (emphasized caps)

**Line-height tokens:**
- `lineHeightNormal`: `1.5` (body)
- `lineHeightCompact`: `1.2` (display/buttons)

### Principles

- **Tight negative tracking (`-0.01em`)** is applied universally — the entire product reads slightly compressed for a confident, modern feel.
- **Weight shifts carry hierarchy, not size shifts.** H1 and H2 share the same 24px/36px size; only weight (600 vs 400) and color (Sprout-Green-Dark vs Text Black) separate them.
- **Body text never goes pure black** — it sits at `rgba(0,0,0,0.87)` to match the warm-neutral canvas temperature.

## 4. Component Stylings

### Buttons

**1. Primary Filled — "Water / Fertilize / Add Plant"**
- Background: `#00754A` (Sprout Green)
- Text: `#ffffff`
- Border: `1px solid #00754A`
- Radius: `50px` (full pill)
- Padding: `7px 16px`
- Font: Inter, 16px, weight 600, letter-spacing `-0.01em`
- Active state: `transform: scale(0.95)`
- Transition: `all 0.2s ease`

**2. Primary Outlined — "View Archive / Cancel"**
- Background: transparent
- Text: `#00754A` (Sprout Green)
- Border: `1px solid #00754A`
- Same radius/padding/active/transition as Primary Filled

**3. Destructive — "Delete Plant / Delete Photo"**
- Background: `#dc2626` (Red)
- Text: `#ffffff`
- Border: `1px solid #dc2626`
- Radius: `50px`, Padding: `7px 16px`
- Font: 14px, weight 600
- Requires confirmation modal before action

**4. Destructive Outlined — "Archive"**
- Background: transparent
- Text: `#dc2626` (Red)
- Border: `1px solid #dc2626`
- Radius: `50px`, Padding: `7px 16px`
- Font: 14px, weight 600

**5. Floating Action Button — "Add Plant"**
- Background: `#00754A` (Sprout Green)
- Icon: `#ffffff` (plus icon)
- Size: `5.6rem / 56px`
- Radius: `50%` (full circle)
- Fixed bottom-right, `-0.8rem` touch offset for extra tap comfort
- Shadow stack: base `0 0 6px rgba(0,0,0,0.24)` + ambient `0 8px 12px rgba(0,0,0,0.14)`
- Active state: ambient shadow fades + `scale(0.95)`
- This is the product's signature elevation element

**6. Task Complete Button — "Complete"**
- Background: `#00754A` (Sprout Green)
- Text: `#ffffff`
- Radius: `50px`
- Padding: `7px 16px`
- Font: 14px, weight 600
- On click: shows checkmark animation, advances due date

### Cards & Containers

**Plant Card (Dashboard)**
- Background: `#ffffff`
- Radius: `12px`
- Shadow: `0px 0px .5px 0px rgba(0,0,0,0.14), 0px 1px 1px 0px rgba(0,0,0,0.24)`
- Contents:
  - Top: Plant photo thumbnail (400px wide, variable height, maintain aspect ratio)
  - Below photo: Plant name (H3, Sprout-Green-Dark)
  - Location badge (Small, Text Black Soft)
  - Next due task pill (water/fertilize/repot icon + due date)
  - Overdue badge (amber background if ≥1 day overdue)

**Archived Plant Card**
- Same structure as Plant Card
- Overlay: subtle grayscale filter on photo
- Badge: "Archived" pill with archive reason
- No task information displayed

**Task Card**
- Background: `#ffffff`
- Radius: `12px`
- Shadow: same as Plant Card
- Layout: horizontal row with:
  - Left: task type icon (water drop / leaf / pot)
  - Center: task label, due date, interval badge
  - Right: Complete button (green filled) or Edit/Delete icons

**Dropdown Menu**
- Background: `#f9f9f9` (Neutral Cool)
- Menu items at `24px / weight 400` in Text Black
- No border — just background surface shift against white nav

**Modal**
- Padding: `2.4rem`
- Top padding: `8.8rem` — leaves room for close button / header
- Radius: `12px`
- Background: `#ffffff`

### Inputs & Forms

**Floating Label Input**
- Label floats above the input border when focused/filled
- Desktop label font size: `1.9rem` default, animates to `1.4rem` when active
- Mobile label font size: `1.6rem` default, animates to `1.3rem` active
- Label horizontal offset: `12px` from left
- Active label translate: up to `-12px` with `-50%` Y translation
- Field padding: `12px`
- Form horizontal padding: `1.6rem`
- Validation: valid-field gets `rgba(212, 233, 226, 0.33)` tint; invalid-field gets `rgba(220, 38, 38, 0.05)` tint
- Border: `1px solid #d6dbde` (neutral)
- Focus: border shifts to Sprout Green (`#00754A`)

**Select Dropdown**
- Background: `#ffffff`
- Border: `1px solid #d6dbde`
- Radius: `4px`
- Padding: `12px`
- Right side: chevron-down icon in Text Black Soft

### Navigation

**Global Nav (top bar)**
- Fixed position, height: `64px` mobile → `72px` tablet → `83px` desktop
- Background: `#ffffff`
- Shadow: `0 1px 3px rgba(0,0,0,0.1), 0 2px 2px rgba(0,0,0,0.06), 0 0 2px rgba(0,0,0,0.07)`
- Left: Sprout logo/wordmark
- Center: nav links (Dashboard, Archive)
- Right: user avatar + dropdown

### Image Treatment

- **Plant photos**: Hero images on plant cards — full-bleed or soft-shadow cards. Variable height to preserve aspect ratio (portrait whole-plant vs landscape close-up).
- **Thumbnails**: 400px wide, height auto-scaled, maintain aspect ratio. Never upscale if original is narrower than 400px.
- **Placeholder**: Simple leaf/plant icon in Sprout-Green-Light when no photo available.
- **Image fade-in**: `opacity 0.3s ease-in` transition on image load.

### Badges & Pills

**Task Type Pill**
- Background: Sprout-Green-Light (`#d4e9e2`)
- Text: Sprout-Green-Dark (`#006241`)
- Radius: `50px`
- Padding: `4px 12px`
- Content: task type icon + label (Water / Fertilize / Repot / Custom)

**Overdue Badge**
- Background: Amber (`#f59e0b`)
- Text: `#ffffff`
- Radius: `50px`
- Padding: `4px 12px`
- Content: number of days overdue + "days overdue"

**Location Badge**
- Background: transparent
- Text: Text Black Soft (`rgba(0,0,0,0.58)`)
- Font: Small, weight 400
- Prefix: location pin icon

**Interval Badge**
- Background: Neutral Cool (`#f9f9f9`)
- Text: Text Black Soft
- Radius: `4px`
- Padding: `2px 8px`
- Content: "Every 7 days" / "Every 14 days" etc.

## 5. Layout Principles

### Spacing System

Rem-based semantic scale (anchored `1rem = 10px` via `font-size: 62.5%` root):

| Token | Rem | Pixels | Typical Use |
|-------|-----|--------|-------------|
| `--space-1` | `0.4rem` | 4px | Tightest inline padding |
| `--space-2` | `0.8rem` | 8px | Small gap, button vertical padding |
| `--space-3` | `1.6rem` | 16px | Default — card padding, outer gutter xs |
| `--space-4` | `2.4rem` | 24px | Section inner spacing, outer gutter md |
| `--space-5` | `3.2rem` | 32px | Major between-section spacing |
| `--space-6` | `4.0rem` | 40px | Large gaps, outer gutter lg |
| `--space-7` | `4.8rem` | 48px | Section-to-section spacing |
| `--space-8` | `5.6rem` | 56px | Very large breathing — FAB height |
| `--space-9` | `6.4rem` | 64px | Widest section padding |

**Gutter tokens:**
- `--outerGutter: 1.6rem` (16px, default / mobile)
- `--outerGutterMedium: 2.4rem` (24px, tablet)
- `--outerGutterLarge: 4.0rem` (40px, desktop)

**Universal rhythm constant:** `1.6rem` (16px) appears across every page as the default outer gutter, card padding baseline, and text size 3 body.

### Grid & Container

- Dashboard plant card grid: responsive 2-3-4 column grid
- Plant detail page: single column with photo gallery + task list
- Modal widths: small (`343px`), medium (`500px`), large (`720px`)

### Whitespace Philosophy

Whitespace carries the feeling of "plenty of space in a garden." Section padding leans generous (32–48px). Content blocks are separated by whitespace rather than dividers. The cream canvas (`#f2f0eb`) is itself a visual breath between white cards.

### Border Radius Scale

| Value | Use |
|-------|-----|
| `12px` | Cards, modals, plant tiles |
| `50px` | All buttons — full-pill radius |
| `50%` | Circular icons, FAB, avatar thumbnails |
| `4px` | Input fields, small utility badges |

## 6. Depth & Elevation

| Level | Treatment | Use |
|-----------|-----|
| Card | `0 0 0.5px rgba(0,0,0,0.14), 0 1px 1px rgba(0,0,0,0.24)` | Default content cards — whisper-soft dual-shadow |
| Global Nav | `0 1px 3px rgba(0,0,0,0.1), 0 2px 2px rgba(0,0,0,0.06), 0 0 2px rgba(0,0,0,0.07)` | Triple-layer soft lift on fixed top bar |
| FAB Base | `0 0 6px rgba(0,0,0,0.24)` | Base halo around floating action button |
| FAB Ambient | `0 8px 12px rgba(0,0,0,0.14)` | Stacked directional ambient — floats the FAB forward |

**Shadow philosophy:** Whisper-soft, layered over solid — the system never reaches for a single heavy drop shadow. Instead, it stacks 2–3 low-alpha shadows with different offsets to simulate real-world ambient + direct lighting. The FAB is the most elevated element on any page.

## 7. Do's and Don'ts

### Do

- Use Neutral Warm (`#f2f0eb`) as the page canvas instead of pure white — the warm cream is the signature
- Map the green tiers to their intended surface role — Sprout Green for CTAs, Sprout Green Dark for headings, Sprout Green Light for backgrounds
- Use Amber (`#f59e0b`) for overdue/warning states instead of harsh red — warmer, plant-appropriate
- Keep tracking tight at `-0.01em` on Inter across the whole system
- Use 50px full-pill radius on every button without exception
- Apply `transform: scale(0.95)` as the universal button active state
- Reserve Red (`#dc2626`) for destructive actions only
- Layer 2–3 low-alpha shadows instead of one heavier drop shadow for elevation
- Use the FAB circular button as the persistent "Add Plant" action on the dashboard
- Let the cream canvas breathe between content cards — use whitespace, not dividers
- Maintain aspect ratio for plant photos — never crop or distort

### Don't

- Don't use pure white as the page canvas — the warm cream temperature is load-bearing
- Don't use Red for overdue states — Amber is warmer and more plant-appropriate
- Don't square the corners on buttons — the 50px pill is universal
- Don't introduce gradient fills — the system is color-block throughout
- Don't weight-contrast h1 and h2 by size — the hierarchy comes from weight + color (600 Sprout-Green-Dark vs 400 Text Black)
- Don't use pure black for body text — `rgba(0,0,0,0.87)` matches the warm canvas
- Don't skip the `scale(0.95)` active feedback on buttons — it's a signature micro-interaction
- Don't stack single heavy shadows; always layer 2–3 low-alpha ones
- Don't crop or distort plant photos — maintain full aspect ratio for both portrait and landscape images
- Don't upscale thumbnails — if original < 400px, keep original dimensions

## 8. Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|------|-------------|
| xs | < 480px | Global nav 64px; hamburger menu; single-column layouts; buttons may be full-width |
| Mobile | 480–767px | Global nav 72px; plant grid 2-up; card padding tightens |
| Tablet | 768–1023px | Global nav 83px; plant grid 3-up |
| Desktop | 1024–1439px | Plant grid 4-up |
| XLarge | 1440px+ | Content caps at ~1200px centered; extra cream margin |

### Touch Targets

- Pill buttons at `7px 16px` padding measure ~32px tall — acceptable for homelab app. On mobile, can expand to meet 44px minimum if needed.
- FAB at `56px` is well above minimum.
- FAB uses `--fabTouchOffset: calc(-1 * .8rem)` to extend tap area 8px beyond visual edge.

### Collapsing Strategy

- **Global nav height scales progressively**: 64 → 72 → 83px across breakpoints
- **Plant grid**: 4-up → 3-up → 2-up → 1-up across breakpoints
- **Outer gutter scales**: 16px → 24px → 40px as viewport grows

### Image Behavior

- Plant photos maintain aspect ratio at all breakpoints
- Thumbnails stay 400px wide on desktop, scale down proportionally on mobile
- `opacity 0.3s ease-in` fade-in transition on image load

## 9. Agent Prompt Guide

### Quick Color Reference

- Primary CTA: "Sprout Green (`#00754A`)"
- Primary CTA text: "White (`#ffffff`)"
- Brand heading: "Sprout Green Dark (`#006241`)"
- Page canvas: "Neutral Warm (`#f2f0eb`)"
- Card canvas: "White (`#ffffff`)"
- Heading text on light: "Text Black (`rgba(0,0,0,0.87)`)"
- Body text on light: "Text Black Soft (`rgba(0,0,0,0.58)`)"
- Overdue/warning: "Amber (`#f59e0b`)"
- Destructive: "Red (`#dc2626`)"

### Example Component Prompts

1. "Create a primary Sprout CTA pill button with Sprout Green (`#00754A`) background, white text 'Water', Inter font at 16px weight 600 with `-0.01em` letter-spacing, `50px` border-radius (full pill), `7px 16px` padding. Apply `transform: scale(0.95)` as the active state with a `0.2s ease` transition."

2. "Design a plant card with White (`#ffffff`) background at `12px` border-radius, layered shadow `0 0 0.5px rgba(0,0,0,0.14), 0 1px 1px rgba(0,0,0,0.24)`. Top section: plant photo thumbnail (400px wide, variable height, maintain aspect ratio). Below photo: plant name in Inter 20px weight 600 Sprout-Green-Dark, location badge in Text Black Soft, next due task pill with water icon and due date. If overdue ≥1 day, show amber badge with days overdue. Pad contents `16–24px`."

3. "Build the floating 'Add Plant' action button — `56px` diameter, Sprout Green (`#00754A`) fill, white plus icon centered. Layered shadow: `0 0 6px rgba(0,0,0,0.24)` + `0 8px 12px rgba(0,0,0,0.14)`. Fixed position bottom-right with `-0.8rem` touch offset. Active state collapses ambient shadow with `scale(0.95)`."

4. "Create an overdue task badge — Amber (`#f59e0b`) background, white text showing '3 days overdue', Inter 14px weight 600, `50px` radius, `4px 12px` padding. Used on plant cards when tasks are past due."

5. "Design a task row card — White (`#ffffff`) background, `12px` radius, horizontal layout. Left: water drop icon in Sprout Green. Center: task label 'Water' in Inter 16px weight 600, due date in Text Black Soft, interval badge 'Every 7 days'. Right: 'Complete' pill button in Sprout Green filled. If overdue, background row gets Amber Light (`#fef3c7`) wash."

6. "Build a plant detail photo gallery — horizontal scrollable row of thumbnail images, each 400px wide maintaining aspect ratio. Selected photo shows in a lightbox modal with dark overlay. Upload button as a dashed outlined rectangle with plus icon. Delete photo button shows only on hover with trash icon. Primary photo gets a badge 'Primary' in Sprout Green."

7. "Create a floating label input field — White background, `1px solid #d6dbde` border, `4px` radius, `12px` padding. Label 'Plant name' starts inside the field at 19px, animates up and shrinks to 14px when focused. Focus state: border shifts to Sprout Green (`#00754A`). Valid state: light green tint `rgba(212, 233, 226, 0.33)`."

8. "Design an archive confirmation modal — White card at `12px` radius, `2.4rem` padding. Header: 'Archive Big Monstera?' in Inter 24px weight 600 Sprout-Green-Dark. Body: 'This plant will be moved to the archive. You can restore it later.' in Text Black. Reason dropdown with floating label 'Reason'. Footer: 'Cancel' outlined button + 'Archive' destructive red button."

9. "Create an empty state for no plants — centered illustration of a potted plant in Sprout-Green-Light outline style. Header: 'No plants yet' in Inter 24px weight 600 Sprout-Green-Dark. Body: 'Add your first plant to start tracking.' in Text Black Soft. Below: 'Add Plant' primary filled pill button."

10. "Build a task completion success state — when user clicks 'Complete', button transforms to a checkmark icon with green background, briefly shows 'Done!' text, then the card animates out (slides up with fade). Next due date updates in place with a subtle highlight animation."

### Iteration Guide

When refining existing screens generated with this design system:
1. Focus on ONE component at a time
2. Reference specific color names and hex codes from this document
3. Use natural language descriptions ("warm cream canvas," "three-tier green system") alongside exact values
4. Preserve the 50px pill + `scale(0.95)` active state universally
5. Check that greens are mapped to their correct role (Sprout Green for CTAs, Sprout Green Dark for headings)
6. Don't introduce gradients — the system is color-block
7. Keep Inter tracking at `-0.01em` across the board
8. Maintain plant photo aspect ratios — never crop or distort
9. Use Amber for overdue/warning, Red only for destructive actions

### Implementation Notes

- **Inter** is available on Google Fonts — load via `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">`
- Tailwind config should include the Sprout color palette as custom colors
- Use Tailwind's `@apply` for consistent button/card classes
- CSS custom properties for spacing tokens enable easy theming
- Photo thumbnails are generated server-side by Pillow at 400px wide, maintain aspect ratio, no upscale
