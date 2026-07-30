"""
Tests for Telegram Booking Handler
==================================
Comprehensive tests for the production-ready booking handler.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

import sys
from pathlib import Path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from telegram_bot.handlers.booking_handler import (
    BookingHandler, BookingStep, BookingData
)
from telegram_bot.schemas import TelegramMessage, UserContext, BotResponse


class TestBookingHandler:
    """Test cases for BookingHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create booking handler instance."""
        return BookingHandler()
    
    @pytest.fixture
    def mock_context(self):
        """Create mock user context."""
        return UserContext(
            user_id="test_user_123",
            chat_id=123456789,
            state="idle",
            data={},
            language="en"
        )
    
    @pytest.fixture
    def sample_train_data(self):
        """Sample train data from search."""
        return {
            "train_no": "12951",
            "train_name": "Mumbai Rajdhani",
            "departure": "16:55",
            "arrival": "08:35",
            "duration": "15h 40m",
            "date": "2025-06-15",
            "from": "NDLS",
            "to": "BCT",
            "safety_score": 95
        }
    
    def test_class_mapping(self, handler):
        """Test class code mapping."""
        assert handler.CLASS_MAP["class_1A"] == ("AC First Class (1A)", "1A")
        assert handler.CLASS_MAP["class_SL"] == ("Sleeper (SL)", "SL")
        assert handler.CLASS_MAP["class_3A"] == ("AC 3-Tier (3A)", "3A")
    
    def test_quota_mapping(self, handler):
        """Test quota code mapping."""
        assert handler.QUOTA_MAP["quota_general"] == ("General", "GN")
        assert handler.QUOTA_MAP["quota_tatkal"] == ("Tatkal", "TQ")
        assert handler.QUOTA_MAP["quota_senior"] == ("Senior Citizen", "SS")
    
    def test_method_mapping(self, handler):
        """Test method code mapping."""
        assert handler.METHOD_MAP["method_irctc"] == "IRCTC Direct"
        assert handler.METHOD_MAP["method_agent"] == "Verified Agent"
    
    def test_base_fares(self, handler):
        """Test base fare values."""
        assert handler.BASE_FARES["1A"] == 3500
        assert handler.BASE_FARES["2A"] == 2500
        assert handler.BASE_FARES["3A"] == 1500
        assert handler.BASE_FARES["SL"] == 500
        assert handler.BASE_FARES["2S"] == 300
    
    def test_parse_passengers_valid(self, handler):
        """Test parsing valid passenger details."""
        text = """John Doe, 25, M
Jane Smith, 22, F
Bob Wilson, 30, M"""
        
        passengers = handler._parse_passengers(text)
        
        assert len(passengers) == 3
        assert passengers[0]["name"] == "John Doe"
        assert passengers[0]["age"] == 25
        assert passengers[0]["gender"] == "M"
        assert passengers[1]["name"] == "Jane Smith"
        assert passengers[1]["gender"] == "F"
    
    def test_parse_passengers_with_preference(self, handler):
        """Test parsing passengers with berth preference."""
        text = "John Doe, 25, M, lower"
        
        passengers = handler._parse_passengers(text)
        
        assert len(passengers) == 1
        assert passengers[0]["berth_preference"] == "lower"
    
    def test_parse_passengers_invalid(self, handler):
        """Test parsing invalid passenger details."""
        text = """Invalid Line
