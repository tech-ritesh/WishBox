# WishBox — UI/UX Recommendations

Comparing the Celebration Box frontend (functional but heavy, monolithic) and what WishBox implements / recommends.

## What WishBox already improves
1. **Modular pages & components** — replaced the 228 KB `AdminDashboard.jsx` monolith with small, focused files (`pages/admin/*`, `components/*`).
2. **Consistent design system** — Tailwind tokens + reusable `.btn`, `.card`, `.input`, `.badge` classes and a single `brand` color scale. No ad-hoc inline styling drift.
3. **Clear visual hierarchy** — hero, occasion chips, top-rated grid on Home; predictable card layout everywhere.
4. **Loading & empty states** — shared `<Spinner/>`, explicit empty-cart / no-orders / no-reviews messaging.
5. **Order tracking timeline** — a real visual stepper (pending → delivered) instead of a bare status string.
6. **Resilient auth** — silent token refresh via an Axios interceptor; users aren't kicked out every 30 min.
7. **Accessible forms** — labels, `required`, typed inputs, inline error text.

## Recommended next UX iterations (documented for a later pass)
| Area | Recommendation |
|---|---|
| Search | Debounced live search + autocomplete; persist filters in URL (partly done via query params) |
| Product media | Image gallery/zoom, multiple `ProductImage`s already modeled |
| Cart | Optimistic quantity updates; "save for later"; mini-cart drawer |
| Checkout | Multi-step wizard with progress; address autofill via PIN-code lookup |
| Personalization | Live hamper preview (3D/illustrated box), card-font picker |
| Accessibility | Full keyboard nav audit, focus traps in modals, ARIA roles, color-contrast AA, `prefers-reduced-motion` |
| Feedback | Global toast/snackbar system (replace inline messages); skeleton loaders instead of spinners |
| Mobile | Bottom nav bar, sticky add-to-cart, larger tap targets |
| Trust | Verified-purchase badges (done), delivery ETA, return policy surfacing |
| Admin | Inline edit, bulk actions, CSV export, charts library for richer analytics |
| i18n / currency | Locale-aware formatting hook (started in `utils/format.js`) |
| Dark mode | Tailwind `dark:` variants + theme toggle |

## Performance UX
- Code-split admin bundle (`React.lazy` on `/admin/*`) so customers never download admin code.
- Image lazy-loading + responsive `srcset`.
- Cache product lists with a data layer (React Query/SWR) to avoid refetch flicker.

## Information architecture
- Primary nav: Shop · Build a Hamper · Gift Finder · Cart · Account.
- Occasion-first browsing (chips on Home, category tree in Shop) matches how gift shoppers actually think ("I need something for an anniversary"), not product-type-first.
