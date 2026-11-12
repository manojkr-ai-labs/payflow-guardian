---
name: PayFlow Guardian
colors:
  surface: '#faf8ff'
  surface-dim: '#d1d8ff'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f2ff'
  surface-container: '#ebedff'
  surface-container-high: '#e4e7ff'
  surface-container-highest: '#dce1ff'
  on-surface: '#001551'
  on-surface-variant: '#414753'
  inverse-surface: '#132a71'
  inverse-on-surface: '#efefff'
  outline: '#717785'
  outline-variant: '#c1c6d6'
  surface-tint: '#005cba'
  primary: '#0058b2'
  on-primary: '#ffffff'
  primary-container: '#0070e0'
  on-primary-container: '#f9f9ff'
  inverse-primary: '#abc7ff'
  secondary: '#475f8a'
  on-secondary: '#ffffff'
  secondary-container: '#b4ccfe'
  on-secondary-container: '#3e5681'
  tertiary: '#983f00'
  on-tertiary: '#ffffff'
  tertiary-container: '#bf5100'
  on-tertiary-container: '#fff8f5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d7e3ff'
  primary-fixed-dim: '#abc7ff'
  on-primary-fixed: '#001b3f'
  on-primary-fixed-variant: '#00458f'
  secondary-fixed: '#d7e3ff'
  secondary-fixed-dim: '#afc7f8'
  on-secondary-fixed: '#001b3f'
  on-secondary-fixed-variant: '#2e4770'
  tertiary-fixed: '#ffdbcb'
  tertiary-fixed-dim: '#ffb692'
  on-tertiary-fixed: '#341100'
  on-tertiary-fixed-variant: '#793000'
  background: '#faf8ff'
  on-background: '#001551'
  surface-variant: '#dce1ff'
typography:
  display-currency:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  currency-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  title-page:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  title-page-mobile:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  title-section:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0em
  body-default:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-medium:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0em
  body-secondary:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  metadata-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.06em
  chip-label:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system establishes an exact, disciplined, and utilitarian financial operations interface inspired directly by mission-critical enterprise commerce consoles. The emotional tone is authoritative, sober, and reassuringly precise—engineered to handle high-value ledger events, dispute resolution, and settlement audits without visual friction.

Key principles:
- **Quiet Precision**: Zero illustrative fluff, decorative gradients, or blurred translucent panels. Visual weight is derived solely from tabular precision, rigorous borders, and crisp typography.
- **Immediate Legibility**: Financial operators must parse dispute states, ledger balances, and payment outcomes instantaneously. Visual hierarchy is established through contrast between deep navy titles, structured hairline containers, and standardized outcome tags.
- **Institutional Trust**: Surfaces reflect traditional banking confidence translated into a contemporary enterprise web standard.

## Colors

The palette is engineered for institutional fintech workflows, anchoring actions with high-visibility enterprise blues against neutral slate grounds.

### Core Canvas & Structure
- **Canvas / Page Background**: `#F5F7FA` (cool, stable ground reducing eye strain across dense monitoring sessions)
- **Surface / Card Background**: `#FFFFFF` (pure white for operational data modules)
- **Hairline Border**: `#E6E8EB` (1px structural boundaries defining containers, tabular cells, and secondary controls)
- **Primary Text**: `#001C64` (deep enterprise navy used for primary labels, data values, and headers)
- **Secondary Text / Metadata**: `#687173` (subdued cool slate for auxiliary labels, timestamps, and table headers)

### Action & Interaction Palette
- **Primary Action Default**: `#0070E0`
- **Primary Action Hover / Active**: `#003087`
- **Interactive Focus Ring**: `rgba(0, 112, 224, 0.40)` (2px outer offset)
- **Disabled Elements**: `#CCD2D8` background with `#8C96A0` text

### Status Palette (Flat, High-Readability Chips)
- **Completed / Settled**: Text `#0E7A3D` on Surface `#E8F6EE`
- **Pending / Action Required**: Text `#8A5A00` on Surface `#FFF6E0`
- **Failed / Disputed**: Text `#B42318` on Surface `#FDECEC`
- **Refunded / Archived**: Text `#3D4C66` on Surface `#EEF2F6`

Color usage must strictly eschew gradients, ambient colored glows, or decorative secondary accent hues.

## Typography

The type system is standardized around **Inter**, optimized for density and numerical accuracy.

- **Tabular Figures**: All currency, numeric volume metrics, transaction identifiers, and dates must explicitly enforce CSS `font-variant-numeric: tabular-nums lining-nums`. This prevents layout shifts across dynamic polling tables.
- **Section & Column Labels**: Metadata headers, table columns, and form section eyebrows utilize `metadata-caps` (12px, 600 weight, uppercase with strict `0.06em` tracking) styled in `#687173`.
- **Hierarchical Text Pairing**: Primary content and actionable rows use `#001C64`. Contextual breadcrumbs, timestamps, and help text strictly use `#687173`.

## Layout & Spacing

