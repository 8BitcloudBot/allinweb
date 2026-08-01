# Frontier Style Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild every local frontend page with the light paper, serif/mono typography, crisp borders, hard shadows, and yellow/ice-blue controls of Frontier Intelligence while preserving the portfolio's routes, content, layout, and behavior.

**Architecture:** Centralize the visual language in `src/styles/global.css`, then give each Astro component semantic classes instead of page-specific inline styling. Preserve the interactive system pages' JavaScript and API calls while applying a compatibility layer to their existing Tailwind-heavy markup. Verify the result with source-level UI contracts, Astro production builds, and browser screenshots at desktop and mobile widths.

**Tech Stack:** Astro 6, Tailwind CSS 4, React 19, CSS custom properties, Node.js built-in test runner, local browser screenshot inspection.

## Global Constraints

- Keep the existing routes, content, page-level information architecture, and section order.
- Modify local frontend source only; do not edit deployment scripts or deploy.
- Use one light theme with paper `#f4efea`, panel `#ffffff`, ink `#383838`, yellow `#ffde00`, ice blue `#6fc2ff`, soft blue `#e6f5fb`, and muted ink `#818181`.
- Use Lora for prose and Aeonik Mono with JetBrains Mono fallback for labels, navigation, controls, code, and compact headings.
- Use square-to-2px corners, 2px ink borders, hard offset shadows, and a subtle 26px grid.
- Remove gradients, glass effects, purple-led styling, large rounded containers, dark-theme controls, and dark-theme output.
- Preserve all existing system-page JavaScript, API integration, photo lightbox behavior, copy action, navigation, and external links.
- Respect keyboard focus, minimum touch targets, responsive content order, and `prefers-reduced-motion`.

## File Map

- `src/styles/global.css`: tokens, base rules, reusable UI primitives, page shells, article prose, system-page compatibility, responsive behavior.
- `src/layouts/BaseLayout.astro`: font loading, permanent light-theme setup, global shell behavior.
- `src/components/layout/Header.astro`: framed brand/navigation structure and route-aware current state.
- `src/components/layout/Footer.astro`: reference-style footer bar.
- `src/components/layout/BackToTop.astro`: semantic floating control with CSS-owned presentation.
- `src/pages/index.astro`: existing hero composition expressed through shared hero/API-console primitives.
- `src/components/projects/ProjectList.astro`, `src/components/projects/ProjectCard.astro`: project index framing and card anatomy.
- `src/components/blog/BlogList.astro`, `src/components/blog/BlogItem.astro`: blog index framing and card anatomy.
- `src/layouts/BlogPostLayout.astro`, `src/pages/projects/[...slug].astro`: article and project-detail actions.
- `src/pages/about.astro`, `src/pages/photos.astro`: editorial profile, photo grid, and lightbox.
- `src/pages/chefmate.astro`, `src/pages/chefmate-graphrag.astro`, `src/pages/tripplan.astro`: system UI semantic hooks only; preserve scripts.
- `tests/ui-contract.test.mjs`: source-level assertions for permanent theme, tokens, semantic primitives, and removal of legacy style signatures.
- `package.json`: `test:ui` script using Node's built-in test runner.

---

### Task 1: Establish the permanent light-theme UI contract

**Files:**
- Create: `tests/ui-contract.test.mjs`
- Modify: `package.json`
- Modify: `src/styles/global.css`
- Modify: `src/layouts/BaseLayout.astro`

**Interfaces:**
- Consumes: existing `BaseLayout` shell and Tailwind import.
- Produces: CSS tokens `--paper`, `--panel`, `--ink`, `--yellow`, `--ice`, `--soft-blue`, `--muted`, `--line`, `--shadow`, and global classes consumed by all later tasks.

- [ ] **Step 1: Add failing UI contract tests**

