# 🚀 RouteMaster V2: Compliant Growth & Agent Portal Plan

This plan shifts the focus from web-scraping to Route Intelligence, Autofill UX, and Human-Assisted Booking (Agent Portal).

---

## 🔒 Phase 1: Route Unlocking & Payment (Tasks 1-15)
1. **Route Masking Logic**: Show partial route data (e.g., "3 Trains available") but hide Train Nos/Times until ₹49 is paid.
2. **"Unlock Now" UI**: Replace "Book Now" with "Unlock Route Details" for ₹49.
3. **Escrow for Unlock**: Payment verified via UPI -> Instantly unlock JSON details in the DB.
4. **Deep-Link Generator**: Create direct links to `irctc.co.in` with pre-filled search parameters (Station Code, Date).
5. **Passenger Data Export**: Button to "Copy All Passenger Details" in a format easy to paste into IRCTC.
6. **Autofill Helper (Client-Side)**: JS snippet/extension that users can use to fill the IRCTC form with one click.
7. **Unlock Expiry**: Unlocked routes stay visible for 24 hours.
8. **Revenue Dashboard**: Track total "Unlocks" vs "Agent Requests."
9. **Instant WhatsApp Unlock**: Send the unlocked route details + IRCTC link to user's WhatsApp automatically.
10. **Tax Invoice for ₹49**: Professional digital receipt for the service fee.

## 🤵 Phase 2: Agent Booking Portal (Tasks 16-35)
11. **Agent Role Implementation**: New user type `AGENT` in the database.
12. **"Request Agent" Button**: Option for users to pay an extra fee for a human guide to book for them.
13. **Agent Dashboard**: Interface for agents to see pending booking requests and passenger details.
14. **Document Secure Vault**: Securely share ID proofs (if needed) between User and Agent.
15. **Agent Fulfillment Flow**: Agent uploads the final ticket PDF -> User is notified.
16. **Commission Logic**: Split the service fee between the platform and the Agent.
17. **Agent Rating System**: Users rate the speed and helpfulness of the Agent.
18. **Chat Bridge**: Direct real-time chat between the User and the assigned Agent.
19. **Bulk Agent Management**: Admin tools to onboard and verify real-world agents.
20. **Ticket Verification**: Automated PNR check once the Agent uploads the ticket.

## 🛠️ Phase 3: System Cleanup & Compliance (Tasks 36-50)
21. **Scraping Removal**: Delete all Playwright code that logs into IRCTC autonomously.
22. **API Stabilization**: Ensure official train data APIs are used for search results.
23. **Terms of Service Update**: Clearly state we are an "Intelligence & Assistance" platform, not a booking agent.
24. **Autofill Security**: Ensure no passenger data is stored in the browser longer than needed.
25. **Manual Ticket Upload UI**: Allow users to upload their own tickets for trip management.
