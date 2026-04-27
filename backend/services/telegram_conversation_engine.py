import logging
import asyncio
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import uuid

from database.models import User, Booking, TelegramAccount, SOSEvent, SOSTelemetry
from services.telegram_dispatcher import telegram_dispatcher
from services.telegram_session_manager import session_manager
from services.unified_travel_planner import UnifiedTravelPlanner, TravelRequest, TravelPreference
from utils.nlp_router import get_local_intent
from database.config import Config

logger = logging.getLogger("telegram.conversation_engine")

class ConversationEngine:
    """
    Stateful conversation engine for Telegram.
    Processes messages based on current session state.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.planner = UnifiedTravelPlanner(db)

    async def handle_message(self, chat_id: int, user_id: str, text: str):
        session = session_manager.get_or_create_session(self.db, str(chat_id), user_id)
        
        # 1. Handle high-priority intents first
        intent_res = await asyncio.to_thread(get_local_intent, text)
        intent = intent_res.get("intent") if intent_res else "unknown"
        
        if intent == "sos":
            # FORCE CLEAR state to handle emergency
            session_manager.clear_session(self.db, f"{chat_id}:{user_id}")
            return await self._handle_sos_request(chat_id)

        # 2. Handle stateful flows
        if session.current_intent == "search":
            return await self._handle_search_flow(chat_id, user_id, text, session)
        
        if session.current_intent == "pnr":
            return await self._handle_pnr_flow(chat_id, user_id, text, session)

        if session.current_intent == "booking":
            return await self._handle_booking_flow(chat_id, user_id, text, session)
            
        # 3. Fallback to NLP for new intents
        return await self._process_new_intent(chat_id, user_id, text, intent_res)

    async def handle_location(self, chat_id: int, latitude: float, longitude: float):
        """Processes live location updates for journey tracking."""
        account = self.db.query(TelegramAccount).filter(TelegramAccount.telegram_id == str(chat_id)).first()
        if not account:
            return

        from database.models import LiveLocation
        location = LiveLocation(
            user_id=account.user_id,
            latitude=latitude,
            longitude=longitude,
            created_at=datetime.utcnow()
        )
        self.db.add(location)
        
        # Also check if there's an active SOS for this user
        active_sos = self.db.query(SOSEvent).filter(
            SOSEvent.user_id == account.user_id,
            SOSEvent.status == "ACTIVE"
        ).first()
        
        if active_sos:
            telemetry = SOSTelemetry(
                event_id=active_sos.id,
                lat=latitude,
                lng=longitude,
                timestamp=datetime.utcnow()
            )
            self.db.add(telemetry)
            
        self.db.commit()
        logger.info(f"Updated live location for Telegram user {chat_id}")

    async def _handle_booking_flow(self, chat_id: int, user_id: str, text: str, session):
        if session.current_step == "awaiting_passenger":
            # Format: Name, Age, Gender (e.g. John Doe, 30, M)
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 3:
                return await telegram_dispatcher.send_message(
                    chat_id, 
                    "⚠️ <b>Invalid Format.</b>\n\nPlease enter passenger details as: <code>Name, Age, Gender</code>\nExample: <code>John Doe, 28, M</code>"
                )
            pax = {"name": parts[0], "age": parts[1], "gender": parts[2].upper()}
            passengers = session.context_data.get("passengers", [])
            passengers.append(pax)
            session_manager.update_session(self.db, str(chat_id), str(user_id), context={"passengers": passengers}, step="confirm_pax")
            return await telegram_dispatcher.send_message(
                chat_id,
                f"✅ Added {parts[0]}. Do you want to add another passenger or proceed to payment?",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "➕ Add Another", "callback_data": "add_pax"}],
                        [{"text": "💳 Proceed to Payment", "callback_data": "select_payment_method"}]
                    ]
                }
            )

    async def handle_callback(self, chat_id: int, user_id: str, data: str, callback_query_id: str):
        """Processes inline keyboard callbacks."""
        session = session_manager.get_or_create_session(self.db, str(chat_id), user_id)
        
        # Acknowledge callback
        await telegram_dispatcher._api_request("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": "Acknowledged"
        })
        
        parts = data.split(":")
        action = parts[0]
        payload = parts[1] if len(parts) > 1 else None

        if action == "select_train":
            return await self._process_train_selection(chat_id, user_id, payload if payload is not None else "", session)
        
        if action == "continue_last_search":
            source = session.context_data.get("source")
            dest = session.context_data.get("destination")
            if source and dest:
                return await self._perform_search(chat_id, source, dest)
            return await telegram_dispatcher.send_message(chat_id, "Sorry, I lost the context of your search. Where are you headed?")

        if action == "track":
            return await telegram_dispatcher.send_message(
                chat_id, 
                "📍 <b>Live Tracking Enabled.</b>\n\nPlease use the 'Share My Live Location' button in Telegram to keep us updated on your journey safety.",
                reply_markup={"keyboard": [[{"text": "📍 Share Live Location", "request_location": True}]], "one_time_keyboard": True, "resize_keyboard": True}
            )

        if action == "select_option":
            # Handle selection from the Unified Planner
            session_manager.update_session(self.db, str(chat_id), user_id, intent="booking", step="confirm", context={"selected_option": payload})
            return await telegram_dispatcher.send_message(
                chat_id,
                f"✅ <b>Option Selected!</b>\n\nI have locked this route for you. Proceed to book or view more details on the web.",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "🎫 Book Now", "callback_data": f"confirm_booking:{payload}"}],
                        [{"text": "👥 Share with Group", "callback_data": f"share_trip:{payload}"}],
                        [{"text": "❌ Cancel", "callback_data": "cancel_flow"}]
                    ]
                }
            )

        if action == "share_trip":
            # Store trip in session context so others can join
            # payload is the option_id or trip details
            trip_id = f"trip_{uuid.uuid4().hex[:8]}"
            # Create the trip record
            from database.models import GroupTrip, TripParticipant
            trip = GroupTrip(
                trip_id=trip_id,
                group_id=str(chat_id),
                origin=session.context_data.get("source", "Unknown"),
                destination=session.context_data.get("destination", "Unknown"),
                travel_date=datetime.utcnow() + timedelta(days=1),
                created_by=str(user_id) # Ensure user_id is str if required
            )
            self.db.add(trip)
            self.db.commit()
            
            session_manager.update_session(self.db, str(chat_id), str(user_id), context={"active_trip_id": trip.id})
            
            return await telegram_dispatcher.send_message(
                chat_id,
                f"📣 <b>Trip Created!</b> (Trip ID: <code>{trip_id}</code>)\n\nGroup members, click 'Join' to sync your booking status.",
                reply_markup={
                    "inline_keyboard": [[{"text": "🚀 Join Trip", "callback_data": f"join_trip:{trip_id}"}]]
                }
            )

        if action == "join_trip":
            # Payload is trip_id
            trip_id = payload
            from database.models import GroupTrip, TripParticipant
            trip = self.db.query(GroupTrip).filter(GroupTrip.trip_id == trip_id).first()
            if trip:
                participant = TripParticipant(trip_id=trip.id, user_id=str(user_id), telegram_id=str(user_id))
                self.db.add(participant)
                self.db.commit()
                return await telegram_dispatcher.send_message(chat_id, "✅ You've joined the trip! Updates for this journey will be pushed here.")
            return await telegram_dispatcher.send_message(chat_id, "Trip not found.")

        if action == "confirm_booking":
            session_manager.update_session(self.db, str(chat_id), user_id, intent="booking", step="awaiting_passenger")
            return await telegram_dispatcher.send_message(
                chat_id,
                "👤 <b>Passenger Details</b>\n\nPlease enter the details for the first passenger in the format:\n<code>Name, Age, Gender</code>\n\nExample: <code>John Doe, 30, M</code>"
            )

        if action == "add_pax":
            session_manager.update_session(self.db, str(chat_id), user_id, step="awaiting_passenger")
            return await telegram_dispatcher.send_message(chat_id, "Please enter the next passenger's details (<code>Name, Age, Gender</code>).")

        if action == "select_payment_method":
            return await telegram_dispatcher.send_message(
                chat_id,
                "💳 <b>Choose Payment Method</b>\n\nSelect 'Razorpay' for cards/netbanking or 'UPI' for instant direct transfer.",
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "🚀 Razorpay (Standard)", "callback_data": "pay:razorpay"}],
                        [{"text": "⚡ UPI (Direct)", "callback_data": "pay:upi"}]
                    ]
                }
            )

        if action.startswith("pay"):
            method = payload
            session_manager.update_session(self.db, str(chat_id), user_id, step="payment_initiated", context={"payment_method": method})
            
            account = self.db.query(TelegramAccount).filter(TelegramAccount.telegram_id == str(chat_id)).first()
            telegram_user_id = str(account.user_id) if account and account.user_id is not None else None
            
            if method == "razorpay":
                from services.telegram_intelligence_service import telegram_intelligence
                magic_link = await telegram_intelligence.generate_magic_link(self.db, telegram_user_id) if telegram_user_id else "https://safesafar.app/checkout"
                
                return await telegram_dispatcher.send_message(
                    chat_id,
                    "🔗 <b>Secure Checkout</b>\n\nClick the link below to complete your payment via Razorpay. Your booking will start automatically upon success.",
                    reply_markup={"inline_keyboard": [[{"text": "💳 Pay via Razorpay", "url": magic_link}]]}
                )
            else:
                return await self._process_upi_intent(chat_id, session)

        if action == "manual_confirm":
            # Link to confirm_manual endpoint logic
            return await telegram_dispatcher.send_message(
                chat_id,
                "⏳ <b>Verifying Payment...</b>\n\nOur system is checking for your transaction. We will notify you here the moment it is confirmed.",
                reply_markup=telegram_dispatcher.get_keyboard("default")
            )

        if action == "cancel_flow":
            session_manager.clear_session(self.db, str(chat_id))
            return await telegram_dispatcher.send_message(
                chat_id, 
                "Flow cancelled. I'm ready for your next request.",
                reply_markup=telegram_dispatcher.get_keyboard("default")
            )

        if action == "crowd_feedback":
            # Link to CrowdControlService
            level = payload.upper() if payload is not None else "UNKNOWN"
            logger.info(f"User {chat_id} reported crowd level: {level}")
            return await telegram_dispatcher.send_message(
                chat_id,
                f"🙏 <b>Thank you!</b> Your report of <b>{level}</b> crowding has been integrated into our live heatmap. Safe travels!",
                reply_markup=telegram_dispatcher.get_keyboard("journey")
            )

    async def _handle_sos_request(self, chat_id: int):
        """Production-grade SOS handler."""
        account = self.db.query(TelegramAccount).filter(TelegramAccount.telegram_id == str(chat_id)).first()
        user_id = account.user_id if account else None
        
        sos = SOSEvent(
            user_id=user_id,
            status="ACTIVE",
            priority="high",
            category="TELEGRAM_TRIGGER",
            extra=f"Triggered via Telegram Bot (Chat ID: {chat_id})"
        )
        self.db.add(sos)
        self.db.commit()
        
        await telegram_dispatcher.send_message(
            chat_id,
            "🚨 <b>SOS RECEIVED.</b>\n\nEmergency contacts and admins have been notified. Please stay calm and share your live location if possible.",
            reply_markup=telegram_dispatcher.get_keyboard("journey")
        )
        
        # Notify admin
        admin_chat = Config._get_env("TELEGRAM_CHAT_ID")
        if admin_chat:
            name = account.first_name if account else "Unknown User"
            await telegram_dispatcher.send_message(
                admin_chat,
                f"🚨 <b>URGENT: SOS Alert</b>\nUser: {name}\nChat ID: {chat_id}\nEvent ID: {sos.id}"
            )

    async def _process_new_intent(self, chat_id: int, user_id: str, text: str, intent_res: Optional[Dict[str, Any]] = None):
        """Initializes a new flow based on recognized intent."""
        intent = intent_res.get("intent") if intent_res else "unknown"
        entities = intent_res.get("entities", {}) if intent_res else {}

        if intent == "search":
            source = entities.get("source")
            destination = entities.get("destination")
            if source and destination:
                session_manager.update_session(
                    self.db, str(chat_id), user_id,
                    intent="search", 
                    step="results",
                    context={"source": source, "destination": destination}
                )
                return await self._perform_search(chat_id, source, destination)
            else:
                session_manager.update_session(self.db, str(chat_id), user_id, intent="search", step="awaiting_route")
                return await telegram_dispatcher.send_message(
                    chat_id, 
                    "Where are you traveling from and to? (e.g. Mumbai to Delhi)"
                )

        if intent == "pnr":
            pnr = entities.get("pnr")
            if pnr:
                return await self._show_pnr_status(chat_id, pnr)
            else:
                session_manager.update_session(self.db, str(chat_id), user_id, intent="pnr", step="awaiting_pnr")
                return await telegram_dispatcher.send_message(
                    chat_id, 
                    "Please provide the 10-digit PNR number."
                )
        
        if intent == "bookings":
            return await self._show_recent_bookings(chat_id)

        if intent == "ledger" or text.startswith("/transactions"):
            return await self._show_financial_ledger(chat_id)

        # Default fallback
        return await telegram_dispatcher.send_message(
            chat_id,
            "I'm your RouteMaster assistant. I can help you search trains, check PNR, or trigger SOS. What would you like to do?",
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    async def _handle_search_flow(self, chat_id: int, user_id: str, text: str, session):
        if session.current_step == "awaiting_route":
            # Re-parse route from text
            intent_res = await asyncio.to_thread(get_local_intent, text)
            entities = intent_res.get("entities", {}) if intent_res else {}
            source = entities.get("source")
            destination = entities.get("destination")
            
            if source and destination:
                session_manager.update_session(
                    self.db, str(chat_id), user_id,
                    step="results",
                    context={"source": source, "destination": destination}
                )
                return await self._perform_search(chat_id, source, destination)
            else:
                return await telegram_dispatcher.send_message(
                    chat_id,
                    "I still couldn't get the route. Please use the format 'Source to Destination'."
                )

    async def _handle_pnr_flow(self, chat_id: int, user_id: str, text: str, session):
        # Extract digits
        pnr = "".join(filter(str.isdigit, text))
        if len(pnr) == 10:
            session_manager.clear_session(self.db, str(chat_id))
            return await self._show_pnr_status(chat_id, pnr)
        else:
            return await telegram_dispatcher.send_message(
                chat_id,
                "That doesn't look like a 10-digit PNR. Please try again or type /cancel."
            )

    async def _perform_search(self, chat_id: int, source: str, destination: str, travel_date: Optional[date] = None):
        try:
            # If no date provided, default to tomorrow
            if not travel_date:
                travel_date = datetime.utcnow().date() + timedelta(days=1)
            
            request = TravelRequest(
                origin=source,
                destination=destination,
                travel_date=travel_date,
                allow_multi_modal=True,
                travel_preference=TravelPreference.BALANCED
            )
            
            # Using the advanced planner
            plan = await self.planner.create_travel_plan(request)
            options = plan.options if plan else []
            
            if not options:
                return await telegram_dispatcher.send_message(
                    chat_id, 
                    f"No travel options found for {source} to {destination}. Try a different date.",
                    reply_markup=telegram_dispatcher.get_keyboard("default")
                )
            
            msg = [f"<b>Travel Plan: {source} → {destination}</b>\n"]
            keyboard_buttons = []
            
            # Show top 3 varied options (Direct Train, Multi-modal, etc.)
            for opt in options[:3]:
                icon = "🚂" if opt.option_type == "direct" else "🚌" if opt.option_type == "multi_modal" else "⚡"
                msg.append(
                    f"{icon} <b>{opt.option_type.title()} Option</b>\n"
                    f"⌚ {opt.departure_time.strftime('%H:%M')} → {opt.arrival_time.strftime('%H:%M')}\n"
                    f"💰 ₹{opt.total_fare} | 🏆 Score: {int(opt.comfort_score * 100)}%\n"
                )
                
                label = f"Select {opt.option_type.title()}"
                frontend_url = Config._get_env("FRONTEND_URL", "https://safesafar.app")
                keyboard_buttons.append([
                    {"text": label, "callback_data": f"select_option:{opt.option_id}"},
                    {"text": "🌐 View on Web", "url": f"{frontend_url}/search?from={source}&to={destination}&option={opt.option_id}"}
                ])
            
            keyboard_buttons.append([{"text": "🔙 Back", "callback_data": "cancel_flow"}])
            
            return await telegram_dispatcher.send_message(
                chat_id,
                "\n".join(msg),
                reply_markup={"inline_keyboard": keyboard_buttons}
            )
        except Exception as e:
            logger.error(f"Unified search failed: {e}")
            return await telegram_dispatcher.send_message(chat_id, "Travel planner is currently busy. Please try later.")

    async def _process_train_selection(self, chat_id: int, user_id: str, train_no: str, session):
        if train_no is None:
            train_no = ""
        session_manager.update_session(
            self.db, str(chat_id), user_id,
            intent="booking", 
            step="confirm",
            context={"selected_train": train_no}
        )
        
        return await telegram_dispatcher.send_message(
            chat_id,
            f"🎯 <b>Confirmed:</b> Train {train_no}\n\nWould you like to proceed with the booking or view more details?",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🎫 Proceed to Book", "callback_data": f"confirm_booking:{train_no}"}],
                    [{"text": "📊 Detailed View", "url": f"https://safesafar.app/train/{train_no}"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel_flow"}]
                ]
            }
        )

    async def _process_booking_confirmation(self, chat_id: int, payload: str, session):
        """Displays the payment method selector after passenger entry."""
        return await telegram_dispatcher.send_message(
            chat_id,
            "💳 <b>Final Step: Secure Payment</b>\n\nChoose your preferred method to complete the booking.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🚀 Razorpay (Cards/Netbanking)", "callback_data": "pay:razorpay"}],
                    [{"text": "⚡ UPI (GPay/PhonePe/Paytm)", "callback_data": "pay:upi"}]
                ]
            }
        )

    async def _process_upi_intent(self, chat_id: int, session):
        import time
        """Generates a dynamic UPI link for the bot."""
        from services.merchant_vpa_service import merchant_vpa_service
        merchant = merchant_vpa_service.get_next_vpa()
        amount = session.context_data.get("amount", 49)
        
        from utils.payments import generate_upi_uri
        upi_link, _ = generate_upi_uri(
            merchant_vpa=merchant["vpa"],
            merchant_name=merchant["name"],
            amount=amount,
            transaction_note=f"Bot_{chat_id}_{int(time.time())}"
        )
        
        return await telegram_dispatcher.send_message(
            chat_id,
            f"📲 <b>Direct UPI Payment</b>\n\nMerchant: {merchant['name']}\nAmount: ₹{amount}\n\n"
            f"Please click the link below to open your UPI app, then click 'I have paid'.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "💸 Open UPI App", "url": upi_link}],
                    [{"text": "✅ I have paid", "callback_data": "manual_confirm"}]
                ]
            }
        )

    async def _show_pnr_status(self, chat_id: int, pnr: str):
        booking = self.db.query(Booking).filter(Booking.pnr_number == pnr).first()
        if not booking:
            return await telegram_dispatcher.send_message(
                chat_id, 
                f"I couldn't find a record for PNR {pnr}. Please check the number or view your dashboard.",
                reply_markup=telegram_dispatcher.get_keyboard("default")
            )
            
        status = booking.booking_status or "Unknown"
        date = booking.travel_date or "N/A"
        return await telegram_dispatcher.send_message(
            chat_id,
            f"📋 <b>PNR Status: {pnr}</b>\n\n🔹 Status: {status}\n📅 Date: {date}\n\nWe will notify you of any status changes!",
            reply_markup=telegram_dispatcher.get_keyboard("journey")
        )

    async def _show_recent_bookings(self, chat_id: int):
        account = self.db.query(TelegramAccount).filter(TelegramAccount.telegram_id == str(chat_id)).first()
        if not account:
            # Fallback to old User.telegram_id check
            user = self.db.query(User).filter(User.telegram_id == str(chat_id)).first()
            if not user:
                return await telegram_dispatcher.send_message(
                    chat_id,
                    "🔗 Your account is not linked yet. Use /start <code> to link your RouteMaster account.",
                    reply_markup=telegram_dispatcher.get_keyboard("help")
                )
            user_id = user.id
        else:
            user_id = account.user_id

        bookings = self.db.query(Booking).filter(Booking.user_id == user_id).order_by(Booking.created_at.desc()).limit(3).all()
        if not bookings:
            return await telegram_dispatcher.send_message(
                chat_id, 
                "You haven't made any bookings yet. Want to search for a train?",
                reply_markup=telegram_dispatcher.get_keyboard("default")
            )
            
        msg = ["<b>Your Recent Bookings:</b>\n"]
        for b in bookings:
            msg.append(f"PNR: <code>{b.pnr_number}</code>\nStatus: {b.booking_status}\nDate: {b.travel_date}\n")
            
        return await telegram_dispatcher.send_message(
            chat_id, 
            "\n".join(msg),
            reply_markup=telegram_dispatcher.get_keyboard("default")
        )

    async def _show_financial_ledger(self, chat_id: int):
        """Displays user's transaction history in Telegram."""
        account = self.db.query(TelegramAccount).filter(TelegramAccount.telegram_id == str(chat_id)).first()
        if not account:
            return await telegram_dispatcher.send_message(chat_id, "Please link your account first.")
            
        from services.ledger_service import LedgerService
        service = LedgerService(self.db)
        ledger = await service.get_user_ledger(account.user_id, limit=5)
        
        if not ledger:
            return await telegram_dispatcher.send_message(chat_id, "No transaction history found.")
            
        msg = [f"📊 <b>Your Financial Ledger</b> (Karma: {account.user.karma_score})\n"]
        for entry in ledger:
            icon = "💳" if entry["type"] == "PAYMENT" else "💸"
            status_icon = "✅" if entry["status"] in ("completed", "captured", "COMPLETED") else "⏳"
            msg.append(
                f"{icon} {entry['type']} - ₹{entry['amount']}\n"
                f"Status: {status_icon} {entry['status'].title()}\n"
                f"Date: {entry['created_at'].strftime('%d %b %H:%M')}\n"
            )
            
        return await telegram_dispatcher.send_message(chat_id, "\n".join(msg))