The layout is grounded in a predictable, rhythmic 8px baseline grid designed to preserve spatial economy in dense desktop monitoring workflows.

### Grid & Form Factors
- **Desktop (1024px and above)**: 12-column layout with 24px (`gutter-desktop`) gutters and 32px (`margin-desktop`) outer canvas margins. Maximized for broad side-by-side transaction inspection and dual-pane reconciliation views.
- **Tablet (768px – 1023px)**: 8-column layout with 16px (`gutter`) gutters and 24px page margins.
- **Mobile (Below 768px)**: 4-column fluid layout with 16px margins. Data grids collapse into stacked hairline transaction cards; secondary metrics convert to horizontal scroll tracks.

### Spacing Philosophy
- Component inner paddings strictly respect the 4px/8px step scale (`space-xs` to `space-xl`).
- High-density table cells: 8px vertical padding, 16px horizontal padding.
- Card padding: Standardized at 24px (`space-lg`) on desktop and 16px (`space-md`) on mobile viewports.

## Elevation & Depth

This design system deliberately restricts layered elevation to maintain an authoritative, low-distraction work environment.

### Depth Hierarchy
1. **Flat Structural Containers (Default)**: `#FFFFFF` surface bounded by a crisp `1px solid #E6E8EB`. No shadow. Used for data tables, form groupings, summaries, and static metric modules.
2. **Raised Operational Cards**: Applied only to actionable or selected card entities (e.g., active dispute cards or contextual flyouts). Configured strictly as:
   `box-shadow: 0 1px 2px rgba(0, 28, 100, 0.06); border: 1px solid #E6E8EB;`
3. **Modals & Overlays**: Used for transaction refunds and critical confirmation sheets:
   `box-shadow: 0 4px 16px rgba(0, 28, 100, 0.12); border: 1px solid #E6E8EB;`
   Paired with a solid backdrop wash of `rgba(0, 28, 100, 0.32)` (no blur filters).

Z-index and shadow usage must remain lean; hierarchy is established via hairline nesting and contrast rather than vertical elevation.

## Shapes

The geometry balances modern software clarity with enterprise solidity:

- **Cards & Data Modules**: Strictly fixed at `8px` (`rounded-md` / level 2 baseline).
- **Interactive Buttons & Input Controls**: Styled with a tighter `6px` radius (`0.375rem`) to maintain architectural firmness.
- **Status Chips**: Standardized at `4px` (`rounded-sm`) to remain compact, flat, and distinct from full-sized action components. Never render status indicators as circular pills.

## Components

### Buttons
- **Primary Button**: Solid `#0070E0` fill, `#FFFFFF` text, 6px border-radius, font size 14px (weight 500), height 40px, padding 0 16px. Hover state: `#003087`. Focus state: 2px ring `#0070E0` with 40% opacity.
- **Secondary Button**: `#FFFFFF` surface, 1px solid `#E6E8EB`, `#001C64` text, 6px border-radius. Hover: `#F5F7FA` surface, `#001C64` border.
- **Destructive Button**: Flat surface with `#FDECEC` background, `#B42318` text, and border-radius 6px. Hover: `#FCD7D7`.

### Status Chips
Small, flat metadata badges (height 22px, padding 2px 8px, 4px border-radius, font size 12px, font weight 600, no drop shadows):
- **Completed**: Background `#E8F6EE`, Text `#0E7A3D`
- **Pending**: Background `#FFF6E0`, Text `#8A5A00`
- **Failed**: Background `#FDECEC`, Text `#B42318`
- **Refunded**: Background `#EEF2F6`, Text `#3D4C66`

### Form Inputs & Selects
- **Height**: 40px.
- **Surface**: `#FFFFFF`, 1px solid `#E6E8EB`, 6px border-radius, text `#001C64` (14px).
- **Placeholder**: `#687173`.
- **Focus**: Border color `#0070E0`, 2px outer glow in `rgba(0, 112, 224, 0.40)`.
- **Validation**: Error state uses `#B42318` border with 12px caption error copy below the field.

### Checkboxes & Radio Controls
- **Checkboxes**: 18x18px box, 1px solid `#CCD2D8`, 4px radius. Checked state: `#0070E0` background with crisp white check icon.
- **Radios**: 18x18px circular container, 1px solid `#CCD2D8`. Selected state: `#0070E0` center pip (6px diameter).

### Data Tables
- **Header Cell**: Background `#F5F7FA`, 1px border bottom `#E6E8EB`, text 12px uppercase `#687173` with `0.06em` tracking, height 36px.
- **Body Cell**: Background `#FFFFFF`, 1px border bottom `#E6E8EB`, text 14px `#001C64`, tabular numeric values, height 48px.
- **Row Hover**: Subtle `#F5F7FA` fill transition.

### Operational Cards
- Standard containers feature a `#FFFFFF` fill, 1px continuous border in `#E6E8EB`, and an 8px border-radius. Raised variants feature the subtle `0 1px 2px rgba(0, 28, 100, 0.06)` box shadow.