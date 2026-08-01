# Frontier Style Frontend Redesign

## Goal

Rebuild the local Astro frontend so every portfolio-facing page shares the current light visual language of `api.frontier-intelligence.tech`. Preserve the portfolio's existing routes, content, page-level information architecture, and section order. This work is local only: it must not modify deployment scripts or publish changes.

## Scope

Included pages:

- Home
- Project and blog indexes
- Project and blog detail pages
- About and photos
- Existing ChefMate, TripPlan, and GraphRAG presentation pages, without changing their application behavior or API integration

Excluded work:

- Content rewrites
- Route changes
- Deployment configuration and deployment actions
- New dark theme or a theme toggle

## Visual Direction

The site uses a single light paper theme, modeled on the reference site's current UI rather than the old deployed portfolio.

### Tokens

| Role | Value | Use |
| --- | --- | --- |
| Paper | `#f4efea` | Page canvas and low-emphasis surfaces |
| Panel | `#ffffff` | Cards, navigation, dialogs, content panels |
| Ink | `#383838` | Text, 2px structural borders, offset shadows |
| Yellow | `#ffde00` | Current navigation item, primary actions, ticker |
| Ice blue | `#6fc2ff` | Secondary actions, selection and code highlights |
| Soft blue | `#e6f5fb` | Response/code sections and quiet information panels |
| Muted ink | `#818181` | Metadata and secondary labels |

Typography uses Lora for readable prose and content copy. Aeonik Mono with JetBrains Mono fallback is used for labels, navigation, controls, code, and compact headings. Header hierarchy remains within the current layout but gains the target site's high-contrast mono display treatment.

The canvas receives a subtle 26px grid. Surfaces use square to 2px corners, 2px ink borders, and intentional hard offset shadows. There are no gradients, glass effects, large rounded containers, purple-led palette, or dark mode.

## Shared UI System

`global.css` becomes the source of truth for tokens, typography, shell, focus behavior, reduced-motion behavior, and responsive breakpoints. Component-level styles only express structural differences specific to a page.

Shared primitives:

- Framed navigation bar with active yellow state and compact mono controls
- Primary, secondary, and ink buttons with target-style press/hover movement
- Bordered cards with header, content, tag, and footer regions
- Hard-shadow panels for content and dialogs
- Technical labels and tags with monospace type and crisp outlines
- Article prose with generous serif reading rhythm, underlined links, inline code, and ink code blocks
- Photo tile and lightbox treatment consistent with the panel system
- Footer and back-to-top controls aligned to the shared shell

## Page Mapping

| Existing page layout | Visual treatment |
| --- | --- |
| Home hero split layout | Retain left identity block, right API demo and system chips; restyle as the reference's editorial hero and bordered response console |
| Project and blog indexes | Retain card grids; use technical card headers, colored case labels, tags, hard shadows, and precise hover states |
| Project and blog details | Retain article flow; add reference-style back action, metadata rail, prose rhythm, code blocks, and image framing |
| About | Retain profile and social grouping; render as framed editorial profile panel and action set |
| Photos | Retain image masonry/grid and lightbox behavior; turn tiles and dialog into bordered gallery panels |
| System pages | Preserve interactive functionality and forms; map existing utility styles through controlled compatibility selectors plus targeted component changes |

## Interaction and Accessibility

- All interactive elements retain visible keyboard focus with an ice-blue outline.
- Hover states use a small, stable offset and shadow change; active states remove the shadow to simulate pressing.
- Reveal and marquee motion respect `prefers-reduced-motion`.
- Navigation remains horizontally usable on narrow screens; desktop layouts collapse to one column without reordering content.
- Buttons and form inputs maintain a minimum touch target and never rely on color alone for state.

## Verification

- Run the production build after implementation.
- Start the local dev server and compare desktop and mobile screenshots of the home page, each index, a detail page, about, and photos.
- Confirm no local UI exposes a dark theme control or old purple/glass styling.
- Verify existing photo lightbox, copy-contact action, navigation, external links, and system-page forms still function.

## Design Review

The design is intentionally a visual-system migration, not a layout redesign. The reference influence is applied to palette, surface construction, type hierarchy, controls, cards, code treatment, and motion while preserving this portfolio's existing content and page composition.
