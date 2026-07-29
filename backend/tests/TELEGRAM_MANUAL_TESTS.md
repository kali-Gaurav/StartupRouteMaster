# Feature #4: Telegram Bot - Manual Testing Guide

## Test Environment Setup

### Prerequisites
1. Telegram Bot Token (create at @BotFather)
2. Test Telegram account
3. Environment variables:
   ```bash
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_BOT_NAME=@your_bot_name
   ```

### Database
- Ensure `telegram_conversation_states` and `telegram_booking_links` tables exist
- Run migrations: `alembic upgrade head`

---

## Test Cases

### Group 1: User Linking Flow

#### TC1.1: Create Auth Link
**Steps:**
1. User sends `/start` in Telegram
2. System receives webhook, responds with welcome message
3. User clicks "Link Account" button (or sends `/link`)
4. POST to `/api/v1/telegram/auth-link` with telegram_user_id=123456789

**Expected Results:**
- ✅ Response includes `link_token` (UUID format)
- ✅ Response includes `auth_url` (https://app.routemaster.com/telegram/link?token=...)
- ✅ Response includes `expires_in_seconds` = 3600
- ✅ TelegramConversationState created in DB
- ✅ current_state = "AWAITING_AUTHENTICATION"

**Test Command:**
```bash
curl -X POST http://localhost:8000/api/v1/telegram/auth-link \
  -H "Content-Type: application/json" \
  -d '{"telegram_user_id":"123456789","telegram_username":"@testuser"}'
```

#### TC1.2: Confirm Link (Valid Token)
**Steps:**
1. User clicks auth_url from TC1.1
2. User logged into RouteMaster web app
3. Frontend calls `/api/v1/telegram/link-confirm` with link_token and user_id

**Expected Results:**
- ✅ Response: `{"success": true, "message": "✅ Telegram account linked..."}`
- ✅ User.telegram_id set to "123456789"
- ✅ TelegramConversationState.user_id set to user_id
- ✅ TelegramConversationState.current_state reset to "IDLE"

**Test Command:**
```bash
curl -X POST http://localhost:8000/api/v1/telegram/link-confirm \
  -H "Content-Type: application/json" \
  -d '{"link_token":"00000000-0000-0000-0000-000000000000","user_id":"user123"}'
```

#### TC1.3: Confirm Link (Expired Token)
**Steps:**
1. Create auth link (TC1.1)
2. Wait >1 hour (or manipulate DB: set telegram_conversation_states.context auth_link_expiry to past time)
3. Try to confirm link with expired token

**Expected Results:**
- ✅ Response: `{"success": false, "message": "Link token has expired"}`
- ✅ Account NOT linked
- ✅ User can create new auth link

#### TC1.4: Confirm Link (Invalid Token)
**Steps:**
1. Call `/api/v1/telegram/link-confirm` with non-existent link_token

**Expected Results:**
- ✅ Response: `{"success": false, "message": "Invalid or expired link token"}`

---

### Group 2: Conversation State Management

#### TC2.1: Create Conversation State
**Steps:**
1. Send message to bot with unlinked telegram_user_id
2. TelegramConversationState should auto-create

**Expected Results:**
- ✅ TelegramConversationState.current_state = "IDLE"
- ✅ TelegramConversationState.context = {}
- ✅ TelegramConversationState.expires_at set to now + 15 minutes

#### TC2.2: Update Conversation State
**Steps:**
1. User in IDLE state
2. User clicks "Book" button on train search
3. State updates to AWAITING_CLASS

**Expected Results:**
- ✅ current_state = "AWAITING_CLASS"
- ✅ context contains {"selected_train": "12345"}
- ✅ last_message_at updated to current time
- ✅ expires_at reset to now + 15 minutes

#### TC2.3: Conversation Timeout
**Steps:**
1. Create conversation state
2. Wait 15+ minutes without interaction
3. Bot tries to continue conversation

**Expected Results:**
- ✅ Expired state cleaned up by cron job (cleanup_expired_conversations)
- ✅ Next message creates new conversation state
- ✅ User sees "Session expired, starting fresh"

---

### Group 3: Route Search Flow

#### TC3.1: Parse Two-Station Query
**Steps:**
1. User sends "Delhi Mumbai"
2. Bot receives message via webhook

**Expected Results:**
- ✅ Parsed as: from=NDLS, to=BCT, date=today
- ✅ Bot searches trains
- ✅ Results show top 5 trains with action buttons

**Test in Telegram:**
```
@routemasterbot
Delhi Mumbai
```

#### TC3.2: Parse With Date
**Steps:**
1. User sends "NDLS BCT 15 June"

**Expected Results:**
- ✅ Parsed as: from=NDLS, to=BCT, date=2026-06-15
- ✅ Trains listed for that date

#### TC3.3: Fuzzy Station Matching
**Steps:**
1. User sends "Banglore Chennai"

**Expected Results:**
- ✅ "Banglore" fuzzy matches to SBC (Bengaluru)
- ✅ Search executes successfully

#### TC3.4: Invalid Query
**Steps:**
1. User sends "xyz abc"

**Expected Results:**
- ✅ Bot responds: "🤔 I couldn't understand that..."
- ✅ Suggests format examples
- ✅ Offers /help command

---

### Group 4: Callback Query Handling (Button Clicks)

#### TC4.1: Book Button Click
**Steps:**
1. User sees train search results
2. User clicks "✅ Book" button on a train
3. Webhook receives callback_query with data="book_12345"

**Expected Results:**
- ✅ Bot prompts for class selection
- ✅ Message shows class options with emojis
- ✅ State updated to AWAITING_CLASS
- ✅ context["selected_train"] = "12345"

#### TC4.2: Class Selection
**Steps:**
1. After TC4.1, user clicks "AC 2A" button
2. Callback_query received with data="class_2A"

**Expected Results:**
- ✅ Bot prompts for berth preference
- ✅ Shows: Upper, Middle, Lower, Any
- ✅ State updated to AWAITING_BERTH
- ✅ context["passenger_class"] = "2A"

#### TC4.3: Berth Selection
**Steps:**
1. After TC4.2, user clicks "Middle" button
2. Callback_query received with data="berth_Middle"

**Expected Results:**
- ✅ Bot asks for passenger info
- ✅ Prompts format: "name Age Gender"
- ✅ State updated to AWAITING_PASSENGER_INFO
- ✅ context["berth_preference"] = "Middle"

#### TC4.4: Cancel Booking
**Steps:**
1. In any booking state, user clicks "❌ Cancel"
2. Callback_query received with data="cancel"

**Expected Results:**
- ✅ State reset to IDLE
- ✅ context cleared
- ✅ Bot asks: "Type a new search to start over"

---

### Group 5: Booking Completion

#### TC5.1: Complete Booking (Valid Link)
**Steps:**
1. Create TelegramBookingLink via backend (or simulate)
2. POST to `/api/v1/telegram/book` with:
   - link_token (from booking link)
   - passenger_name: "Raj Kumar"
   - passenger_age: 28
   - passenger_gender: "M"
   - berth_preference: "Middle"

**Expected Results:**
- ✅ Response: `{"success": true, "booking_id": "...", "pnr": "..."}`
- ✅ Booking created in database
- ✅ PassengerDetails created with name, age, gender
- ✅ TelegramBookingLink.is_used = True
- ✅ TelegramBookingLink.booking_id set

**Test Command:**
```bash
curl -X POST http://localhost:8000/api/v1/telegram/book \
  -H "Content-Type: application/json" \
  -d '{
    "link_token":"00000000-0000-0000-0000-000000000000",
    "passenger_name":"Raj Kumar",
    "passenger_age":28,
    "passenger_gender":"M",
    "berth_preference":"Middle"
  }'
```

#### TC5.2: Complete Booking (Used Link)
**Steps:**
1. Create booking with TC5.1
2. Try to complete booking again with same link_token

**Expected Results:**
- ✅ Response: `{"success": false, "error": "This booking link has already been used"}`

#### TC5.3: Complete Booking (Expired Link)
**Steps:**
1. Create TelegramBookingLink with expires_at in past
2. Try to complete booking

**Expected Results:**
- ✅ Response: `{"success": false, "error": "Booking link has expired"}`

---

### Group 6: Notification Integration

#### TC6.1: Booking Confirmation via Telegram
**Prerequisites:**
- User account linked to Telegram (completed TC1.2)
- User has telegram_notifications_enabled = True

**Steps:**
1. User completes booking via app or Telegram
2. NotificationService.send_notification(user_id, "booking_confirmed", channels=["telegram"], data={...})

**Expected Results:**
- ✅ Telegram bot sends message:
  ```
  ✅ RouteMaster
  
  Booking confirmed! PNR: 1234567890
  Train: 12345 Mumbai Express
  Date: 15-Jul-2026
  [View ticket button]
  ```
- ✅ Message ID stored in NotificationResult
- ✅ TelegramMessage record created (if enabled)

#### TC6.2: Payment Confirmation via Telegram
**Steps:**
1. After booking, user pays
2. Razorpay webhook triggers payment_received event
3. NotificationService sends telegram notification

**Expected Results:**
- ✅ Message: "💳 RouteMaster - Payment of ₹2500 received for PNR 1234567890"

#### TC6.3: Telegram Notifications Disabled
**Steps:**
1. User disables telegram notifications in preferences
2. Trigger booking_confirmed event
3. NotificationService.send_notification(..., channels=["telegram"])

**Expected Results:**
- ✅ Result shows: `{"channel": "telegram", "success": false, "error": "Telegram disabled"}`
- ✅ No message sent to Telegram

---

### Group 7: Error Handling

#### TC7.1: Missing Bot Token
**Setup:**
1. Unset TELEGRAM_BOT_TOKEN env var

**Steps:**
1. Try to send notification via Telegram
2. Try auth link creation

**Expected Results:**
- ✅ Falls back to logging
- ✅ Returns success=true with stub message_id
- ✅ No error thrown
- ✅ Logs show: "[STUB] To: ..."

#### TC7.2: User Not Linked
**Steps:**
1. Try to book without completing link (TC1)
2. POST to `/api/v1/telegram/book` without user_id link

**Expected Results:**
- ✅ Response: `{"success": false, "error": "User account not linked to Telegram"}`

#### TC7.3: Missing Passenger Info
**Steps:**
1. In AWAITING_PASSENGER_INFO state
2. User sends invalid format (not "name age gender")

**Expected Results:**
- ✅ Bot asks again with format example
- ✅ State remains AWAITING_PASSENGER_INFO
- ✅ Timeout restarts after 15 minutes

---

## Performance Tests

#### PT1: Conversation State Cleanup
**Setup:**
1. Create 100 TelegramConversationState records
2. Set expires_at to past for 50 of them

**Steps:**
1. Run cleanup_expired_conversations()

**Expected Results:**
- ✅ Completes in <1 second
- ✅ 50 records deleted
- ✅ 50 records remain
- ✅ Logs show: "Cleaned up 50 expired conversation states"

#### PT2: Bulk Notifications
**Setup:**
- 100 linked Telegram users
- Feature flag: send booking confirmations to all

**Steps:**
1. Send 100 notifications via Telegram channel

**Expected Results:**
- ✅ All sent in <10 seconds
- ✅ No message rate limiting errors
- ✅ All delivery tracked in NotificationResult

---

## Regression Tests

After each deployment:

1. **Smoke Test**: `/info` endpoint returns bot config
2. **Auth Flow**: Complete user link-confirm cycle
3. **Route Search**: "Delhi Mumbai" returns trains
4. **Booking**: Create booking via `/book` endpoint
5. **Notification**: Send test notification to linked user

---

## Test Matrix

| Test ID | Category | Status | Notes |
|---------|----------|--------|-------|
| TC1.1   | User Link | ⚪ | Auto-test ready |
| TC1.2   | User Link | ⚪ | Manual Telegram required |
| TC1.3   | User Link | ⚪ | Manual (wait 1h) |
| TC1.4   | User Link | ⚪ | Auto-test ready |
| TC2.1   | State | ⚪ | Auto-test ready |
| TC2.2   | State | ⚪ | Auto-test ready |
| TC2.3   | State | ⚪ | Manual (wait 15m) |
| TC3.1   | Route | ⚪ | Manual Telegram |
| TC3.2   | Route | ⚪ | Manual Telegram |
| TC3.3   | Route | ⚪ | Manual Telegram |
| TC3.4   | Route | ⚪ | Manual Telegram |
| TC4.1   | Callback | ⚪ | Manual Telegram |
| TC4.2   | Callback | ⚪ | Manual Telegram |
| TC4.3   | Callback | ⚪ | Manual Telegram |
| TC4.4   | Callback | ⚪ | Manual Telegram |
| TC5.1   | Booking | ⚪ | Auto-test ready |
| TC5.2   | Booking | ⚪ | Auto-test ready |
| TC5.3   | Booking | ⚪ | Auto-test ready |
| TC6.1   | Notification | ⚪ | Manual Telegram |
| TC6.2   | Notification | ⚪ | Manual Telegram |
| TC6.3   | Notification | ⚪ | Manual Telegram |
| TC7.1   | Error | ⚪ | Auto-test ready |
| TC7.2   | Error | ⚪ | Auto-test ready |
| TC7.3   | Error | ⚪ | Auto-test ready |
| PT1     | Performance | ⚪ | Auto-test ready |
| PT2     | Performance | ⚪ | Manual setup |

**Legend:** ⚪ Not Tested | 🟡 In Progress | 🟢 Passed | 🔴 Failed