Create `tests/ui-contract.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');

test('global theme exposes the approved Frontier tokens', async () => {
  const css = await read('src/styles/global.css');
  for (const token of [
    '--paper: #f4efea', '--panel: #ffffff', '--ink: #383838',
    '--yellow: #ffde00', '--ice: #6fc2ff', '--soft-blue: #e6f5fb',
    '--muted: #818181', '--grid-cell: 26px',
  ]) assert.match(css, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('base layout is permanently light and has no theme switch', async () => {
  const layout = await read('src/layouts/BaseLayout.astro');
  assert.match(layout, /color-scheme[^;]*light/);
  assert.doesNotMatch(layout, /ThemeToggle|classList\.toggle\(['"]dark|setItem\(['"]theme/);
});

test('shared interaction styles include focus and reduced motion', async () => {
  const css = await read('src/styles/global.css');
  assert.match(css, /:focus-visible/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
});
```

Add to `package.json` scripts:

```json
"test:ui": "node --test tests/ui-contract.test.mjs"
```

- [ ] **Step 2: Run the UI contract and verify RED**

Run: `npm run test:ui`

Expected: FAIL because `--panel`, `--ice`, and `--soft-blue` are not yet defined with the approved names and the layout still writes theme state to local storage.

- [ ] **Step 3: Replace the global foundation**

In `src/styles/global.css`, retain `@import "tailwindcss"`, replace the token layer with the exact approved variables, and define the permanent canvas:

```css
:root {
  color-scheme: light;
  --paper: #f4efea;
  --panel: #ffffff;
  --ink: #383838;
  --yellow: #ffde00;
  --ice: #6fc2ff;
  --soft-blue: #e6f5fb;
  --muted: #818181;
  --line: 2px solid var(--ink);
  --line-thin: 1px solid var(--ink);
  --shadow: -6px 6px 0 var(--ink);
  --shadow-sm: -3px 3px 0 var(--ink);
  --radius: 2px;
  --grid-cell: 26px;
  --font-prose: "Lora", "Noto Serif SC", Georgia, serif;
  --font-ui: "Aeonik Mono", "JetBrains Mono", "IBM Plex Mono", monospace;
}

html { background: var(--paper); scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background-color: var(--paper);
  background-image:
    linear-gradient(rgb(56 56 56 / 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgb(56 56 56 / 0.055) 1px, transparent 1px);
  background-size: var(--grid-cell) var(--grid-cell);
  font-family: var(--font-prose);
}

:focus-visible { outline: 3px solid var(--ice); outline-offset: 3px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation: none !important; transition: none !important; }
}
```

Keep legacy color aliases only where system-page scripts require them, mapping them to approved tokens. Delete the universal `* { border-radius: ... !important; }` rule so component geometry remains deliberate.

In `src/layouts/BaseLayout.astro`, keep the existing font links and replace the local-storage script with:

```astro
<meta name="color-scheme" content="light" />
<style is:global>html { color-scheme: light; }</style>
```

- [ ] **Step 4: Verify GREEN**

Run: `npm run test:ui && npm run build`

Expected: all UI contract tests PASS and Astro exits successfully with generated routes.

- [ ] **Step 5: Commit the foundation**

```bash
git add tests/ui-contract.test.mjs package.json src/styles/global.css src/layouts/BaseLayout.astro
git commit -m "feat: establish Frontier light theme foundation"
```

### Task 2: Rebuild the shared shell and home page

**Files:**
- Modify: `tests/ui-contract.test.mjs`
- Modify: `src/components/layout/Header.astro`
- Modify: `src/components/layout/Footer.astro`
- Modify: `src/components/layout/BackToTop.astro`
- Modify: `src/pages/index.astro`
- Modify: `src/styles/global.css`

**Interfaces:**
- Consumes: Task 1 tokens and permanent light canvas.
- Produces: `.site-header`, `.site-nav`, `.ui-button`, `.api-console`, `.site-footer`, and `.back-to-top` primitives.

- [ ] **Step 1: Add failing shell assertions**

