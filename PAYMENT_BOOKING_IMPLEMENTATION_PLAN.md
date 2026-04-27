# 💰 RouteMaster: Unified Financial Ledger & Parity Plan

This document tracks the final implementation of "Genius-Level" financial features across Web, Telegram, and Admin subsystems.

## 1. 🏗 Feature Parity Matrix (The Target)

| Feature | Backend Service | Web UI | Telegram Bot | Admin Portal |
| :--- | :--- | :--- | :--- | :--- |
| **Unified Ledger** | ✅ LedgerService | ⚠️ PENDING | ⚠️ PENDING | ✅ nexus_sagas |
| **Refund Tracking** | ✅ AutoRefund | ⚠️ PENDING | ⚠️ PENDING | ⚠️ PENDING |
| **Live P&L Tracking**| ✅ ProfitEngine | ❌ NONE | ❌ NONE | ✅ DailyRecon |
| **Invoice Engine** | ✅ TaxEngine | ⚠️ PENDING | ⚠️ PENDING | ✅ GSTR-1 |

---

## 2. 🧠 Patent-Level Algorithm: "The Sovereign Ledger"
*   **Logic**: Every single byte of financial data (Payment ID, Razorpay Sig, Refund Ref) is cryptographically hashed and linked to a **Nexus Saga ID**.
*   **Performance**: Uses a Denormalized "Financial Snapshot" table for sub-50ms history lookups.

---

## 3. 🛠 Targeted Execution List

### A. The Unified API (`/api/v2/ledger`)
*   Create a high-performance aggregator for Payments + Refunds + Karma.

### B. The Web "Financial Hub"
*   Implementation of `/dashboard/payments` with live status bars and "Request Refund" buttons.

### C. The Telegram "/transactions" Wizard
*   A stateful command to view history and download PDF invoices via bot.

### D. Admin "Dispute Resolver"
*   Implementation of a manual override for stuck Razorpay payments.
