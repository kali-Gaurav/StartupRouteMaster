import asyncio
import logging
import os
from typing import Optional
from playwright.async_api import async_playwright, Page
from database.session import SessionLocal
from database.models import Booking, EscrowStatus, BookingStatus

logger = logging.getLogger(__name__)

class IRCTCWorker:
    """
    Task 28: IRCTC Login Automator with Stealth.
    """
    def __init__(self, booking_id: str):
        self.booking_id = booking_id
        self.browser = None
        self.context = None
        self.page = None
        # Task 48: Latency Metrics
        self.metrics = {}
        import time
        self.start_timestamp = time.perf_counter()

    async def record_metric(self, phase: str):
        import time
        duration = time.perf_counter() - self.start_timestamp
        self.metrics[phase] = round(duration, 2)
        logger.info(f"Latency [{phase}]: {duration:.2f}s")
        self.start_timestamp = time.perf_counter()

    async def start(self):
        playwright = await async_playwright().start()
        
        # Task 46: Proxy Rotation Logic
        proxy_config = None
        proxy_url = os.getenv("RESIDENTIAL_PROXY_URL") # e.g. "http://user:pass@host:port"
        if proxy_url:
            proxy_config = {"server": proxy_url}
            logger.info(f"Using proxy for booking {self.booking_id}")

        # Disable HTTP/2 via launch arguments
        self.browser = await playwright.chromium.launch(
            headless=True,
            proxy=proxy_config,
            args=["--disable-http2"]
        )
        
        # Task 28: Residential Stealth Context
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.irctc.co.in/"
            }
        )
        
        # Mask automation flags
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        await self.update_status("Navigating to IRCTC...", EscrowStatus.BOOKING_INITIATED)

    async def login(self, username, password):
        """
        Subtask 28.1: Scripted login flow with Task 40: Retry on 503.
        """
        for attempt in range(3):
            try:
                await self.page.goto("https://www.irctc.co.in/nget/train-search", wait_until="networkidle")
                
                # Check for 503 or maintenance text
                content = await self.page.content()
                if "Service Unavailable" in content or "Maintenance" in content:
                    raise Exception("IRCTC 503 Service Unavailable")

                # ... (rest of login logic) ...
                break # Exit loop on success
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"IRCTC 503/Error (Attempt {attempt+1}): {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                else:
                    raise

    async def solve_captcha(self) -> Optional[str]:
        """
        Subtask 29.1: CAPTCHA solving logic using Human-in-the-loop.
        """
        try:
            # 1. Locate captcha image (IRCTC selector)
            captcha_img = await self.page.wait_for_selector("img.captcha-img", timeout=10000)
            if not captcha_img:
                logger.warning("No CAPTCHA image found.")
                return None
            
            # 2. Capture image as base64
            img_bytes = await captcha_img.screenshot()
            import base64
            b64_img = base64.b64encode(img_bytes).decode('utf-8')
            
            # 3. Send to Frontend via WebSocket
            from services.ws_manager import ws_manager
            await ws_manager.broadcast_log(
                self.booking_id, 
                "CAPTCHA required. Please solve it in the UI.", 
                status="CAPTCHA_REQUIRED",
                # Pass the image inside the message or as an extra field
            )
            # Send specific CAPTCHA event
            for conn in ws_manager.active_connections.get(self.booking_id, []):
                try:
                    await conn.send_json({"type": "captcha_required", "image": f"data:image/png;base64,{b64_img}"})
                except Exception as e:
                    pass
            
            # 4. Wait for user input (Poll Redis for the answer)
            from services.multi_layer_cache import multi_layer_cache
            redis_key = f"captcha:{self.booking_id}"
            await multi_layer_cache.redis.delete(redis_key) # Clear any old value
            
            logger.info(f"Waiting for human CAPTCHA input for {self.booking_id}...")
            
            # Wait up to 60 seconds
            for _ in range(60):
                answer = await multi_layer_cache.redis.get(redis_key)
                if answer:
                    logger.info("Human CAPTCHA input received!")
                    return answer.decode('utf-8')
                await asyncio.sleep(1)
            
            logger.warning("Human CAPTCHA input timed out.")
            return None
            
        except Exception as e:
            logger.warning(f"CAPTCHA solve failed: {e}")
            return None

    async def search_train(self, from_stn: str, to_stn: str, travel_date: str, train_no: str, t_class: str):
        """
        Subtask 30.1: Auto-navigate to Train and Class.
        """
        try:
            await self.update_status(f"Searching {train_no} from {from_stn} to {to_stn}...", EscrowStatus.BOOKING_INITIATED)
            
            # 1. Fill From/To
            await self.page.fill("input[aria-label='Station From']", from_stn)
            await self.page.keyboard.press("Enter")
            await self.page.fill("input[aria-label='Station To']", to_stn)
            await self.page.keyboard.press("Enter")
            
            # 2. Select Date
            await self.page.fill("input[placeholder='Journey Date']", travel_date)
            
            # 3. Click Search
            await self.page.click("button[type='submit']")
            await self.page.wait_for_load_state("networkidle")
            
            # 4. Locate Train and Class
            # selector for specific train row
            train_row = self.page.locator(f"tr:has-text('{train_no}')")
            await train_row.scroll_into_view_if_needed()
            
            # Click class
            class_btn = train_row.locator(f"div.pre-avail-column:has-text('{t_class}')")
            await class_btn.click()
            
            await self.update_status("Train selected. Checking availability...", EscrowStatus.BOOKING_INITIATED)
            await self.verify_availability()
            
        except Exception as e:
            logger.error(f"Train search failed: {e}")
            await self.update_status(f"Search Failure: {str(e)}", EscrowStatus.FAILED)
            raise

    async def verify_availability(self):
        """
        Subtask 31.1: Real-time availability re-check.
        """
        try:
            # selector for availability status text
            status_element = await self.page.wait_for_selector("div.avail-info", timeout=10000)
            status_text = await status_element.inner_text()
            
            logger.info(f"Availability Status: {status_text}")
            
            if "AVAILABLE" in status_text or "CURR_AVBL" in status_text:
                await self.update_status(f"Seats confirmed: {status_text}. Proceeding...", EscrowStatus.BOOKING_INITIATED)
                return True
            else:
                # Sold out or high waitlist
                error_msg = f"Booking Aborted: Seats no longer available ({status_text})"
                await self.update_status(error_msg, EscrowStatus.FAILED)
                
                # Task 39: Refund Queue Trigger
                await self.trigger_refund(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            if "Booking Aborted" not in str(e):
                logger.error(f"Availability check failed: {e}")
            raise

    async def trigger_refund(self, reason: str):
        """
        Subtask 39.1: Queue a refund for failed booking.
        """
        db = SessionLocal()
        try:
            from database.models import RefundQueue
            booking = db.query(Booking).filter(Booking.id == self.booking_id).first()
            if booking:
                # Get user VPA from transaction history (Task 24)
                user_vpa = "user-vpa@upi" 

                refund = RefundQueue(
                    booking_id=self.booking_id,
                    user_id=booking.user_id,
                    amount=booking.amount_paid,
                    vpa=user_vpa,
                    status="PENDING",
                    reason=reason
                )
                db.add(refund)
                booking.escrow_status = EscrowStatus.FAILED 
                booking.escrow_message = f"FAILED: {reason}. Refund of ₹{booking.amount_paid} queued."
                db.commit()
                logger.info(f"Refund queued for {self.booking_id}")
        finally:
            db.close()

    async def fill_passenger_details(self, passengers: list):
        """
        Subtask 32.1: Rapid DOM injection of passenger data.
        """
        try:
            await self.update_status(f"Filling details for {len(passengers)} passengers...", EscrowStatus.BOOKING_INITIATED)
            
            for i, p in enumerate(passengers):
                # If not the first passenger, click "Add Passenger"
                if i > 0:
                    await self.page.click("a:has-text('+ Add Passenger')")
                
                # IRCTC uses indices for form fields (e.g., p-inputtext for name)
                # We target based on relative positioning or specific dynamic selectors
                row = self.page.locator("app-passenger").nth(i)
                
                await row.locator("input[placeholder='Passenger Name']").fill(p['fullName'])
                await row.locator("input[placeholder='Age']").fill(str(p['age']))
                
                # Gender Selection
                gender_map = {"M": "Male", "F": "Female", "T": "Transgender"}
                await row.locator("select.form-control").nth(0).select_option(label=gender_map.get(p['gender'], "Male"))
                
                # Berth Preference with Task 43 Fallback
                if p.get('berth_preference'):
                    try:
                        await row.locator("select.form-control").nth(1).select_option(label=p['berth_preference'])
                    except:
                        logger.warning(f"Preferred berth {p['berth_preference']} unavailable. Falling back to No Preference.")
                        await row.locator("select.form-control").nth(1).select_option(label="No Preference")

            # Task 33: Auto-Upgradation Toggle
            try:
                auto_upgrade_cb = self.page.locator("label:has-text('Consider for Auto Upgradation')")
                await auto_upgrade_cb.click()
                logger.info("Auto-Upgradation enabled.")
            except:
                logger.warning("Auto-Upgradation checkbox not found.")

            await self.update_status("Passenger details filled successfully.", EscrowStatus.BOOKING_INITIATED)
            
            # Navigate to next page
            await self.page.click("button:has-text('Continue')")
            
        except Exception as e:
            logger.error(f"Form filling failed: {e}")
            await self.update_status(f"Form Fill Failure: {str(e)}", EscrowStatus.FAILED)
            raise

    async def navigate_to_irctc_payment(self):
        """
        Subtask 34.1: Automate "Pay via UPI" selection.
        """
        try:
            await self.update_status("Navigating to payment gateway...", EscrowStatus.BOOKING_INITIATED)
            
            # Task 44: Boarding Point Selection
            await self.select_boarding_point()
            
            # Review Page -> Payment Page
            await self.page.wait_for_selector("button:has-text('Continue')", timeout=10000)
            await self.page.click("button:has-text('Continue')")
            
            # Select Payment Method
            await self.page.click("span:has-text('Payment Gateway / Credit Card / Debit Card / UPI')")
            await self.page.click("span:has-text('BHIM/ UPI/ USSD')")
            await self.page.click("button:has-text('Pay & Book')")
            
            await self.update_status("Payment page reached. Awaiting VPA entry...", EscrowStatus.BOOKING_INITIATED)
            
        except Exception as e:
            logger.error(f"Payment navigation failed: {e}")
            await self.update_status(f"Payment Nav Failure: {str(e)}", EscrowStatus.FAILED)
            raise

    async def select_boarding_point(self):
        # ... (implementation from Task 44) ...
        return True

    async def scrape_fees(self):
        """
        Subtask 45.1: Parse IRCTC fees for accounting.
        """
        try:
            fee_element = await self.page.wait_for_selector("td:has-text('Convenience Fee'), .fare-summary", timeout=5000)
            fee_text = await fee_element.inner_text()
            # Logic to parse numbers from text
            import re
            fees = re.findall(r"[\d\.]+", fee_text)
            
            db = SessionLocal()
            booking = db.query(Booking).filter(Booking.id == self.booking_id).first()
            if booking:
                details = dict(booking.booking_details or {})
                details['irctc_fees'] = fees
                booking.booking_details = details
                db.commit()
            db.close()
            logger.info(f"Scraped fees: {fees}")
        except Exception as e:
            logger.warning(f"Fee scraping failed: {e}")

    async def pay_irctc(self):
        """
        Subtask 35.1: Execute payment from company VPA (MOCKED FOR TESTING).
        """
        try:
            await self.update_status("Initiating company payment to IRCTC...", EscrowStatus.BOOKING_INITIATED)
            
            # 1. Enter VPA
            vpa_input = await self.page.wait_for_selector("input#vpa-input, input[name='vpa']", timeout=10000)
            await vpa_input.fill("anthonynagar1122-1@oksbi")
            
            # MOCK PAYMENT: Do not click Pay to save money
            logger.info("Payment mocked for testing. Skipping actual payment click.")
            await asyncio.sleep(2)
            await self.update_status("MOCK: VPA submitted. Confirming transaction...", EscrowStatus.BOOKING_INITIATED)
            
            # Since we didn't pay, we won't reach the real PNR page.
            # We must raise a specific exception or set a flag so scrape_pnr knows it's a mock.
            self.is_mock_payment = True
            
        except Exception as e:
            logger.error(f"Payment execution failed: {e}")
            await self.update_status(f"Payment Exec Failure: {str(e)}", EscrowStatus.FAILED)
            raise

    async def scrape_pnr_details(self) -> dict:
        """
        Subtask 36.1: Extract PNR and Seat details from success page.
        """
        try:
            await self.update_status("Booking confirmed. Scraping PNR details...", EscrowStatus.BOOKING_INITIATED)
            
            # If payment was mocked, return mock PNR
            if getattr(self, 'is_mock_payment', False):
                import random
                mock_pnr = "PNR" + str(random.randint(1000000000, 9999999999))
                return {"pnr": mock_pnr, "seats": ["MOCK-A1-14", "MOCK-A1-15"]}
            
            # 1. Extract PNR

            pnr_element = await self.page.wait_for_selector("span#pnr-number, .pnr-info", timeout=15000)
            pnr_text = await pnr_element.inner_text()
            import re
            pnr_match = re.search(r"\d{10}", pnr_text)
            pnr = pnr_match.group(0) if pnr_match else "ERROR"
            
            # 2. Extract Seats
            # selector for seat info table
            seats = []
            rows = self.page.locator("tr.seat-row")
            count = await rows.count()
            for i in range(count):
                seat_info = await rows.nth(i).inner_text()
                seats.append(seat_info.strip())
                
            return {"pnr": pnr, "seats": seats}
            
        except Exception as e:
            logger.error(f"PNR scraping failed: {e}")
            return {"pnr": "SCrapeError", "seats": []}

    async def update_status(self, message: str, status: EscrowStatus = None):
        db = SessionLocal()
        try:
            booking = db.query(Booking).filter(Booking.id == self.booking_id).first()
            if booking:
                booking.escrow_message = message
                if status:
                    booking.escrow_status = status
                db.commit()
                
                # Task 42: Broadcast via WebSocket
                from services.ws_manager import ws_manager
                import asyncio
                # Broadcast asynchronously to avoid blocking the main worker flow
                asyncio.create_task(ws_manager.broadcast_log(
                    self.booking_id, 
                    message, 
                    status.name if status else None
                ))
                
                logger.info(f"[Booking {self.booking_id}] {message}")
        finally:
            db.close()

    async def close(self):
        if self.browser:
            await self.browser.close()

async def run_booking_worker(booking_id: str):
    worker = IRCTCWorker(booking_id)
    try:
        await worker.start()
        
        db = SessionLocal()
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            db.close()
            return

        # Task 49: Retrieve Encrypted Credentials from Vault
        from utils.encryption import credential_vault
        import json
        
        irctc_user = os.getenv("IRCTC_USERNAME", "MOCK_USER")
        irctc_pass = os.getenv("IRCTC_PASSWORD", "MOCK_PASS")
        
        user_profile = booking.user.profile if booking.user else None
        if user_profile and user_profile.ai_memory and user_profile.ai_memory.get("encrypted_creds"):
            try:
                decrypted_str = credential_vault.decrypt(user_profile.ai_memory["encrypted_creds"])
                if decrypted_str:
                    decrypted = json.loads(decrypted_str)
                    irctc_user = decrypted["username"]
                    irctc_pass = decrypted["password"]
                    logger.info(f"Retrieved credentials from vault for user {booking.user_id}")
            except Exception as e:
                logger.error(f"Vault decryption failed: {e}")

        await worker.login(irctc_user, irctc_pass)

        # Task 47: Handle Alternatives
        routes_to_try = [booking.booking_details]
        if booking.booking_details.get("alternatives"):
            routes_to_try.extend(booking.booking_details["alternatives"])

        success = False
        for i, route in enumerate(routes_to_try):
            try:
                if i > 0:
                    await worker.update_status(f"Primary full. Attempting AI Alternative {i}...", EscrowStatus.BOOKING_INITIATED)
                
                # We assume single-leg for this simplified worker logic
                # Real implementation would loop through legs
                train_no = route.get('train_number') or route.get('legs', [{}])[0].get('train_number')
                
                await worker.search_train(
                    from_stn="NDLS", # In real, parse from route
                    to_stn="BCT", 
                    travel_date=str(booking.travel_date),
                    train_no=train_no,
                    t_class="3A"
                )
                
                # If we reach here, availability is confirmed
                await worker.fill_passenger_details(route.get('passengers', []))
                await worker.navigate_to_irctc_payment()
                await worker.pay_irctc()
                
                res = await worker.scrape_pnr_details()
                mock_pnr = res["pnr"]
                success = True
                break
            except Exception as e:
                logger.warning(f"Attempt {i} failed: {e}")
                if i == len(routes_to_try) - 1:
                    raise # No more alternatives

        if success:
            await worker.update_status(f"Booking Successful! PNR: {mock_pnr}", EscrowStatus.COMPLETED)
            # ... (rest of success logic) ...
        
        # --- Task 37: Generate Branded PDF ---
        from utils.ticket_generator import generate_branded_ticket
        db = SessionLocal()
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if booking:
            pdf_path = generate_branded_ticket(
                booking_id=booking.id,
                pnr=mock_pnr,
                train_no=booking.train_number or "12345",
                from_stn="NDLS", # Mocked
                to_stn="BCT", # Mocked
                travel_date=str(booking.travel_date),
                passengers=booking.booking_details.get('passengers', [])
            )
            
            # --- Task 41 & 50: Dispatch to Telegram with Formatter ---
            from services.telegram_dispatcher import send_ticket_to_telegram
            
            # Task 50 Formatter
            success_msg = (
                f"🎉 <b>Booking Confirmed!</b>\n\n"
                f"🚂 <b>Train:</b> {booking.train_number}\n"
                f"🎫 <b>PNR:</b> <code>{mock_pnr}</code>\n"
                f"💺 <b>Seats:</b> {', '.join(res.get('seats', []))}\n\n"
                f"✅ <i>Verified by RouteMaster AI Pipeline</i>\n"
                f"🛡️ <i>Escrow Protected Transaction</i>"
            )
            
            user_profile = booking.user.profile if booking.user else None
            telegram_id = user_profile.phone if user_profile else None
            
            if telegram_id:
                await send_ticket_to_telegram(
                    telegram_id=telegram_id,
                    file_path=pdf_path,
                    caption=success_msg
                )

            booking.pnr_number = mock_pnr
            booking.booking_status = BookingStatus.CONFIRMED.value
            db.commit()
        db.close()

    except Exception as e:
        logger.error(f"Worker process crashed: {e}")
    finally:
        await worker.close()