Append to `tests/ui-contract.test.mjs`:

```js
test('shared shell uses semantic Frontier primitives', async () => {
  const [header, footer, top, home] = await Promise.all([
    read('src/components/layout/Header.astro'),
    read('src/components/layout/Footer.astro'),
    read('src/components/layout/BackToTop.astro'),
    read('src/pages/index.astro'),
  ]);
  assert.match(header, /aria-current/);
  assert.match(header, /nav-utility/);
  assert.match(footer, /site-footer__meta/);
  assert.match(top, /class="back-to-top"/);
  assert.doesNotMatch(top, /style="/);
  assert.match(home, /api-console/);
});
```

- [ ] **Step 2: Verify RED**

Run: `npm run test:ui`

Expected: FAIL for the missing shell classes and inline-styled back-to-top control.

- [ ] **Step 3: Implement the shell and home semantics**

In `Header.astro`, compute current state and render navigation links using this contract:

```astro
const isCurrent = (path: string) => path.includes('#')
  ? Astro.url.pathname === base
  : Astro.url.pathname.startsWith(path);

<header class="site-header">
  <a href={base} class="site-brand"><span class="brand-mark">VH</span><span>Vincent Hu</span></a>
  <nav class="site-nav" aria-label="Primary navigation">
    {SITE.nav.map((item) => <a href={item.path} aria-current={isCurrent(item.path) ? 'page' : undefined}>{item.name}</a>)}
  </nav>
  <div class="nav-utility"><span class="status-dot"></span>{SITE.status}</div>
</header>
```

Move all inline presentation out of `BackToTop.astro`, use `class="back-to-top"`, and keep its existing scroll/click script. Give the footer child elements `.site-footer__meta`, `.site-footer__build`, and `.site-footer__action` classes.

In `index.astro`, preserve the current two-column hero and content order. Rename the demo structure to `.api-console`, `.api-console__tabs`, `.api-console__body`, `.api-console__response`, and `.api-console__status`. Keep the existing request/response text and copy script.

In `global.css`, implement the shell as a white framed header on the paper grid, yellow current navigation item, compact mono utility label, editorial hero, and white API console with ink dividers. Buttons use `box-shadow: var(--shadow-sm)` and `transform: translate(2px, -2px)` on hover; active controls use `transform: translate(-1px, 1px); box-shadow: none`.

- [ ] **Step 4: Verify shell behavior**

Run: `npm run test:ui && npm run build`

Expected: PASS; the build generates `/index.html` without warnings caused by invalid Astro markup.

- [ ] **Step 5: Commit the shell**

```bash
git add tests/ui-contract.test.mjs src/components/layout/Header.astro src/components/layout/Footer.astro src/components/layout/BackToTop.astro src/pages/index.astro src/styles/global.css
git commit -m "feat: rebuild portfolio shell and hero"
```

### Task 3: Unify project and blog indexes

**Files:**
- Modify: `tests/ui-contract.test.mjs`
- Modify: `src/components/projects/ProjectList.astro`
- Modify: `src/components/projects/ProjectCard.astro`
- Modify: `src/components/blog/BlogList.astro`
- Modify: `src/components/blog/BlogItem.astro`
- Modify: `src/styles/global.css`

**Interfaces:**
- Consumes: `.ui-button`, shared tokens, and shell typography.
- Produces: `.collection-page`, `.collection-heading`, `.card-grid`, `.content-card`, `.content-card__head`, `.content-card__body`, `.content-card__tags`, and `.content-card__actions`.

- [ ] **Step 1: Add failing card assertions**

Append:

```js
test('project and blog cards share one semantic anatomy', async () => {
  const sources = await Promise.all([
    read('src/components/projects/ProjectCard.astro'),
    read('src/components/blog/BlogItem.astro'),
  ]);
  for (const source of sources) {
    for (const className of ['content-card', 'content-card__head', 'content-card__body', 'content-card__actions']) {
      assert.match(source, new RegExp(className));
    }
    assert.doesNotMatch(source, /style="/);
  }
});
```

