# Features #2-5 Implementation Design & Architecture

**Created:** July 29, 2026  
**Status:** Design Phase  
**Target:** Complete design & architecture for next 4 critical features  
**Total Implementation Time:** 20-25 hours

---

## QUICK START CHECKLIST

### Before Building Each Feature:
- [ ] Read the complete design (Parts 1-4)
- [ ] Review database schema changes
- [ ] Review API contracts
- [ ] Identify dependencies on other features
- [ ] Set up feature branch
- [ ] Create tracking checklist

---

## FEATURE #2: USER DASHBOARD & BOOKING HISTORY
**Timeline:** 4-6 hours  
**Priority:** High (user retention driver)  
**Depends On:** Feature #1 (Booking & Payment)

### 2.1 PRODUCT DESIGN

#### User Journey
```
User Login → Dashboard
  ├─ Upcoming Journeys (bookings in future)
  │   └─ Click journey → View details, cancel, get refund
  ├─ Past Journeys (bookings in past)
  │   └─ Click journey → View receipt, rate, download ticket
  ├─ Saved Routes (frequently searched)
  │   └─ Click route → Jump to search results
  ├─ Settings
  │   └─ Edit profile, preferences, payment methods
  └─ Profile (avatar, name, email, phone)
```

#### Key Screens

**Screen 1: Dashboard Overview**
```
┌─────────────────────────────────────────┐
│  👤 Welcome, John Doe                   │
│  ⭐ Loyalty Points: 245                 │
│  💳 Preferred Payment: UPI              │
├─────────────────────────────────────────┤
│                                         │
│  📅 UPCOMING JOURNEYS (2)               │
│  ┌─────────────────────────────────────┐│
│  │ 🚂 Rajdhani Express (12951)         ││
│  │ New Delhi (NDLS) → Mumbai (BCT)     ││
│  │ Tomorrow, Jun 15 @ 6:00 AM          ││
│  │ Status: ✅ Confirmed | PNR: 7482... ││
│  │ [View Ticket]  [Cancel] [Rate]      ││
│  └─────────────────────────────────────┘│
│                                         │
│  🕐 PAST JOURNEYS (8)                  │
│  [June 2026] [May 2026] [April 2026]   │
│  ┌─────────────────────────────────────┐│
│  │ ✅ Golden Temple Express (25052)    ││
│  │ Completed on Jun 8                  ││
│  │ Rating: ⭐⭐⭐⭐⭐                   ││
│  │ [Receipt] [Download] [Review]       ││
│  └─────────────────────────────────────┘│
│                                         │
│  ❤️ SAVED ROUTES (5)                   │
│  [Delhi-Mumbai] [Delhi-Jaipur] ...     │
│                                         │
└─────────────────────────────────────────┘
```

**Screen 2: Journey Detail Modal**
```
┌─────────────────────────────────────────┐
│ BOOKING DETAILS                    [X]  │
├─────────────────────────────────────────┤
│                                         │
│ 🚂 Rajdhani Express (12951)             │
│ New Delhi (NDLS) → Mumbai (BCT)         │
│                                         │
│ Date: June 15, 2026                     │
│ Departure: 6:00 AM                      │
│ Arrival: 4:30 PM                        │
│ Duration: 10h 30m                       │
│                                         │
│ ─────────────────────────────────────── │
│ PASSENGER DETAILS                       │
│ Name: John Doe                          │
│ Email: john@example.com                 │
│ Phone: +91-9999999999                   │
│ Gender: Male                            │
│ Age: 28                                 │
│                                         │
│ ─────────────────────────────────────── │
│ TICKET INFORMATION                      │
│ PNR: 7482165433                         │
│ Coach: B1 | Seat: 24                    │
│ Berth: Upper                            │
│ Status: ✅ Confirmed                    │
│                                         │
│ ─────────────────────────────────────── │
│ FARE BREAKDOWN                          │
│ Base Fare: ₹2,500                       │
│ Taxes: ₹150                             │
│ Service Fee: ₹50                        │
│ TOTAL: ₹2,700                           │
│                                         │
│ Payment Mode: Credit Card               │
│ Transaction ID: TXN123456789            │
│                                         │
│ ─────────────────────────────────────── │
│ CANCELLATION POLICY                     │
│ Time Remaining: 48h 22m                 │
│ Refund Available: 100%                  │
│                                         │
│ [Cancel Booking]  [Download Ticket]     │
│ [Share with Others] [Print]             │
│                                         │
└─────────────────────────────────────────┘
```

**Screen 3: Settings Page**
```
┌─────────────────────────────────────────┐
│ SETTINGS                            [<]  │
├─────────────────────────────────────────┤
│                                         │
│ 👤 PROFILE                              │
│ ─────────────────────────────────────── │
│ Full Name: John Doe          [Edit]     │
│ Email: john@example.com      [Edit]     │
│ Phone: +91-9999999999        [Edit]     │
│ Date of Birth: Jan 1, 1998   [Edit]     │
│ Gender: Male                 [Edit]     │
│                                         │
│ 🔐 ACCOUNT SECURITY                     │
│ ─────────────────────────────────────── │
│ Password              [Change]          │
│ 2-Factor Auth (SMS)   [Disabled]        │
│                                         │
│ 💳 PAYMENT METHODS                      │
│ ─────────────────────────────────────── │
│ ☑ Credit Card: XXXX XXXX 4242          │
│ ☑ UPI: john@okhdfcbank                 │
│ ☐ Debit Card          [+ Add]           │
│ ☐ Net Banking         [+ Add]           │
│                                         │
│ 🔔 NOTIFICATION PREFERENCES              │
│ ─────────────────────────────────────── │
│ ☑ Email: Booking confirmation          │
│ ☑ Email: Price alerts                  │
│ ☑ SMS: Journey reminders               │
│ ☑ Push: Delay alerts                   │
│ ☑ Telegram: Fare updates               │
│                                         │
│ 🗑️ DANGER ZONE                         │
│ ─────────────────────────────────────── │
│ [Delete Account]  [Export Data]         │
│                                         │
└─────────────────────────────────────────┘
```

