# RouteMaster V2: Frontend Audit & Upgrade Roadmap

## 1. Executive Summary
The frontend requires significant updates to align with the Phase 2-8 backend logic. Current API consumers in `src/api/` are pointing to legacy search endpoints and expecting redundant data structures.

---

## 2. API Integration Audit (`src/api/`)

| File | Status | Missing Gaps / Required Upgrades | Phase |
| :--- | :--- | :--- | :--- |
| `railway.ts` | OUT OF SYNC| **Critical**: Update `searchRoutes` to call `/api/v2/search/unified`. Update response interface to match `JourneyInfoResponse[]`. | Phase 1 |
| `booking.ts` | PARTIAL | Add support for `PassengerDetailsSchema` matching the backend. Integrate with Razorpay v1. | Phase 4 |
| `chatbot.ts` | ACTIVE | Ensure context from search results is passed to the chatbot for "In-context" assistance. | Phase 7 |

---

## 3. Component & Page Audit (`src/pages/`)

| Page | Status | Missing Gaps / Required Upgrades | Phase |
| :--- | :--- | :--- | :--- |
| `Index.tsx` | ACTIVE | Integrate "Unified Search" UI with filters for Comfort/Speed. | Phase 1 |
| `Dashboard.tsx`| ACTIVE | Implement live PNR tracking updates via WebSockets. | Phase 5 |
| `Ticket.tsx` | SCAFFOLD | Complete the E-Ticket generation with QR code and fare breakdown. | Phase 4 |
| `mini-app/` | PARTIAL | Verify RapidAPI integration for third-party mini-apps (Hotel/Taxi). | Phase 3 |

---

## 4. UI/UX Gaps

1. **Skeleton Loaders**: Missing while RAPTOR engine computes routes.
2. **Error Boundaries**: Need better handling for "No trains available" vs "Service Down".
3. **PWA Support**: Offline mode for saved tickets is not fully implemented.

---