- [ ] **Step 2: Verify RED**

Run: `npm run test:ui`

Expected: FAIL because the current cards use `.system-card` and inline font sizing.

- [ ] **Step 3: Convert both collections to shared card anatomy**

Use `article.content-card` for projects and `a.content-card` for posts. Each must contain:

```astro
<div class="content-card__head"><span class="content-card__kind">PROJ</span><span class="content-card__meta">...</span></div>
<div class="content-card__body">
  <h2 class="content-card__title">...</h2>
  <p class="content-card__description">...</p>
  <div class="content-card__tags">...</div>
</div>
<div class="content-card__actions">...</div>
```

Give both lists `.collection-page`, `.collection-kicker`, `.collection-heading`, and `.card-grid` wrappers. Preserve sorting, href calculation, metadata, GitHub links, live links, tags, and dates exactly.

Implement the cards with white panels, 2px ink frames, negative-left hard shadow, yellow kind label, restrained ice-blue hover fill on the action row, and three-to-one columns according to viewport width.

- [ ] **Step 4: Verify indexes**

Run: `npm run test:ui && npm run build`

Expected: PASS and both `/projects/index.html` and `/blog/index.html` are generated.

- [ ] **Step 5: Commit index pages**

```bash
git add tests/ui-contract.test.mjs src/components/projects/ProjectList.astro src/components/projects/ProjectCard.astro src/components/blog/BlogList.astro src/components/blog/BlogItem.astro src/styles/global.css
git commit -m "feat: unify project and blog collections"
```

### Task 4: Rebuild article and project detail presentation

**Files:**
- Modify: `tests/ui-contract.test.mjs`
- Modify: `src/layouts/BlogPostLayout.astro`
- Modify: `src/pages/projects/[...slug].astro`
- Modify: `src/styles/global.css`

**Interfaces:**
- Consumes: shared buttons, tokens, type scales, and shell.
- Produces: `.article-shell`, `.article-header`, `.article-meta`, `.article-body`, and `.project-links`.

- [ ] **Step 1: Add failing detail-page assertions**

Append:

```js
test('detail pages use article and project-link primitives without dark utilities', async () => {
  const [layout, project] = await Promise.all([
    read('src/layouts/BlogPostLayout.astro'),
    read('src/pages/projects/[...slug].astro'),
  ]);
  for (const className of ['article-shell', 'article-header', 'article-meta', 'article-body']) {
    assert.match(layout, new RegExp(className));
  }
  assert.match(project, /project-links/);
  assert.doesNotMatch(project, /dark:|rounded-full|bg-emerald/);
});
```

- [ ] **Step 2: Verify RED**

Run: `npm run test:ui`

Expected: FAIL for missing semantic classes and legacy dark/emerald utilities.

- [ ] **Step 3: Implement editorial detail layout**

Wrap detail content with:

```astro
<article class="article-shell">
  <a class="ui-button article-back" href="...">← Blog</a>
  <header class="article-header">
    <h1>{title}</h1>
    <div class="article-meta">...</div>
  </header>
  <div class="article-body prose-custom"><slot /></div>
</article>
```

In the project slug page, combine GitHub and live links inside one `<div class="project-links">` and style each as `.ui-button`; preserve external-link safety attributes and local-base URL resolution.

Define a 760px readable article measure; Lora body copy; mono metadata; ink horizontal rules; ice-blue link underline/hover; white blockquotes with hard shadow; white inline code; and ink code blocks. Ensure tables scroll horizontally and images use the shared frame.

- [ ] **Step 4: Verify detail generation**

Run: `npm run test:ui && npm run build`

Expected: PASS and all content collection entries render successfully.

- [ ] **Step 5: Commit detail pages**

