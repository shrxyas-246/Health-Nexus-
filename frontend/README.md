# HealthNexus — Frontend

React + Vite + Tailwind implementation of the HealthNexus patient profile.

## Run it

```bash
npm install
npm run dev
```

Then open http://localhost:5173

## Build

```bash
npm run build
npm run preview
```

## Structure

```
frontend/
├─ index.html
├─ tailwind.config.js
├─ postcss.config.js
├─ vite.config.js
└─ src/
   ├─ main.jsx            # React entry
   ├─ App.jsx             # Page composition + scroll spy + animations
   ├─ index.css           # Design system (crimson theme) + Tailwind layers
   ├─ context/
   │   └─ UIContext.jsx   # Global toast + modal
   ├─ components/
   │   ├─ TopNav.jsx
   │   ├─ ChapterBar.jsx
   │   ├─ Footer.jsx
   │   ├─ Modal.jsx
   │   └─ Toast.jsx
   └─ sections/
       ├─ Profile.jsx
       ├─ Snapshot.jsx
       ├─ Prescriptions.jsx
       ├─ History.jsx
       ├─ Billing.jsx
       ├─ Insurance.jsx
       ├─ Doctors.jsx
       ├─ Pharmacy.jsx
       ├─ Insights.jsx
       └─ Plus.jsx
```

## Notes on what changed vs. the single-file HTML

The **look, layout and every feature are preserved 1:1**. What changed under the hood:

- HTML split into React components by section for easy editing.
- Global `toast()` / `modal()` moved into `UIContext` — call `useUI()` in any component.
- Scroll-spy, chapter sub-bar rendering, reveal-on-scroll, chart draw-in animation, timeline rail fill, and PDF/text download all rewritten as React hooks (`useEffect` + `IntersectionObserver`) — same behavior, no globals.
- Tailwind is wired in and ready — the crimson design tokens are exposed as `brand`, `brand-dark`, `brand-tint`, `ink`, `navy`. Use `className="text-brand"` etc. for any new UI you add.
- Original design-system CSS is kept in `src/index.css` so nothing visual drifts.