### 2.2 DATABASE SCHEMA

```sql
-- User profile extension (if needed)
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Personal Info
  full_name VARCHAR(255),
  date_of_birth DATE,
  gender VARCHAR(20),
  avatar_url VARCHAR(1024),
  
  -- Loyalty
  loyalty_points INTEGER DEFAULT 0,
  loyalty_tier VARCHAR(50) DEFAULT 'bronze', -- bronze, silver, gold, platinum
  
  -- Preferences
  preferred_class VARCHAR(50),
  preferred_berth VARCHAR(50),
  seat_preference VARCHAR(50),
  notification_email BOOLEAN DEFAULT true,
  notification_sms BOOLEAN DEFAULT true,
  notification_push BOOLEAN DEFAULT true,
  
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  UNIQUE(user_id)
);

-- Saved routes (for quick access)
CREATE TABLE IF NOT EXISTS saved_routes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  from_station VARCHAR(10) NOT NULL,
  to_station VARCHAR(10) NOT NULL,
  frequency VARCHAR(50), -- 'rarely', 'monthly', 'weekly', 'daily'
  last_searched TIMESTAMP,
  
  created_at TIMESTAMP DEFAULT now(),
  
  UNIQUE(user_id, from_station, to_station)
);

-- Payment methods
CREATE TABLE IF NOT EXISTS payment_methods (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Razorpay Customer ID
  razorpay_customer_id VARCHAR(255),
  
  -- Stored details (encrypted)
  payment_method_type VARCHAR(50), -- 'card', 'upi', 'wallet', 'netbanking'
  display_name VARCHAR(255),
  is_default BOOLEAN DEFAULT false,
  
  -- Last 4 digits (for reference, not security)
  last_4 VARCHAR(4),
  
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Trip history (denormalized for fast queries)
CREATE TABLE IF NOT EXISTS user_trip_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  booking_id UUID NOT NULL REFERENCES bookings(id),
  
  from_station VARCHAR(10),
  to_station VARCHAR(10),
  train_number VARCHAR(20),
  journey_date DATE,
  
  created_at TIMESTAMP DEFAULT now()
);

-- Indexes
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_saved_routes_user_id ON saved_routes(user_id);
CREATE INDEX idx_payment_methods_user_id ON payment_methods(user_id);
CREATE INDEX idx_trip_history_user_id ON user_trip_history(user_id);
CREATE INDEX idx_trip_history_journey_date ON user_trip_history(journey_date);
```

### 2.3 FRONTEND COMPONENTS

```typescript
// File: frontend/src/pages/Dashboard.tsx
import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useBookings } from "@/api/hooks/useBookings";
import { UpcomingJourneys } from "@/components/dashboard/UpcomingJourneys";
import { PastJourneys } from "@/components/dashboard/PastJourneys";
import { SavedRoutes } from "@/components/dashboard/SavedRoutes";
import { ProfileCard } from "@/components/dashboard/ProfileCard";
import { Tabs } from "@/components/ui/tabs";

export function Dashboard() {
  const { user } = useAuth();
  const { bookings, loading } = useBookings();
  
  const upcomingBookings = bookings.filter(b => new Date(b.journey_date) > new Date());
  const pastBookings = bookings.filter(b => new Date(b.journey_date) <= new Date());

  return (
    <div className="container py-8">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="md:col-span-2">
          <h1 className="text-3xl font-bold mb-2">Welcome, {user?.displayName || 'Traveler'}</h1>
          <p className="text-muted-foreground">Manage your bookings and preferences</p>
        </div>
        <ProfileCard user={user} />
      </div>

      <Tabs defaultValue="upcoming" className="w-full">
        <TabsList>
          <TabsTrigger value="upcoming">
            📅 Upcoming ({upcomingBookings.length})
          </TabsTrigger>
          <TabsTrigger value="past">
            ✅ Past ({pastBookings.length})
          </TabsTrigger>
          <TabsTrigger value="saved">
            ❤️ Saved Routes
          </TabsTrigger>
          <TabsTrigger value="settings">
            ⚙️ Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming">
          <UpcomingJourneys bookings={upcomingBookings} loading={loading} />
        </TabsContent>

        <TabsContent value="past">
          <PastJourneys bookings={pastBookings} loading={loading} />
        </TabsContent>

        <TabsContent value="saved">
          <SavedRoutes />
        </TabsContent>

        <TabsContent value="settings">
          <DashboardSettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### 2.4 BACKEND APIS

```python
# File: backend/api/v1/dashboard.py

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy import select, and_

from ..auth import verify_token
from ...database import get_db
from ...models import User, Booking, SavedRoute

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/profile")
async def get_profile(user_id: str = Depends(verify_token), db = Depends(get_db)):
    """Get user profile with loyalty points, preferences"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "loyalty_points": user.loyalty_points,
        "loyalty_tier": user.loyalty_tier,
        "preferred_class": user.preferred_class,
    }

@router.get("/bookings/upcoming")
async def get_upcoming_bookings(
    user_id: str = Depends(verify_token),
    db = Depends(get_db)
):
    """Get upcoming journeys (next 30 days)"""
    future_date = datetime.now()
    
    stmt = select(Booking).where(
        and_(
            Booking.user_id == user_id,
            Booking.journey_date >= future_date,
            Booking.status != "CANCELLED"
        )
    ).order_by(Booking.journey_date.asc())
    
    bookings = await db.execute(stmt)
    return bookings.scalars().all()

@router.get("/bookings/past")
async def get_past_bookings(
    user_id: str = Depends(verify_token),
    skip: int = 0,
    limit: int = 20,
    db = Depends(get_db)
):
    """Get past journeys with pagination"""
    stmt = select(Booking).where(
        and_(
            Booking.user_id == user_id,
            Booking.journey_date < datetime.now(),
            Booking.status.in_(["COMPLETED", "REVIEWED"])
        )
    ).order_by(Booking.journey_date.desc()).offset(skip).limit(limit)
    
    bookings = await db.execute(stmt)
    return bookings.scalars().all()

@router.get("/saved-routes")
async def get_saved_routes(user_id: str = Depends(verify_token), db = Depends(get_db)):
    """Get user's saved routes"""
    stmt = select(SavedRoute).where(SavedRoute.user_id == user_id)
    routes = await db.execute(stmt)
    return routes.scalars().all()