```bash
git add tests/ui-contract.test.mjs src/layouts/BlogPostLayout.astro 'src/pages/projects/[...slug].astro' src/styles/global.css
git commit -m "feat: restyle article and project details"
```

### Task 5: Rebuild about and photo experiences

**Files:**
- Modify: `tests/ui-contract.test.mjs`
- Modify: `src/pages/about.astro`
- Modify: `src/pages/photos.astro`
- Modify: `src/styles/global.css`

**Interfaces:**
- Consumes: panel and button primitives.
- Produces: `.profile-panel`, `.profile-links`, `.photo-grid`, `.photo-tile`, `.lightbox`, `.lightbox__panel`, and `.lightbox__action`.

- [ ] **Step 1: Add failing page assertions**

Append:

```js
test('about and photos avoid inline visual styling', async () => {
  const [about, photos] = await Promise.all([
    read('src/pages/about.astro'), read('src/pages/photos.astro'),
  ]);
  assert.match(about, /profile-panel/);
  assert.match(about, /profile-links/);
  for (const className of ['photo-grid', 'lightbox', 'lightbox__panel', 'lightbox__action']) {
    assert.match(photos, new RegExp(className));
  }
  assert.doesNotMatch(about, /style="/);
  assert.doesNotMatch(photos, /style="/);
});
```

- [ ] **Step 2: Verify RED**

Run: `npm run test:ui`

Expected: FAIL because both pages currently rely on inline presentation.

- [ ] **Step 3: Implement semantic profile and gallery UI**

Keep all About copy and links unchanged. Wrap its copy in `.profile-panel` and social links in `.profile-links`; use a white editorial panel with a mono top label and ice/yellow actions.

Keep the photo discovery, sort order, lazy loading, open/close logic, overlay click, and Escape behavior unchanged. Replace inline styles with `.photo-grid`, `.photo-tile`, `.photo-tile__image`, `.lightbox`, `.lightbox.is-open`, `.lightbox__panel`, `.lightbox__image`, and `.lightbox__action`. Change the script to toggle `is-open` instead of writing `display` directly:

```js
const closeLightbox = () => overlay?.classList.remove('is-open');
const openLightbox = (src) => {
  if (!overlay || !overlayImage) return;
  overlayImage.setAttribute('src', src);
  overlay.classList.add('is-open');
};
```

Use responsive square tiles with the shared frame/shadow and a dark translucent overlay only behind the white framed lightbox panel.

- [ ] **Step 4: Verify static behavior**

Run: `npm run test:ui && npm run build`

Expected: PASS and `/about/index.html` plus `/photos/index.html` build successfully.

- [ ] **Step 5: Commit about and photos**

```bash
git add tests/ui-contract.test.mjs src/pages/about.astro src/pages/photos.astro src/styles/global.css
git commit -m "feat: rebuild profile and photo gallery UI"
```

### Task 6: Apply the shared system to interactive product pages

**Files:**
- Modify: `tests/ui-contract.test.mjs`
- Modify: `src/pages/chefmate.astro`
- Modify: `src/pages/chefmate-graphrag.astro`
- Modify: `src/pages/tripplan.astro`
- Modify: `src/styles/global.css`

**Interfaces:**
- Consumes: Task 1-5 primitives and aliases.
- Produces: `.product-shell`, `.product-hero`, `.product-panel`, `.product-chat`, `.product-prompts`, `.product-input`, `.product-send`, and `.product-metric` while retaining existing DOM ids consumed by scripts.

- [ ] **Step 1: Add failing system-page contract**

Append:

```js
test('interactive product pages expose shared product hooks and no dark variants', async () => {
  const paths = [
    'src/pages/chefmate.astro',
    'src/pages/chefmate-graphrag.astro',
    'src/pages/tripplan.astro',
  ];
  for (const path of paths) {
    const source = await read(path);
    assert.match(source, /product-shell/);
    assert.match(source, /product-hero/);
    assert.match(source, /product-panel/);
    assert.doesNotMatch(source, /dark:/);
  }
});
```

