"""
Keyboard Definitions
====================
UI components for Telegram bot interactions.
"""

from typing import Dict, Any, List
from .config import feature_config


class KeyboardBuilder:
    """Builds Telegram keyboards and inline keyboards."""
    
    # Main menu keyboard
    @staticmethod
    def main_menu() -> Dict[str, Any]:
        """Main menu with primary actions."""
        return {
            "keyboard": [
                [
                    {"text": "🔍 Search Trains", "callback_data": "search_trains"},
                    {"text": "🎫 Book Ticket"}
                ],
                [
                    {"text": "📜 My Bookings", "text": "💳 My Wallet"},
                ],
                [
                    {"text": "🚨 SOS Emergency", "text": "❓ Help"}
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }
    
    @staticmethod
    def search_menu() -> Dict[str, Any]:
        """Search-specific keyboard."""
        return {
            "keyboard": [
                [
                    {"text": "🔍 Check Availability"},
                    {"text": "🛤️ Alternative Routes"}
                ],
                [
                    {"text": "📊 Dashboard"},
                    {"text": "🎫 Book Now"}
                ],
                [
                    {"text": "🔙 Back to Menu"}
                ]
            ],
            "resize_keyboard": True
        }
    
    @staticmethod
    def booking_menu() -> Dict[str, Any]:
        """Booking flow keyboard."""
        return {
            "keyboard": [
                [
                    {"text": "✅ Confirm Booking"},
                    {"text": "❌ Cancel"}
                ],
                [
                    {"text": "🔙 Go Back"}
                ]
            ],
            "resize_keyboard": True
        }
    
    @staticmethod
    def profile_menu() -> Dict[str, Any]:
        """Profile management keyboard."""
        return {
            "keyboard": [
                [
                    {"text": "👤 Edit Profile"},
                    {"text": "📱 Update Phone"}
                ],
                [
                    {"text": "🔒 Change Password"},
                    {"text": "📧 Update Email"}
                ],
                [
                    {"text": "🔙 Back to Menu"}
                ]
            ],
            "resize_keyboard": True
        }
    
    @staticmethod
    def yes_no() -> Dict[str, Any]:
        """Yes/No confirmation keyboard."""
        return {
            "keyboard": [
                [
                    {"text": "✅ Yes"},
                    {"text": "❌ No"}
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    @staticmethod
    def back_only() -> Dict[str, Any]:
        """Back button only."""
        return {
            "keyboard": [
                [
                    {"text": "🔙 Back"}
                ]
            ],
            "resize_keyboard": True
        }
    
    @staticmethod
    def empty() -> Dict[str, Any]:
        """Remove custom keyboard."""
        return {"remove_keyboard": True}
    
    # Inline keyboards
    @staticmethod
    def train_search_results(
        train_no: str,
        train_name: str,
        booking_id: str
    ) -> List[List[Dict[str, str]]]:
        """Inline keyboard for train search results."""
        return [
            [
                {"text": "📊 Availability", "callback_data": f"avail_{train_no}"},
                {"text": "🎫 Book Now", "callback_data": f"book_{train_no}_{booking_id}"}
            ],
            [
                {"text": "⏰ Schedule", "callback_data": f"schedule_{train_no}"},
                {"text": "🚉 Stations", "callback_data": f"stations_{train_no}"}
            ]
        ]
    
    @staticmethod
    def booking_confirmation(booking_id: str) -> List[List[Dict[str, str]]]:
        """Inline keyboard for booking confirmation."""
        return [
            [
                {"text": "✅ Confirm & Pay", "callback_data": f"confirm_{booking_id}"},
                {"text": "❌ Cancel", "callback_data": f"cancel_{booking_id}"}
            ],
            [
                {"text": "👥 Add Passengers", "callback_data": f"add_passengers_{booking_id}"},
                {"text": "🎫 Change Class", "callback_data": f"change_class_{booking_id}"}
            ]
        ]
    
    @staticmethod
    def booking_details(booking_id: str, pnr: str) -> List[List[Dict[str, str]]]:
        """Inline keyboard for booking details."""
        return [
            [
                {"text": "📥 Download PDF", "callback_data": f"pdf_{booking_id}"},
                {"text": "🔍 Check PNR", "callback_data": f"pnr_{pnr}"}
            ],
            [
                {"text": "❌ Cancel Ticket", "callback_data": f"cancel_ticket_{booking_id}"},
                {"text": "🔄 Reschedule", "callback_data": f"reschedule_{booking_id}"}
            ],
            [
                {"text": "📤 Share", "callback_data": f"share_{booking_id}"}
            ]
        ]
    
    @staticmethod
    def pnr_status(pnr: str) -> List[List[Dict[str, str]]]:
        """Inline keyboard for PNR status."""
        return [
            [
                {"text": "🔄 Refresh", "callback_data": f"refresh_pnr_{pnr}"},
                {"text": "📜 Boarding Slip", "callback_data": f"slip_{pnr}"}
            ],
            [
                {"text": "🚉 Station Map", "callback_data": f"station_map_{pnr}"},
                {"text": "⏰ Alerts", "callback_data": f"alerts_{pnr}"}
            ]
        ]
    
    @staticmethod
    def sos_emergency() -> List[List[Dict[str, str]]]:
        """SOS emergency keyboard."""
        return [
            [
                {"text": "🚨 Send SOS", "callback_data": "sos_send"},
                {"text": "📍 Share Location", "callback_data": "sos_location"}
            ],
            [
                {"text": "📞 Call Helpline", "callback_data": "sos_helpline"},
                {"text": "🆘 Get Help", "callback_data": "sos_help"}
            ],
            [
                {"text": "❌ Cancel", "callback_data": "sos_cancel"}
            ]
        ]
    
    @staticmethod
    def dashboard() -> List[List[Dict[str, str]]]:
        """Dashboard inline keyboard."""
        return [
            [
                {"text": "📊 Analytics", "callback_data": "dashboard_analytics"},
                {"text": "💳 Transactions", "callback_data": "dashboard_transactions"}
            ],
            [
                {"text": "🎫 Active Bookings", "callback_data": "dashboard_bookings"},
                {"text": "⚙️ Settings", "callback_data": "dashboard_settings"}
            ]
        ]
    
    @staticmethod
    def help_menu() -> List[List[Dict[str, str]]]:
        """Help menu inline keyboard."""
        return [
            [
                {"text": "🔍 How to Search", "callback_data": "help_search"},
                {"text": "🎫 How to Book", "callback_data": "help_booking"}
            ],
            [
                {"text": "💳 Payments", "callback_data": "help_payments"},
                {"text": "❓ FAQ", "callback_data": "help_faq"}
            ],
            [
                {"text": "📞 Contact Support", "callback_data": "help_support"}
            ]
        ]
    
    @staticmethod
    def class_selection() -> List[List[Dict[str, str]]]:
        """Train class selection."""
        return [
            [
                {"text": "🛋️ AC First Class (1A)", "callback_data": "class_1A"},
                {"text": "🛋️ AC 2-Tier (2A)", "callback_data": "class_2A"}
            ],
            [
                {"text": "🛋️ AC 3-Tier (3A)", "callback_data": "class_3A"},
                {"text": "💺 AC Chair Car (CC)", "callback_data": "class_CC"}
            ],
            [
                {"text": "💺 Sleeper (SL)", "callback_data": "class_SL"},
                {"text": "💺 Second Sitting (2S)", "callback_data": "class_2S"}
            ],
            [
                {"text": "🔙 Back", "callback_data": "class_back"}
            ]
        ]
    
    @staticmethod
    def quota_selection() -> List[List[Dict[str, str]]]:
        """Booking quota selection."""
        return [
            [
                {"text": "General", "callback_data": "quota_general"},
                {"text": "Tatkal", "callback_data": "quota_tatkal"}
            ],
            [
                {"text": "Ladies", "callback_data": "quota_ladies"},
                {"text": "Senior Citizen", "callback_data": "quota_senior"}
            ],
            [
                {"text": "Divyang", "callback_data": "quota_divyang"},
                {"text": "Premium Tatkal", "callback_data": "quota_premium_tatkal"}
            ]
        ]


# Global instance
keyboard_builder = KeyboardBuilder()