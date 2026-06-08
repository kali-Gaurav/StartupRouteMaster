# 🚀 Real-System Pipeline: Payment & Booking Priority Tasks (50 Tasks)

This document outlines the top 50 priority tasks to make the manual payment (Direct UPI) and manual booking (Agent-assisted) system production-ready.

---

## 💳 Phase 1: Direct UPI Payment Infrastructure (Tasks 1-10)
*Goal: Ensure users can pay flawlessly via QR and Mobile Deep Links.*

1.  **Correct VPA Merchant Rotation**: Ensure rotation between `anthonynagar1122-1@oksbi` and `8529841981@ptsbi`.
2.  **Mobile App Deep Linking**: Implement `upi://pay` deep links that auto-open GPay, PhonePe, or Paytm on mobile devices.
3.  **Dynamic Amount Locking**: Ensure the `am` parameter in UPI URI is non-editable to prevent users from paying less than required.
4.  **Transaction Note Serialization**: Format `tn` as `RM_<BookingID>` for easy manual searching in bank apps.
5.  **React QR Code Level-H**: Use high-error correction for QR codes to ensure they scan even on low-quality screens.
6.  **"Copy UPI ID" UI**: Add a one-tap copy button for users whose QR scanners aren't working.
7.  **Payment Timeout Countdown**: Implement a 15-minute countdown timer on the payment screen.
8.  **Automatic UTR Input Trigger**: Show the UTR submission field only after the user clicks "I have paid".
9.  **UTR Length & Format Validation**: Client-side and server-side validation for exactly 12 digits.
10. **Duplicate UTR Prevention**: Backend check to ensure a UTR hasn't been used for another booking.

---

## 🛠️ Phase 2: Manual Verification & Admin Dashboard (Tasks 11-20)
*Goal: Provide the admin (you) with tools to verify payments quickly.*

11. **Admin UTR Verification Panel**: A dedicated view in the admin dashboard to see all `UTR_SUBMITTED` bookings.
12. **Bank SMS Webhook (Optional but Recommended)**: Setup a listener for bank SMS (via a helper app) to auto-verify UTRs.
13. **Manual "Mark as Paid" Action**: One-click button for admin to change state from `UTR_SUBMITTED` to `VERIFIED`.
14. **Unmatched Funds Ledger**: A table for UTRs submitted by users that don't match any incoming bank record yet.
15. **Booking Detail Tooltip**: Show journey details (source, dest, date, fare) in the admin verification list.
16. **User Contact Quick-Link**: Show user phone/email next to UTR for quick resolution if payment is missing.
17. **Audit Log for Status Changes**: Record which admin verified which UTR and at what time.
18. **CSV Statement Importer**: Tool to upload bank CSV statements to bulk-verify pending UTRs.
19. **Fraudulent UTR Flagging**: Mark specific UTRs as "Fake" and block the associated user.
20. **Admin Notification (Telegram)**: Bot notification to the admin whenever a new UTR is submitted.

---

## 🚄 Phase 3: Manual Booking (Agent-Assisted Flow) (Tasks 21-30)
*Goal: Smooth transition from "Paid" to "Booked" via manual agent action.*

21. **"Initiate Booking" State**: Once verified, booking status moves to `BOOKING_INITIATED`, notifying the user.
22. **Passenger Data Export**: Button for admin to copy all passenger details in a format easy to paste into IRCTC.
23. **IRCTC Login Helper**: Link to open IRCTC with pre-filled search parameters (if possible).
24. **Manual PNR Entry**: Admin field to enter the 10-digit PNR once the manual booking is successful on IRCTC.
25. **"Booking Successful" Transition**: Moving state to `COMPLETED` once PNR is entered.
26. **Ticket PDF Uploader**: Admin tool to upload the E-ticket PDF for the user to download.
27. **Tatkal Queue Management**: Sort `VERIFIED` bookings by journey time to prioritize 10:00/11:00 AM bookings.
28. **Manual Seat/Coach Update**: Allow admin to specify exact Coach and Seat numbers in the system.
29. **Booking Failure Handling**: Admin option to mark as `FAILED` (e.g., Sold Out) and trigger refund flow.
30. **WhatsApp Ticket Dispatch**: Integration to send the PNR/PDF via WhatsApp to the user automatically.

---

## 🔔 Phase 4: User Notifications & Status Tracking (Tasks 31-40)
*Goal: Keep the user informed so they don't call support.*

31. **Real-time Status Polling**: Frontend hook to poll for status changes from `UTR_SUBMITTED` -> `VERIFIED`.
32. **In-App "Payment Verified" Confetti**: Visual celebration once the admin verifies the payment.
33. **"Agent Working" Progress Bar**: Show a progress indicator when the admin is manually booking on IRCTC.
34. **PNR Status Widget**: Once PNR is entered, show a live PNR status check inside the app.
35. **Email Confirmation**: Send a branded email once the booking is confirmed.
36. **Push Notifications**: (FCM/OneSignal) for status updates (Payment Received, Ticket Booked).
37. **Payment Receipt Generation**: Generate a simple PDF receipt for the payment made to the UPI IDs.
38. **"Report Issue" Button**: Direct link to support for a specific booking.
39. **FAQ on Manual Payments**: In-app guide explaining how UTR verification works and how long it takes.
40. **Booking History View**: Comprehensive list of all past bookings with PNRs and payment status.

---

## 🛡️ Phase 5: Reliability, Security & Refunds (Tasks 41-50)
*Goal: Ensure the system is robust and handles edge cases.*

41. **Escrow State Machine Guards**: Prevent status jumping (e.g., can't go to `VERIFIED` without a UTR).
42. **Amount Discrepancy Alert**: Notify admin if the user submitted a UTR for ₹49 but the journey cost ₹499.
43. **Refund VPA Collection**: If a booking fails, prompt the user to provide their VPA for a refund.
44. **Refund Processing Dashboard**: Interface for admin to track and process pending refunds.
45. **Database Transaction Integrity**: Use SQL transactions for status updates to prevent race conditions.
46. **IP-based UTR Rate Limiting**: Prevent bots from spamming the UTR submission endpoint.
47. **Admin 2FA**: Ensure the admin panel is secured with more than just a token (e.g., TOTP).
48. **Daily Revenue Report**: Automated summary of total payments received vs. bookings completed.
49. **Database Backup (Automated)**: Daily backups of the `bookings` and `bank_transactions` tables.
50. **Health Check Endpoint**: Ensure the payment and booking APIs are always reachable.