- [ ] **Step 2: Verify RED**

Run: `npm run test:ui`

Expected: FAIL because product hooks are absent and dark variants remain.

- [ ] **Step 3: Add semantic hooks without changing runtime contracts**

Add `.product-shell` to each outer application container, `.product-hero` to each hero, and `.product-panel` to chat, prompts, context, graph, strategy, and metrics surfaces. Add `.product-input` and `.product-send` to existing controls. Do not rename or remove any `id`, `data-query`, endpoint string, event listener, streaming parser, graph renderer, or dynamic-content function.

Remove `dark:*`, purple background, glass opacity, large rounded, and soft shadow utility classes from static markup. In dynamic HTML templates, replace `rounded-*`, `dark:*`, and purple/emerald surface utilities with `.product-message`, `.product-message--user`, `.product-message--agent`, and `.product-metric` class strings while preserving escaped user input and interpolated data.

In `global.css`, style product panels as white framed regions, message blocks as paper/soft-blue sections, prompt chips as compact bordered controls, active version tabs in yellow, and send buttons in ice blue. Keep status colors limited to small semantic dots or labels.

- [ ] **Step 4: Verify system sources and production build**

Run: `npm run test:ui && npm run build`

Expected: PASS; all three product routes build and tests confirm no dark variant remains.

- [ ] **Step 5: Commit product pages**

```bash
git add tests/ui-contract.test.mjs src/pages/chefmate.astro src/pages/chefmate-graphrag.astro src/pages/tripplan.astro src/styles/global.css
git commit -m "feat: unify interactive product page styling"
```

### Task 7: Perform full responsive and interaction verification

**Files:**
- Modify: `src/styles/global.css` only if verification exposes a defect.

**Interfaces:**
- Consumes: completed UI implementation.
- Produces: verified desktop/mobile frontend with no deployment changes.

- [ ] **Step 1: Run automated verification**

Run:

```bash
npm run test:ui
npm run build
git diff --check
git status --short
```

Expected: UI tests PASS; Astro build succeeds; diff check has no output. Existing unrelated working-tree changes, including `deploy.sh`, are preserved and are not staged or modified by this work.

- [ ] **Step 2: Start the local frontend**

Run: `npm run dev -- --host 127.0.0.1 --port 4325`

Expected: Astro reports the local URL `http://127.0.0.1:4325/` and remains running for browser inspection.

- [ ] **Step 3: Inspect desktop screenshots**

At 1440px width, capture and inspect:

- `/`
- `/projects`
- `/blog`
- one `/blog/<slug>` route
- `/about`
- `/photos`
- `/chefmate`
- `/chefmate-graphrag`
- `/tripplan`

Expected: all pages use paper/grid canvas, framed white surfaces, ink borders, hard shadows, Lora/mono hierarchy, yellow/ice accents, and no dark/purple/glass remnants. Existing layout and content order remain unchanged.

- [ ] **Step 4: Inspect mobile screenshots and interactions**

At 390px width, inspect `/`, `/projects`, `/blog`, one article, `/photos`, and one product page. Exercise keyboard navigation, photo open/Escape close, back-to-top, copy-contact, and navigation links.

Expected: no horizontal page overflow; columns collapse without reordering content; controls remain reachable; focus is visible; the lightbox and copy action behave as before.

- [ ] **Step 5: Fix only defects found by verification and rerun checks**

For each issue, first add a focused assertion to `tests/ui-contract.test.mjs` when the defect has a source-level contract, run it to observe failure, apply the smallest CSS or markup correction, then rerun `npm run test:ui && npm run build`.

- [ ] **Step 6: Commit verification fixes if any**

```bash
git add tests/ui-contract.test.mjs src/styles/global.css src/components src/layouts src/pages
git commit -m "fix: polish responsive Frontier UI"
```

If Step 5 required no source changes, skip this commit.
