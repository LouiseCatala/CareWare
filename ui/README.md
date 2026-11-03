# CareWare React desktop interface

This interface restores the supplied template's black layout, Poppins typography, top navigation, gradient hero and original artwork, with CareWare labels and actions. The original component is preserved in `components/ui/saa-s-template.reference.txt`. The former CRM screenshot is now an interactive Checks dashboard with the same dark sidebar, metric cards, chart panels and lower lists. Counts, result distribution and health history come from recorded visits; empty states are shown before scanning.

## Run

The built interface is included in `dist`. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Use `python desktop.py --preview` for an isolated temporary database. The Windows desktop requires the Microsoft Edge WebView2 runtime. `python main.py --legacy` opens the previous Tk interface if needed.

## Develop

Use Node 22.12+ or 24, then run in this folder:

```powershell
npm ci
npm run dev
npm run build
```

Browser development mode shows the design; local diagnostics require the desktop Python bridge. Rebuild before restarting the desktop app after editing React code.

## Structure

- `components/ui/saa-s-template.tsx`: supplied template and responsive navigation.
- `components/ui/checks-dashboard.tsx`: live dashboard replacing the CRM screenshot.
- `app.tsx`: consent, scans, cleanup, inspection, reports, history, comparisons, reminders, and settings.
- `styles.css`: Tailwind entry point and bundled Poppins fonts.
- `components.json`: shadcn configuration; `@/components/ui` resolves to this project's `components/ui` directory.
- `lib/utils.ts`: shadcn-compatible `cn` helper.

The `components/ui` folder keeps reusable UI separate from app behavior and allows shadcn-generated imports to resolve consistently. React, TypeScript and Tailwind are already configured. No context provider package is needed; navigation uses React's built-in context. To add a shadcn primitive later, run `npx shadcn@latest add <component>` here.

Setup references: [Tailwind with Vite](https://tailwindcss.com/docs/installation/using-vite), [shadcn Vite setup](https://ui.shadcn.com/docs/installation/vite), [pywebview bridge](https://pywebview.flowrl.com/guide/interdomain.html).

Fonts and the two supplied images are bundled locally. The desktop loads only local assets and uses the existing SQLite database and diagnostic modules. It does not upload customer records. The interface intentionally retains the template's black theme; the report accent remains configurable independently.