Another Invalid
John Doe, M, F"""
        
        passengers = handler._parse_passengers(text)
        
        assert len(passengers) == 0
    
    def test_parse_passengers_empty(self, handler):
        """Test parsing empty passenger details."""
        passengers = handler._parse_passengers("")
        assert passengers == []
        
        passengers = handler._parse_passengers("   ")
        assert passengers == []
    
    def test_calculate_fare_standard(self, handler):
        """Test fare calculation for standard booking."""
        booking_data = {
            "class_code": "SL",
            "passenger_count": 2,
            "tatkal_charge": 0
        }
        
        fare = handler._calculate_fare(booking_data)
        
        # 500 × 2 = 1000
        assert fare == 1000
    
    def test_calculate_fare_with_tatkal(self, handler):
        """Test fare calculation with Tatkal charges."""
        booking_data = {
            "class_code": "3A",
            "passenger_count": 1,
            "tatkal_charge": 300
        }
        
        fare = handler._calculate_fare(booking_data)
        
        # 1500 + 300 = 1800
        assert fare == 1800
    
    def test_calculate_fare_ac_first(self, handler):
        """Test fare calculation for AC First Class."""
        booking_data = {
            "class_code": "1A",
            "passenger_count": 3,
            "tatkal_charge": 0
        }
        
        fare = handler._calculate_fare(booking_data)
        
        # 3500 × 3 = 10500
        assert fare == 10500
    
    def test_generate_pnr(self, handler):
        """Test PNR generation."""
        pnr1 = handler._generate_pnr()
        pnr2 = handler._generate_pnr()
        
        # Should be 10 characters
        assert len(pnr1) == 10
        # Should be alphanumeric
        assert pnr1.isalnum()
        # Should be uppercase
        assert pnr1.isupper()
        # Should be unique
        assert pnr1 != pnr2
    
    def test_generate_irctc_url(self, handler):
        """Test IRCTC URL generation."""
        train_data = {"train_no": "12951"}
        booking_data = {"class_code": "SL", "quota_code": "GN"}
        
        url = handler._generate_irctc_url(train_data, booking_data)
        
        assert "trainNo=12951" in url
        assert "class=SL" in url
        assert "quota=GN" in url
        assert url.startswith("https://www.irctc.co.in")
    
    def test_create_booking_summary(self, handler, sample_train_data):
        """Test booking summary creation."""
        booking_data = {
            "class_type": "Sleeper (SL)",
            "class_code": "SL",
            "quota": "General",
            "method": "Verified Agent",
            "passengers": [
                {"name": "John Doe", "age": 25, "gender": "M"},
                {"name": "Jane Smith", "age": 22, "gender": "F"}
            ],
            "base_fare": 500,
            "passenger_count": 2,
            "total_fare": 1000
        }
        
        summary = handler._create_booking_summary(sample_train_data, booking_data)
        
        assert "12951" in summary
        assert "Mumbai Rajdhani" in summary
        assert "Sleeper (SL)" in summary
        assert "General" in summary
        assert "John Doe" in summary
        assert "Jane Smith" in summary
        assert "₹1000" in summary
    
    def test_format_passengers(self, handler):
        """Test passenger formatting."""
        passengers = [
            {"name": "John Doe", "age": 25, "gender": "M"},
            {"name": "Jane Smith", "age": 22, "gender": "F"}
        ]
        
        formatted = handler._format_passengers(passengers)
        
        assert "1. John Doe (25 yrs, M)" in formatted
        assert "2. Jane Smith (22 yrs, F)" in formatted
    
    def test_format_passengers_empty(self, handler):
        """Test formatting empty passenger list."""
        formatted = handler._format_passengers([])
        assert formatted == "No passengers"
    
    @pytest.mark.asyncio
    async def test_handle_booking_start(self, handler, mock_context):
        """Test booking start handler."""
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="/book",
            date=datetime.now()
        )
        
        result = await handler._handle_booking_start(
            123456789, "/book", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.NEEDS_INPUT
        assert "Start Booking" in result.response.text
        assert result.next_state == BookingStep.START.value
    
    @pytest.mark.asyncio
    async def test_handle_train_selection(self, handler, mock_context, sample_train_data):
        """Test train selection handler."""
        mock_context.data["selected_train"] = sample_train_data
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="Select Train",
            date=datetime.now()
        )
        
        result = await handler._handle_train_selection(
            123456789, "select_train", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Train Selected" in result.response.text
        assert "12951" in result.response.text
        assert result.next_state == BookingStep.SELECT_CLASS.value
    
    @pytest.mark.asyncio
    async def test_handle_class_selection(self, handler, mock_context):
        """Test class selection handler."""
        mock_context.data["booking_data"] = {}
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="class_SL",
            date=datetime.now()
        )
        
        result = await handler._handle_class_selection(
            123456789, "class_SL", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Class Selected" in result.response.text
        assert "Sleeper (SL)" in result.response.text
        assert result.next_state == BookingStep.SELECT_QUOTA.value
        
        # Verify booking data was updated
        booking_data = result.data["booking_data"]
        assert booking_data["class_type"] == "Sleeper (SL)"
        assert booking_data["class_code"] == "SL"
    
    @pytest.mark.asyncio
    async def test_handle_quota_selection(self, handler, mock_context):
        """Test quota selection handler."""
        mock_context.data["booking_data"] = {
            "class_type": "Sleeper (SL)",
            "class_code": "SL"
        }
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="quota_general",
            date=datetime.now()
        )
        
        result = await handler._handle_quota_selection(
            123456789, "quota_general", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Quota Selected" in result.response.text
        assert "General" in result.response.text
        assert result.next_state == BookingStep.SELECT_METHOD.value
        
        # Verify booking data was updated
        booking_data = result.data["booking_data"]
        assert booking_data["quota"] == "General"
        assert booking_data["quota_code"] == "GN"
    
    @pytest.mark.asyncio
    async def test_handle_quota_selection_tatkal(self, handler, mock_context):
        """Test quota selection with Tatkal."""
        mock_context.data["booking_data"] = {
            "class_type": "AC 3-Tier (3A)",
            "class_code": "3A"
        }
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="quota_tatkal",
            date=datetime.now()
        )
        
        result = await handler._handle_quota_selection(
            123456789, "quota_tatkal", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Tatkal" in result.response.text
        assert "₹300" in result.response.text  # Tatkal charge for 3A
        
        booking_data = result.data["booking_data"]
        assert booking_data["tatkal_charge"] == 200
    
    @pytest.mark.asyncio
    async def test_handle_passenger_entry_valid(self, handler, mock_context, sample_train_data):
        """Test valid passenger entry."""
        mock_context.data["booking_data"] = {
            "class_type": "Sleeper (SL)",
            "class_code": "SL",
            "quota": "General",
            "quota_code": "GN",
            "base_fare": 500
        }
        mock_context.data["selected_train"] = sample_train_data
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="John Doe, 25, M\nJane Smith, 22, F",
            date=datetime.now()
        )
        
        result = await handler._handle_passenger_entry(
            123456789, "John Doe, 25, M\nJane Smith, 22, F", 
            mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Passengers Added" in result.response.text
        assert result.next_state == BookingStep.REVIEW_BOOKING.value
        
        booking_data = result.data["booking_data"]
        assert len(booking_data["passengers"]) == 2
        assert booking_data["passenger_count"] == 2
        assert booking_data["total_fare"] == 1000  # 500 × 2
    
    @pytest.mark.asyncio
    async def test_handle_passenger_entry_invalid(self, handler, mock_context):
        """Test invalid passenger entry."""
        mock_context.data["booking_data"] = {}
        mock_context.data["selected_train"] = {}
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="Invalid input",
            date=datetime.now()
        )
        
        result = await handler._handle_passenger_entry(
            123456789, "Invalid input", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.NEEDS_INPUT
        assert "Invalid Format" in result.response.text
    
    @pytest.mark.asyncio
    async def test_handle_passenger_entry_too_many(self, handler, mock_context):
        """Test passenger entry with too many passengers."""
        mock_context.data["booking_data"] = {}
        mock_context.data["selected_train"] = {}
        
        # Create text with more than max passengers
        too_many = "\n".join([
            f"Passenger {i}, 25, M" for i in range(10)
        ])
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text=too_many,
            date=datetime.now()
        )
        
        result = await handler._handle_passenger_entry(
            123456789, too_many, mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.NEEDS_INPUT
        assert "Too Many Passengers" in result.response.text
    
    @pytest.mark.asyncio
    async def test_handle_review_confirm(self, handler, mock_context):
        """Test review handler with confirm."""
        mock_context.data["booking_data"] = {
            "total_fare": 1000,
            "pnr_number": "ABC123XYZ"
        }
        mock_context.data["selected_train"] = {
            "train_no": "12951",
            "train_name": "Rajdhani"
        }
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="confirm",
            date=datetime.now()
        )
        
        result = await handler._handle_review(
            123456789, "confirm", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert result.next_state == BookingStep.PAYMENT.value
    
    @pytest.mark.asyncio
    async def test_handle_review_cancel(self, handler, mock_context):
        """Test review handler with cancel."""
        mock_context.data["booking_data"] = {}
        mock_context.data["selected_train"] = {}
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="cancel",
            date=datetime.now()
        )
        
        result = await handler._handle_review(
            123456789, "cancel", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Booking Cancelled" in result.response.text
        assert result.next_state == BookingStep.START.value
    
    @pytest.mark.asyncio
    async def test_handle_payment(self, handler, mock_context, sample_train_data):
        """Test payment handler."""
        mock_context.data["booking_data"] = {
            "class_type": "Sleeper (SL)",
            "class_code": "SL",
            "quota": "General",
            "quota_code": "GN",
            "passenger_count": 2,
            "base_fare": 500,
            "tatkal_charge": 0
        }
        mock_context.data["selected_train"] = sample_train_data
        
        message = TelegramMessage(
            message_id=1,
            chat=Mock(id=123456789),
            text="Proceed to payment",
            date=datetime.now()
        )
        
        result = await handler._handle_payment(
            123456789, "Proceed to payment", mock_context, {}, message
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Payment Required" in result.response.text
        assert "PNR:" in result.response.text
        assert "Total Amount: ₹1000" in result.response.text
        assert result.next_state == BookingStep.PAYMENT.value
        
        # Verify booking data was updated
        booking_data = result.data["booking_data"]
        assert "booking_id" in booking_data
        assert "pnr_number" in booking_data
        assert booking_data["total_fare"] == 1000
    
    @pytest.mark.asyncio
    async def test_handle_callback_book(self, handler, mock_context):
        """Test callback handler for book action."""
        result = await handler.handle_callback(
            "book_12951",
            123456789,
            mock_context
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Train Selected for Booking" in result.response.text
        assert result.next_state == BookingStep.SELECT_CLASS.value
        assert result.data["selected_train"]["train_no"] == "12951"
    
    @pytest.mark.asyncio
    async def test_handle_callback_pay(self, handler, mock_context):
        """Test callback handler for pay action."""
        mock_context.data["booking_data"] = {
            "total_fare": 1000
        }
        mock_context.data["selected_train"] = {}
        
        result = await handler.handle_callback(
            "pay_wallet_BK123456",
            123456789,
            mock_context
        )
        
        assert result.status == HandlerResultStatus.SUCCESS
        assert "Wallet Payment" in result.response.text or "Gateway Payment" in result.response.text
    
    def test_create_error_response(self, handler):
        """Test error response creation."""
        result = handler._create_error_response(123456789, "Test error")
        
        assert result.status == HandlerResultStatus.FAILED
        assert "Booking Error" in result.response.text
        assert "Test error" in result.response.text


class TestBookingData:
    """Test cases for BookingData dataclass."""
    
    def test_booking_data_defaults(self):
        """Test BookingData default values."""
        data = BookingData()
        
        assert data.train_data is None
        assert data.class_type is None
        assert data.passengers == []
        assert data.fare == 0.0
        assert data.booking_id is None
        assert data.pnr_number is None
    
    def test_booking_data_with_values(self):
        """Test BookingData with values."""
        data = BookingData(
            train_data={"train_no": "12951"},
            class_type="SL",
            passengers=[{"name": "John", "age": 25, "gender": "M"}],
            fare=500
        )
        
        assert data.train_data["train_no"] == "12951"
        assert data.class_type == "SL"
        assert len(data.passengers) == 1
        assert data.fare == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])