@router.post("/saved-routes")
async def save_route(
    from_station: str,
    to_station: str,
    user_id: str = Depends(verify_token),
    db = Depends(get_db)
):
    """Save a route for quick access"""
    saved_route = SavedRoute(
        user_id=user_id,
        from_station=from_station,
        to_station=to_station,
        frequency="monthly"
    )
    db.add(saved_route)
    await db.commit()
    return {"status": "saved"}

@router.put("/profile")
async def update_profile(
    profile_data: dict,
    user_id: str = Depends(verify_token),
    db = Depends(get_db)
):
    """Update user profile settings"""
    user = await db.get(User, user_id)
    for key, value in profile_data.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    await db.commit()
    return {"status": "updated"}
```

### 2.5 IMPLEMENTATION CHECKLIST

- [ ] Create `user_profiles` table migration
- [ ] Create `saved_routes` table migration
- [ ] Create `payment_methods` table migration
- [ ] Implement `GET /api/v1/dashboard/profile`
- [ ] Implement `GET /api/v1/dashboard/bookings/upcoming`
- [ ] Implement `GET /api/v1/dashboard/bookings/past`
- [ ] Implement `GET /api/v1/dashboard/saved-routes`
- [ ] Implement `POST /api/v1/dashboard/saved-routes`
- [ ] Implement `PUT /api/v1/dashboard/profile`
- [ ] Create Dashboard.tsx page
- [ ] Create UpcomingJourneys component
- [ ] Create PastJourneys component
- [ ] Create SavedRoutes component
- [ ] Create DashboardSettings component
- [ ] Create ProfileCard component
- [ ] Implement journey detail modal
- [ ] Test all endpoints
- [ ] Mobile responsive design
- [ ] Performance optimization (pagination, caching)

---

## FEATURE #3: EMAIL & SMS NOTIFICATIONS
**Timeline:** 3-4 hours  
**Priority:** High (engagement & retention)  
**Depends On:** Feature #1 (Booking confirmations)

### 3.1 PRODUCT DESIGN

#### Notification Types

```
TYPE 1: BOOKING CONFIRMATION
├─ Email: "Your booking is confirmed! PNR: 7482165433"
├─ SMS: "RouteMaster: Booking confirmed! PNR: 7482165433. Train: 12951"
└─ Trigger: When booking payment succeeds

TYPE 2: BOOKING REMINDER
├─ Email: "Your train departs tomorrow at 6:00 AM"
├─ SMS: "Reminder: Rajdhani Express departs tomorrow 6:00 AM"
└─ Trigger: 24 hours before departure

TYPE 3: DELAY ALERT
├─ Email: "Your train (12951) is running 30 minutes late"
├─ SMS: "Alert: Train 12951 is 30 mins late"
└─ Trigger: Real-time from live tracking API

TYPE 4: FARE ALERT
├─ Email: "Price drop! Delhi-Mumbai: ₹1,999 (was ₹2,500)"
├─ SMS: "Fare Alert: Delhi-Mumbai now ₹1,999"
└─ Trigger: User-created price alert threshold met

TYPE 5: REVIEW REMINDER
├─ Email: "How was your journey? Share your experience"
├─ SMS: "Rate your journey & earn 10 loyalty points"
└─ Trigger: 2 days after journey completion

TYPE 6: PROMOTIONAL
├─ Email: "🎉 Get 20% off on your next booking!"
├─ SMS: "RouteMaster: 20% discount on your next trip!"
└─ Trigger: Monthly or via admin campaign
```

### 3.2 NOTIFICATION SERVICE ARCHITECTURE

```python
# File: backend/services/notification_service.py

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
from abc import ABC, abstractmethod

class NotificationType(str, Enum):
    BOOKING_CONFIRMATION = "booking_confirmation"
    BOOKING_REMINDER = "booking_reminder"
    DELAY_ALERT = "delay_alert"
    FARE_ALERT = "fare_alert"
    REVIEW_REMINDER = "review_reminder"
    PROMOTIONAL = "promotional"

class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    TELEGRAM = "telegram"

class NotificationProvider(ABC):
    """Base class for notification providers"""
    
    @abstractmethod
    async def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        pass

class EmailProvider(NotificationProvider):
    """SendGrid email integration"""
    
    def __init__(self, api_key: str):
        from sendgrid import SendGridAPIClient
        self.sg = SendGridAPIClient(api_key)
    
    async def send(self, recipient: str, message: str, subject: str, **kwargs) -> Dict[str, Any]:
        from sendgrid.helpers.mail import Mail, Email, To, Content
        
        mail = Mail(
            from_email=Email("noreply@routemaster.app"),
            to_emails=To(recipient),
            subject=Subject(subject),
            plain_text_content=Content("text/plain", message),
            html_content=Content("text/html", kwargs.get("html", message))
        )
        
        try:
            response = self.sg.send(mail)
            return {"status": "sent", "message_id": response.headers.get("X-Message-ID")}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

class SMSProvider(NotificationProvider):
    """Twilio SMS integration"""
    
    def __init__(self, account_sid: str, auth_token: str):
        from twilio.rest import Client
        self.client = Client(account_sid, auth_token)
    
    async def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        try:
            response = self.client.messages.create(
                body=message,
                from_=kwargs.get("from_number", "+1234567890"),
                to=recipient
            )
            return {"status": "sent", "message_id": response.sid}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

class NotificationService:
    """Unified notification service"""
    
    def __init__(self, email_provider: EmailProvider, sms_provider: SMSProvider):
        self.email = email_provider
        self.sms = sms_provider
        self.templates = {}
    
    async def send_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        channels: list[NotificationChannel],
        data: Dict[str, Any]
    ):
        """Send notification via specified channels"""
        
        # Get template
        template = self.get_template(notification_type)
        
        # Get user preferences
        user_prefs = await self.get_user_notification_preferences(user_id)
        
        # Filter channels based on user preferences
        channels = [
            c for c in channels 
            if user_prefs.get(f"notification_{c.value}", True)
        ]
        
        # Send via each channel
        results = {}
        for channel in channels:
            if channel == NotificationChannel.EMAIL:
                results["email"] = await self.send_email(
                    template, data, user_prefs
                )
            elif channel == NotificationChannel.SMS:
                results["sms"] = await self.send_sms(
                    template, data, user_prefs
                )
            elif channel == NotificationChannel.PUSH:
                results["push"] = await self.send_push(
                    template, data, user_prefs
                )
        
        # Log notification
        await self.log_notification(user_id, notification_type, results)
        
        return results
    
    def get_template(self, notification_type: NotificationType):
        """Get email/SMS template"""
        templates = {
            NotificationType.BOOKING_CONFIRMATION: {
                "subject": "Booking Confirmed - {train_number}",
                "email_body": """
Hello {user_name},

Your booking has been confirmed!

Train: {train_number} {train_name}
Date: {journey_date}
From: {from_station} at {departure_time}
To: {to_station} at {arrival_time}
PNR: {pnr}
Total Amount: ₹{total_amount}

Your ticket is attached. Keep it safe!

Thank you for using RouteMaster.
""",
                "sms_body": "RouteMaster: Booking confirmed! PNR: {pnr}. Train: {train_number}. Check your email for ticket."
            },
            NotificationType.BOOKING_REMINDER: {
                "subject": "Reminder: Your train departs tomorrow",
                "email_body": "Your train {train_number} departs tomorrow at {departure_time}. Have a great journey!",
                "sms_body": "Reminder: {train_number} departs tomorrow at {departure_time}"
            },
            # ... more templates
        }
        return templates.get(notification_type, {})
    
    async def send_email(self, template, data, user_prefs):
        subject = template["subject"].format(**data)
        body = template["email_body"].format(**data)
        
        return await self.email.send(
            recipient=user_prefs["email"],
            subject=subject,
            message=body
        )
    
    async def send_sms(self, template, data, user_prefs):
        message = template["sms_body"].format(**data)
        
        return await self.sms.send(
            recipient=user_prefs["phone"],
            message=message
        )
    
    async def send_push(self, template, data, user_prefs):
        # Firebase Cloud Messaging implementation (Feature #8)
        pass
    
    async def get_user_notification_preferences(self, user_id: str):
        # Fetch from database
        pass
    
    async def log_notification(self, user_id: str, notification_type, results):
        # Log to database for tracking
        pass

```

### 3.3 NOTIFICATION TRIGGERS

```python
# File: backend/api/v1/bookings.py (add to existing)

@router.post("/bookings/{booking_id}/confirm-payment")
async def confirm_booking_payment(
    booking_id: str,
    notification_service: NotificationService = Depends(),
    db = Depends(get_db)
):
    """Confirm booking after payment"""
    
    booking = await db.get(Booking, booking_id)
    booking.status = "PAYMENT_CONFIRMED"
    booking.payment_confirmed_at = datetime.now()
    
    await db.commit()
    
    # Trigger notification
    await notification_service.send_notification(
        user_id=booking.user_id,
        notification_type=NotificationType.BOOKING_CONFIRMATION,
        channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        data={
            "user_name": booking.user.full_name,
            "train_number": booking.train_number,
            "train_name": booking.train_name,
            "journey_date": booking.journey_date,
            "from_station": booking.from_station,
            "to_station": booking.to_station,
            "departure_time": booking.departure_time,
            "arrival_time": booking.arrival_time,
            "pnr": booking.pnr,
            "total_amount": booking.total_amount,
        }
    )
    
    return {"status": "confirmed"}

# Scheduled job for reminder notifications
@app.on_event("startup")
async def start_reminder_scheduler():
    """Start background job for sending reminders"""
    
    async def send_reminders():
        while True:
            # Send booking reminders 24h before journey
            tomorrow = datetime.now() + timedelta(days=1)
            bookings = await db.query(Booking).filter(
                Booking.journey_date == tomorrow.date(),
                Booking.status == "TICKET_CONFIRMED",
                Booking.reminder_sent == False
            ).all()
            
            for booking in bookings:
                await notification_service.send_notification(
                    user_id=booking.user_id,
                    notification_type=NotificationType.BOOKING_REMINDER,
                    channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
                    data={
                        "user_name": booking.user.full_name,
                        "train_number": booking.train_number,
                        "departure_time": booking.departure_time,
                    }
                )
                booking.reminder_sent = True
                await db.commit()
            
            # Wait 1 hour before next check
            await asyncio.sleep(3600)
    
    asyncio.create_task(send_reminders())
```

### 3.4 IMPLEMENTATION CHECKLIST

- [ ] Set up SendGrid API key in .env
- [ ] Set up Twilio API key in .env
- [ ] Create `notification_logs` table
- [ ] Implement EmailProvider class
- [ ] Implement SMSProvider class
- [ ] Implement NotificationService class
- [ ] Create email templates for each notification type
- [ ] Create SMS templates for each notification type
- [ ] Implement notification trigger in booking confirmation
- [ ] Implement 24h reminder scheduler (background job)
- [ ] Implement fare alert notifications
- [ ] Implement review reminder notifications
- [ ] Add notification preferences to user settings
- [ ] Create API endpoint for notification preferences
- [ ] Test email delivery (sendgrid sandbox)
- [ ] Test SMS delivery (Twilio test mode)
- [ ] Add unsubscribe links to emails
- [ ] Monitor delivery rates

---

## FEATURE #4: TELEGRAM BOT WIRING
**Timeline:** 2-3 hours  
**Priority:** Medium (low-friction user acquisition)  
**Depends On:** Feature #1 (Bookings)

### 4.1 PRODUCT DESIGN

#### Bot Commands

```
/start
  → Welcome message + quick links

/search <from> <to> [date]
  → Search for trains
  → Example: /search Delhi Mumbai tomorrow
  → Returns: Top 3 results with inline keyboard

/live <train_number>
  → Get live train status
  → Example: /live 12951
  → Returns: Current station, delay, next stops

/pnr <pnr_number>
  → Check PNR status
  → Example: /pnr 7482165433
  → Returns: Passenger details, berth, status

/mybookings
  → Show upcoming bookings
  → Returns: List with quick actions

/alert <from> <to> <price>
  → Set fare alert
  → Example: /alert Delhi Mumbai 1500
  → Returns: Confirmation

/cancel <booking_id>
  → Cancel booking (if allowed)
  → Example: /cancel BOOK123
  → Returns: Refund calculation

/help
  → Show command list
```

### 4.2 TELEGRAM BOT SERVICE

```python
# File: backend/services/telegram_bot.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import httpx

class RouteMasterTelegramBot:
    
    def __init__(self, token: str, api_base_url: str):
        self.token = token
        self.api_base_url = api_base_url
        self.app = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup command handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("search", self.search))
        self.app.add_handler(CommandHandler("live", self.live_status))
        self.app.add_handler(CommandHandler("pnr", self.check_pnr))
        self.app.add_handler(CommandHandler("mybookings", self.my_bookings))
        self.app.add_handler(CommandHandler("alert", self.set_alert))
        self.app.add_handler(CommandHandler("cancel", self.cancel_booking))
        self.app.add_handler(CommandHandler("help", self.show_help))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        text = """
👋 Welcome to RouteMaster - Book trains with ease!

Quick Commands:
🔍 /search Delhi Mumbai tomorrow
🚂 /live 12951
📋 /pnr 7482165433
📅 /mybookings
🔔 /alert Delhi Mumbai 1500
❌ /cancel BOOK123
❓ /help

Book now: https://routemaster.app
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Search", url="https://routemaster.app"),
                InlineKeyboardButton("📅 My Bookings", callback_data="mybookings"),
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /search <from_station> <to_station> [date]\n"
                "Example: /search Delhi Mumbai tomorrow"
            )
            return
        
        from_station = context.args[0]
        to_station = context.args[1]
        date = context.args[2] if len(context.args) > 2 else "today"
        
        # Call our API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/api/v1/search/routes",
                params={
                    "from_station": from_station,
                    "to_station": to_station,
                    "date": date
                }
            )
            
            if response.status_code != 200:
                await update.message.reply_text("❌ Search failed. Please try again.")
                return
            
            results = response.json()
            
            if not results:
                await update.message.reply_text("No trains found for this route.")
                return
            
            # Show top 3 results
            message = f"🚂 Trains from {from_station} to {to_station}\n\n"
            
            keyboard = []
            for idx, train in enumerate(results[:3]):
                message += f"{idx+1}. {train['train_number']} - {train['train_name']}\n"
                message += f"   Depart: {train['departure_time']} | Arrive: {train['arrival_time']}\n"
                message += f"   ₹{train['fare']} | {train['available_seats']} seats\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"Book {train['train_number']}",
                        url=f"https://routemaster.app/book?train={train['train_number']}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
    
    async def live_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /live command"""
        if not context.args:
            await update.message.reply_text("Usage: /live <train_number>")
            return
        
        train_number = context.args[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/api/v1/live/train/{train_number}"
            )
            
            if response.status_code != 200:
                await update.message.reply_text("Train not found.")
                return
            
            train = response.json()
            
            status = "✅ On Time" if train['delay'] == 0 else f"⚠️ {train['delay']} min late"
            
            message = f"""
🚂 {train['train_number']} - {train['train_name']}

{status}

Current Location: {train['current_station']}
Arrival: {train['next_arrival_time']}

Next Stops:
"""
            for stop in train['next_stops'][:3]:
                message += f"  • {stop['station']} - {stop['arrival_time']}\n"
            
            await update.message.reply_text(message)
    
    async def check_pnr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pnr command"""
        if not context.args:
            await update.message.reply_text("Usage: /pnr <pnr_number>")
            return
        
        pnr = context.args[0]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/api/v1/pnr/{pnr}"
            )
            
            if response.status_code != 200:
                await update.message.reply_text("PNR not found.")
                return
            
            data = response.json()
            
            message = f"""
📋 PNR Status: {data['pnr']}

Train: {data['train_number']} - {data['train_name']}
Journey Date: {data['journey_date']}
Status: {data['status']}

Passengers:
"""
            for p in data['passengers']:
                message += f"  • {p['name']} - {p['berth']}\n"
            
            await update.message.reply_text(message)
    
    async def my_bookings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mybookings command"""
        # This would require auth - for now show login prompt
        keyboard = [[InlineKeyboardButton("Login to see bookings", 
                    url="https://routemaster.app/login")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Login to view your bookings",
            reply_markup=reply_markup
        )
    
    async def set_alert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /alert command"""
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /alert <from> <to> <price>\n"
                "Example: /alert Delhi Mumbai 1500"
            )
            return
        
        from_station, to_station, price = context.args[0], context.args[1], context.args[2]
        
        # Save alert (requires linking Telegram to RouteMaster account)
        keyboard = [[InlineKeyboardButton("Link Account", 
                    url="https://routemaster.app/telegram/link")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Alert set for {from_station} → {to_station} at ₹{price}\n\n"
            "Link your RouteMaster account to save alerts",
            reply_markup=reply_markup
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button presses"""
        query = update.callback_query
        
        if query.data == "help":
            await query.answer()
            await self.show_help(update, context)
        elif query.data == "settings":
            await query.answer()
            await query.edit_message_text("Settings: Link your account at https://routemaster.app")
        elif query.data == "mybookings":
            await query.answer()
            await query.edit_message_text("Login: https://routemaster.app/login")
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        help_text = """
🤖 RouteMaster Telegram Bot - Help

Available Commands:
🔍 /search <from> <to> [date] - Search trains
🚂 /live <train_no> - Check train status
📋 /pnr <pnr> - Check PNR status
📅 /mybookings - View your bookings
🔔 /alert <from> <to> <price> - Set fare alert
❌ /cancel <booking_id> - Cancel booking
❓ /help - This message

Examples:
  /search Delhi Mumbai tomorrow
  /live 12951
  /pnr 7482165433
  /alert Delhi Mumbai 1500

Need help? https://routemaster.app/support
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text)
        else:
            await update.message.reply_text(help_text)
    
    async def cancel_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        if not context.args:
            await update.message.reply_text("Usage: /cancel <booking_id>")
            return
        
        booking_id = context.args[0]
        
        # Require login
        keyboard = [[InlineKeyboardButton("Login to cancel", 
                    url="https://routemaster.app/login")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Login to your RouteMaster account to cancel bookings",
            reply_markup=reply_markup
        )
    
    def run(self):
        """Start the bot"""
        self.app.run_polling()
```

### 4.3 IMPLEMENTATION CHECKLIST

- [ ] Create Telegram bot via BotFather (@BotFather on Telegram)
- [ ] Get bot token
- [ ] Set up webhook endpoint
- [ ] Implement RouteMasterTelegramBot class
- [ ] Implement /search command
- [ ] Implement /live command
- [ ] Implement /pnr command
- [ ] Implement /mybookings command (with auth)
- [ ] Implement /alert command
- [ ] Implement /cancel command
- [ ] Implement inline keyboards
- [ ] Add bot link to frontend (Login page)
- [ ] Test all commands
- [ ] Deploy webhook
- [ ] Monitor bot usage

---

## FEATURE #5: ADMIN OPERATIONS DASHBOARD
**Timeline:** 6-8 hours  
**Priority:** High (operational visibility)  
**Depends On:** Features #1-3 (Bookings, Notifications)

### 5.1 PRODUCT DESIGN

#### Admin Dashboard Sections

```
┌──────────────────────────────────────────────────┐
│  🛠️ ADMIN DASHBOARD - Operations Overview        │
├──────────────────────────────────────────────────┤
│                                                   │
│  📊 KEY METRICS (Today)                          │
│  ┌──────────┬──────────┬──────────┬──────────┐   │
│  │  Searches│ Bookings │ Revenue  │ Failures │   │
│  │   2,456  │    234   │ ₹156,000 │   12     │   │
│  └──────────┴──────────┴──────────┴──────────┘   │
│                                                   │
│  🚂 LIVE TRAIN ALERTS (Need Action)               │
│  ┌────────────────────────────────────────────┐  │
│  │ 🔴 12951 Rajdhani Express: 45 min late     │  │
│  │    50 passengers affected                  │  │
│  │    [Send SMS Alert] [Send Email]           │  │
│  │                                            │  │
│  │ 🟡 25052 Golden Temple: 15 min late       │  │
│  │    12 passengers affected                  │  │
│  │    [Send Notification]                     │  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  💳 PAYMENT ALERTS                               │
│  ┌────────────────────────────────────────────┐  │
│  │ Failed Payments (Last 24h): 8              │  │
│  │  • 3 timeouts                              │  │
│  │  • 2 declined cards                        │  │
│  │  • 2 user cancellations                    │  │
│  │  • 1 gateway error                         │  │
│  │ [Retry Failed] [Investigate]               │  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  📋 PENDING ACTIONS                              │
│  ┌────────────────────────────────────────────┐  │
│  │ Bookings Awaiting IRCTC Confirmation: 34   │  │
│  │  [Sync Now] [Manual Review]                │  │
│  │                                            │  │
│  │ Refunds Pending: 5                         │  │
│  │  [Process] [View Details]                  │  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  📈 CHARTS                                       │
│  ├─ Hourly Bookings (Last 24h)                   │
│  ├─ Revenue Trend (Last 7 days)                  │
│  ├─ Failure Rate by Hour                        │
│  └─ Top Routes                                  │
│                                                   │
└──────────────────────────────────────────────────┘
```

### 5.2 BACKEND APIS

```python
# File: backend/api/v1/admin.py

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_

from ..auth import verify_admin_token
from ...database import get_db
from ...models import Booking, Payment, TrainLive, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/metrics/today")
async def get_today_metrics(
    admin_id: str = Depends(verify_admin_token),
    db = Depends(get_db)
):
    """Get key metrics for today"""
    today = datetime.now().date()
    
    # Count searches
    searches = await db.query(Search).filter(
        Search.created_at >= today
    ).count()
    
    # Count bookings
    bookings = await db.query(Booking).filter(
        Booking.created_at >= today
    ).count()
    
    # Calculate revenue
    revenue = await db.query(func.sum(Payment.amount)).filter(
        and_(
            Payment.status == "CONFIRMED",
            Payment.created_at >= today
        )
    ).scalar()
    
    # Count failures
    failures = await db.query(Payment).filter(
        and_(
            Payment.status.in_(["FAILED", "TIMEOUT"]),
            Payment.created_at >= today
        )
    ).count()
    
    return {
        "searches": searches,
        "bookings": bookings,
        "revenue": revenue or 0,
        "failures": failures
    }

@router.get("/alerts/trains/delayed")
async def get_delayed_trains(
    admin_id: str = Depends(verify_admin_token),
    min_delay: int = 15,
    db = Depends(get_db)
):
    """Get trains with significant delays"""
    
    # Query live train data
    delayed = await db.query(TrainLive).filter(
        TrainLive.delay >= min_delay
    ).all()
    
    # Count affected bookings
    result = []
    for train in delayed:
        affected = await db.query(Booking).filter(
            Booking.train_number == train.train_number,
            Booking.status.in_(["CONFIRMED", "TICKET_CONFIRMED"])
        ).count()
        
        result.append({
            "train_number": train.train_number,
            "train_name": train.train_name,
            "delay_minutes": train.delay,
            "current_station": train.current_station,
            "affected_passengers": affected,
            "action": "send_alert"
        })
    
    return result

@router.post("/alerts/trains/{train_number}/send-notification")
async def send_train_delay_notification(
    train_number: str,
    message: str = None,
    admin_id: str = Depends(verify_admin_token),
    notification_service = Depends(),
    db = Depends(get_db)
):
    """Send delay notification to affected passengers"""
    
    # Get all affected bookings
    bookings = await db.query(Booking).filter(
        Booking.train_number == train_number,
        Booking.status.in_(["CONFIRMED", "TICKET_CONFIRMED"])
    ).all()
    
    # Get train info
    train = await db.query(TrainLive).filter(
        TrainLive.train_number == train_number
    ).first()
    
    sent_count = 0
    
    for booking in bookings:
        data = {
            "user_name": booking.user.full_name,
            "train_number": train_number,
            "delay_minutes": train.delay,
            "message": message or f"Train is running {train.delay} minutes late"
        }
        
        await notification_service.send_notification(
            user_id=booking.user_id,
            notification_type=NotificationType.DELAY_ALERT,
            channels=[NotificationChannel.SMS, NotificationChannel.EMAIL],
            data=data
        )
        
        sent_count += 1
    
    return {
        "status": "sent",
        "passengers_notified": sent_count
    }

@router.get("/payments/failed")
async def get_failed_payments(
    admin_id: str = Depends(verify_admin_token),
    hours: int = 24,
    db = Depends(get_db)
):
    """Get failed payments in last N hours"""
    
    since = datetime.now() - timedelta(hours=hours)
    
    failed = await db.query(Payment).filter(
        and_(
            Payment.status.in_(["FAILED", "TIMEOUT"]),
            Payment.created_at >= since
        )
    ).order_by(Payment.created_at.desc()).all()
    
    # Group by failure reason
    by_reason = {}
    for payment in failed:
        reason = payment.failure_reason or "unknown"
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append({
            "id": payment.id,
            "user_id": payment.user_id,
            "amount": payment.amount,
            "created_at": payment.created_at
        })
    
    return {
        "total_failed": len(failed),
        "by_reason": by_reason
    }

@router.post("/payments/{payment_id}/retry")
async def retry_failed_payment(
    payment_id: str,
    admin_id: str = Depends(verify_admin_token),
    payment_service = Depends(),
    db = Depends(get_db)
):
    """Retry a failed payment"""
    
    payment = await db.get(Payment, payment_id)
    
    if payment.status not in ["FAILED", "TIMEOUT"]:
        raise HTTPException(status_code=400, detail="Payment not in failed state")
    
    # Initiate retry
    result = await payment_service.retry_payment(payment_id)
    
    return result

@router.get("/bookings/pending-confirmation")
async def get_pending_confirmations(
    admin_id: str = Depends(verify_admin_token),
    db = Depends(get_db)
):
    """Get bookings awaiting IRCTC confirmation"""
    
    pending = await db.query(Booking).filter(
        Booking.status == "PAYMENT_CONFIRMED"
    ).all()
    
    return {
        "count": len(pending),
        "bookings": [
            {
                "id": b.id,
                "user_name": b.user.full_name,
                "train_number": b.train_number,
                "journey_date": b.journey_date,
                "payment_confirmed_at": b.payment_confirmed_at,
                "time_waiting_hours": (
                    datetime.now() - b.payment_confirmed_at
                ).total_seconds() / 3600
            }
            for b in pending
        ]
    }

@router.post("/bookings/{booking_id}/sync-irctc")
async def sync_booking_with_irctc(
    booking_id: str,
    admin_id: str = Depends(verify_admin_token),
    irctc_service = Depends(),
    db = Depends(get_db)
):
    """Manually sync booking with IRCTC"""
    
    booking = await db.get(Booking, booking_id)
    
    # Call IRCTC API to get PNR
    result = await irctc_service.get_booking_status(
        user_id=booking.irctc_user_id,
        booking_reference=booking.irctc_booking_ref
    )
    
    if result["status"] == "confirmed":
        booking.pnr = result["pnr"]
        booking.status = "TICKET_CONFIRMED"
        booking.pnr_confirmed_at = datetime.now()
        await db.commit()
    
    return result

@router.get("/refunds/pending")
async def get_pending_refunds(
    admin_id: str = Depends(verify_admin_token),
    db = Depends(get_db)
):
    """Get pending refunds"""
    
    pending = await db.query(Booking).filter(
        Booking.status == "REFUND_INITIATED"
    ).all()
    
    return {
        "count": len(pending),
        "total_amount": sum(b.total_amount for b in pending),
        "bookings": [
            {
                "id": b.id,
                "user_name": b.user.full_name,
                "amount": b.total_amount,
                "refund_reason": b.cancellation_reason,
                "initiated_at": b.cancellation_initiated_at
            }
            for b in pending
        ]
    }

@router.post("/refunds/{booking_id}/process")
async def process_refund(
    booking_id: str,
    admin_id: str = Depends(verify_admin_token),
    razorpay_service = Depends(),
    db = Depends(get_db)
):
    """Process pending refund"""
    
    booking = await db.get(Booking, booking_id)
    payment = await db.query(Payment).filter(
        Payment.booking_id == booking_id,
        Payment.status == "CONFIRMED"
    ).first()
    
    # Calculate refund amount based on policy
    refund_amount = calculate_refund_amount(booking)
    
    # Initiate Razorpay refund
    result = await razorpay_service.create_refund(
        payment_id=payment.razorpay_payment_id,
        amount=int(refund_amount * 100)
    )
    
    # Update booking status
    booking.status = "REFUNDED"
    booking.refund_amount = refund_amount
    booking.refund_processed_at = datetime.now()
    
    await db.commit()
    
    return result
```

### 5.3 FRONTEND ADMIN DASHBOARD

```typescript
// File: frontend/src/pages/Admin/AdminOperations.tsx

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { adminApi } from "@/api/admin";
import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";

export function AdminOperations() {
  const [metrics, setMetrics] = useState(null);
  const [delayedTrains, setDelayedTrains] = useState([]);
  const [failedPayments, setFailedPayments] = useState([]);
  const [pendingConfirmations, setPendingConfirmations] = useState([]);
  const [pendingRefunds, setPendingRefunds] = useState([]);

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchAllData = async () => {
    const [metrics, trains, payments, confirmations, refunds] = await Promise.all([
      adminApi.getTodayMetrics(),
      adminApi.getDelayedTrains(),
      adminApi.getFailedPayments(),
      adminApi.getPendingConfirmations(),
      adminApi.getPendingRefunds(),
    ]);

    setMetrics(metrics);
    setDelayedTrains(trains);
    setFailedPayments(payments);
    setPendingConfirmations(confirmations);
    setPendingRefunds(refunds);
  };

  const handleSendTrainAlert = async (trainNumber: string) => {
    await adminApi.sendTrainDelayNotification(trainNumber);
    fetchAllData();
  };

  return (
    <div className="container py-8 space-y-8">
      <h1 className="text-4xl font-bold">Operations Dashboard</h1>

      {/* Key Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Searches Today
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.searches}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Bookings Today
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.bookings}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Revenue Today
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">₹{metrics.revenue.toLocaleString()}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Failed Payments
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{metrics.failures}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Train Delays Alert */}
      {delayedTrains.length > 0 && (
        <Card className="border-orange-200 bg-orange-50">
          <CardHeader>
            <CardTitle className="text-orange-900">🚂 Train Delays Alert</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {delayedTrains.map((train) => (
              <div key={train.train_number} className="border-b pb-4 last:border-0">
                <p className="font-semibold">
                  {train.train_number} - {train.delay_minutes} min late
                </p>
                <p className="text-sm text-muted-foreground">
                  {train.affected_passengers} passengers affected
                </p>
                <div className="flex gap-2 mt-2">
                  <Button
                    size="sm"
                    onClick={() => handleSendTrainAlert(train.train_number)}
                  >
                    Send SMS Alert
                  </Button>
                  <Button size="sm" variant="outline">
                    Send Email
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Payment Failures */}
      {failedPayments.total_failed > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-red-900">💳 Failed Payments ({failedPayments.total_failed})</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.entries(failedPayments.by_reason).map(([reason, payments]) => (
              <div key={reason} className="mb-2">
                <p className="text-sm">
                  <strong>{payments.length}</strong> - {reason}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Pending Confirmations */}
      {pendingConfirmations.count > 0 && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardHeader>
            <CardTitle className="text-yellow-900">
              📋 Pending IRCTC Confirmations ({pendingConfirmations.count})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {pendingConfirmations.bookings.slice(0, 5).map((booking) => (
                <div key={booking.id} className="flex justify-between items-center text-sm">
                  <div>
                    <p>{booking.train_number}</p>
                    <p className="text-muted-foreground">{booking.user_name}</p>
                  </div>
                  <Button size="sm" variant="ghost">
                    Sync
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pending Refunds */}
      {pendingRefunds.count > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              🔄 Pending Refunds ({pendingRefunds.count}) - ₹{pendingRefunds.total_amount}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {pendingRefunds.bookings.map((booking) => (
                <div key={booking.id} className="flex justify-between items-center">
                  <div>
                    <p>{booking.user_name}</p>
                    <p className="text-sm text-muted-foreground">₹{booking.amount}</p>
                  </div>
                  <Button size="sm">Process</Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

### 5.4 IMPLEMENTATION CHECKLIST

- [ ] Create `train_live` table with delay tracking
- [ ] Implement `GET /api/v1/admin/metrics/today`
- [ ] Implement `GET /api/v1/admin/alerts/trains/delayed`
- [ ] Implement `POST /api/v1/admin/alerts/trains/{train_number}/send-notification`
- [ ] Implement `GET /api/v1/admin/payments/failed`
- [ ] Implement `POST /api/v1/admin/payments/{payment_id}/retry`
- [ ] Implement `GET /api/v1/admin/bookings/pending-confirmation`
- [ ] Implement `POST /api/v1/admin/bookings/{booking_id}/sync-irctc`
- [ ] Implement `GET /api/v1/admin/refunds/pending`
- [ ] Implement `POST /api/v1/admin/refunds/{booking_id}/process`
- [ ] Create AdminOperations.tsx page
- [ ] Implement metrics cards
- [ ] Implement train delay alerts section
- [ ] Implement payment failures section
- [ ] Implement pending confirmations section
- [ ] Implement pending refunds section
- [ ] Add real-time refresh (60s interval)
- [ ] Add charts/graphs
- [ ] Test all endpoints
- [ ] Mobile responsive design
- [ ] Add admin role verification

---

## IMPLEMENTATION PRIORITIES

### Week 1 (Best ROI):
1. ✅ Feature #1: Booking & Payment (Design ready)
2. 🎯 Feature #2: User Dashboard (start Week 1 day 3)
3. 🎯 Feature #3: Notifications (start Week 1 day 5)

### Week 2:
4. 🎯 Feature #4: Telegram Bot (parallel with Week 1)
5. 🎯 Feature #5: Admin Dashboard (start Week 2)

---

## BRANCHING STRATEGY

```bash
# Create feature branches
git checkout -b feature/booking-flow-complete
git checkout -b feature/user-dashboard
git checkout -b feature/notifications
git checkout -b feature/telegram-bot
git checkout -b feature/admin-dashboard

# Work on each feature in parallel
# Create PR when ready for review
# Merge to main after approval + testing
```

---

## SUCCESS CRITERIA

Each feature is "done" when:
- [ ] All APIs implemented & tested
- [ ] All frontend components completed
- [ ] All database migrations applied
- [ ] All edge cases handled
- [ ] All error scenarios tested
- [ ] Mobile responsive
- [ ] Performance > 90 Lighthouse score
- [ ] Security audit passed
- [ ] Documentation updated
- [ ] Ready for production deployment

---

**Last Updated:** July 29, 2026  
**Next Review:** After Feature #1 completion
