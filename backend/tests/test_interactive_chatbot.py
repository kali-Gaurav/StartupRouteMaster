"""
Tests for Interactive Chatbot System
=====================================

Tests for the interactive chatbot functionality.

Author: RouteMaster Team
Version: 1.0.0
"""

import pytest
import asyncio
from datetime import datetime
from services.interactive_response_types import (
    InteractiveResponseBuilder, Button, FormField, CarouselItem,
    ResponseType, ActionType, InteractiveResponse
)
from services.conversation_manager import (
    ConversationManager, ConversationContext, ConversationState, Intent, Entity
)
from services.interactive_bot_handler import InteractiveBotHandler, Platform


class TestInteractiveResponseTypes:
    """Tests for interactive response types"""
    
    def test_text_response(self):
        """Test creating a text response"""
        response = (InteractiveResponseBuilder()
            .text("Hello, world!", title="Greeting")
            .build())
        
        assert response.response_type == ResponseType.TEXT
        assert response.content == "Hello, world!"
        assert response.title == "Greeting"
        assert len(response.buttons) == 0
    
    def test_buttons_response(self):
        """Test creating a buttons response"""
        buttons = [
            Button(text="Yes", action="yes", style="primary"),
            Button(text="No", action="no", style="danger")
        ]
        
        response = (InteractiveResponseBuilder()
            .buttons(
                content="Are you sure?",
                buttons=buttons,
                title="Confirmation"
            )
            .build())
        
        assert response.response_type == ResponseType.BUTTONS
        assert len(response.buttons) == 2
        assert response.buttons[0].text == "Yes"
        assert response.buttons[0].style == "primary"
    
    def test_carousel_response(self):
        """Test creating a carousel response"""
        items = [
            CarouselItem(
                item_id="1",
                title="Train 1",
                subtitle="Route 1",
                description="5h • ₹1000"
            ),
            CarouselItem(
                item_id="2",
                title="Train 2",
                subtitle="Route 2",
                description="6h • ₹1200"
            )
        ]
        
        response = (InteractiveResponseBuilder()
            .carousel(
                items=items,
                title="Search Results",
                content="2 trains found"
            )
            .build())
        
        assert response.response_type == ResponseType.CAROUSEL
        assert len(response.carousel_items) == 2
    
    def test_form_response(self):
        """Test creating a form response"""
        fields = [
            FormField(
                field_id="name",
                field_type="text",
                label="Name",
                required=True
            ),
            FormField(
                field_id="age",
                field_type="number",
                label="Age",
                required=False
            )
        ]
        
        response = (InteractiveResponseBuilder()
            .form(
                content="Please fill out the form:",
                fields=fields,
                action=ActionType.BOOK_TICKET
            )
            .build())
        
        assert response.response_type == ResponseType.FORM
        assert len(response.form_fields) == 2
        assert response.primary_action == ActionType.BOOK_TICKET
    
    def test_card_response(self):
        """Test creating a card response"""
        buttons = [
            Button(text="Action", action="do_something", style="primary")
        ]
        
        response = (InteractiveResponseBuilder()
            .card(
                title="Card Title",
                content="Card content here",
                buttons=buttons,
                subtitle="Card subtitle"
            )
            .build())
        
        assert response.response_type == ResponseType.CARD
        assert response.title == "Card Title"
        assert len(response.buttons) == 1
    
    def test_sos_response(self):
        """Test creating an SOS response"""
        response = (InteractiveResponseBuilder()
            .sos(
                location="Mumbai Central",
                train_info={"train_number": "12952", "train_name": "Rajdhani"}
            )
            .build())
        
        assert response.response_type == ResponseType.ACTION
        assert response.primary_action == ActionType.EMERGENCY_SOS
        assert len(response.buttons) == 5  # 5 SOS options
    
    def test_payment_response(self):
        """Test creating a payment response"""
        response = (InteractiveResponseBuilder()
            .payment(amount=1250.00, description="Train fare")
            .build())
        
        assert response.response_type == ResponseType.PAYMENT
        assert response.metadata["amount"] == 1250.00
        assert len(response.buttons) == 3  # Card, UPI, Net Banking
    
    def test_feedback_response(self):
        """Test creating a feedback response"""
        response = (InteractiveResponseBuilder()
            .feedback(journey_id="journey_123")
            .build())
        
        assert response.response_type == ResponseType.FEEDBACK
        assert len(response.buttons) == 5  # 5 rating options
    
    def test_redirect_response(self):
        """Test creating a redirect response"""
        response = (InteractiveResponseBuilder()
            .redirect(
                url="https://example.com",
                message="Click to open",
                button_text="Open"
            )
            .build())
        
        assert response.response_type == ResponseType.REDIRECT
        assert response.metadata["url"] == "https://example.com"
    
    def test_confirmation_response(self):
        """Test creating a confirmation response"""
        response = (InteractiveResponseBuilder()
            .confirmation(
                message="Are you sure?",
                confirm_action="confirm_yes",
                cancel_action="confirm_no"
            )
            .build())
        
        assert response.response_type == ResponseType.CONFIRMATION
        assert len(response.buttons) == 2
        assert response.buttons[0].text == "✓ Confirm"
        assert response.buttons[1].text == "✗ Cancel"
    
    def test_response_to_dict(self):
        """Test converting response to dictionary"""
        response = (InteractiveResponseBuilder()
            .text("Test", title="Test")
            .build())
        
        data = response.to_dict()
        
        assert "response_id" in data
        assert "response_type" in data
        assert data["content"] == "Test"
        assert data["title"] == "Test"


class TestConversationManager:
    """Tests for conversation manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = ConversationManager()
    
    def test_get_or_create_conversation(self):
        """Test getting or creating a conversation"""
        conv = self.manager.get_or_create_conversation("user123")
        
        assert conv is not None
        assert conv.user_id == "user123"
        assert conv.state == ConversationState.IDLE
        assert conv.intent == Intent.UNKNOWN
    
    def test_get_existing_conversation(self):
        """Test getting an existing conversation"""
        conv1 = self.manager.get_or_create_conversation("user123")
        conv2 = self.manager.get_or_create_conversation("user123")
        
        assert conv1.conversation_id == conv2.conversation_id
    
    def test_add_entity(self):
        """Test adding entities to conversation"""
        conv = self.manager.get_or_create_conversation("user123")
        
        entity = Entity(
            entity_type="station_code",
            value="NDLS",
            confidence=0.95,
            start_pos=0,
            end_pos=4
        )
        conv.add_entity(entity)
        
        assert conv.entities["station_code"] == "NDLS"
        assert len(conv.entities_list) == 1
    
    def test_add_to_history(self):
        """Test adding to conversation history"""
        conv = self.manager.get_or_create_conversation("user123")
        
        response = (InteractiveResponseBuilder()
            .text("Hello!")
            .build())
        
        conv.add_to_history("user", "Hi", response)
        
        assert len(conv.history) == 1
        assert conv.history[0]["role"] == "user"
        assert conv.history[0]["response_type"] == "text"
    
    def test_detect_intent_greeting(self):
        """Test detecting greeting intent"""
        intent = self.manager.detect_intent("Hi there!")
        assert intent == Intent.GREETING
    
    def test_detect_intent_search(self):
        """Test detecting search intent"""
        intent = self.manager.detect_intent("Search trains from NDLS to BCT")
        assert intent == Intent.SEARCH_TRAINS
    
    def test_detect_intent_pnr(self):
        """Test detecting PNR intent"""
        intent = self.manager.detect_intent("Check my PNR status")
        assert intent == Intent.CHECK_PNR
    
    def test_detect_intent_track(self):
        """Test detecting track intent"""
        intent = self.manager.detect_intent("Where is train 12952?")
        assert intent == Intent.TRACK_TRAIN
    
    def test_detect_intent_emergency(self):
        """Test detecting emergency intent"""
        intent = self.manager.detect_intent("Emergency! I need help!")
        assert intent == Intent.EMERGENCY_SOS
    
    def test_detect_intent_unknown(self):
        """Test detecting unknown intent"""
        intent = self.manager.detect_intent("Random text")
        assert intent == Intent.UNKNOWN
    
    def test_extract_entities_station(self):
        """Test extracting station entities"""
        entities = self.manager.extract_entities("From NDLS to BCT")
        
        station_entities = [e for e in entities if e.entity_type == "station_code"]
        assert len(station_entities) == 2
        assert station_entities[0].value == "NDLS"
        assert station_entities[1].value == "BCT"
    
    def test_extract_entities_pnr(self):
        """Test extracting PNR entities"""
        entities = self.manager.extract_entities("Check PNR 1234567890")
        
        pnr_entities = [e for e in entities if e.entity_type == "pnr"]
        assert len(pnr_entities) == 1
        assert pnr_entities[0].value == "1234567890"
    
    def test_extract_entities_train_number(self):
        """Test extracting train number entities"""
        entities = self.manager.extract_entities("Track train 12952")
        
        train_entities = [e for e in entities if e.entity_type == "train_number"]
        assert len(train_entities) == 1
        assert train_entities[0].value == "12952"
    
    def test_extract_entities_date(self):
        """Test extracting date entities"""
        entities = self.manager.extract_entities("Search for tomorrow")
        
        date_entities = [e for e in entities if e.entity_type == "date"]
        assert len(date_entities) == 1
        assert date_entities[0].value == "tomorrow"
    
    def test_end_conversation(self):
        """Test ending a conversation"""
        conv = self.manager.get_or_create_conversation("user123")
        self.manager.end_conversation("user123")
        
        # Should create a new conversation
        conv2 = self.manager.get_or_create_conversation("user123")
        assert conv2.conversation_id != conv.conversation_id
    
    def test_get_stats(self):
        """Test getting manager statistics"""
        self.manager.get_or_create_conversation("user1")
        self.manager.get_or_create_conversation("user2")
        
        stats = self.manager.get_stats()
        
        assert stats["active_conversations"] == 2
        assert stats["user_sessions"] == 2


class TestInteractiveBotHandler:
    """Tests for interactive bot handler"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.handler = InteractiveBotHandler()
    
    @pytest.mark.asyncio
    async def test_process_message_greeting(self):
        """Test processing a greeting message"""
        response = await self.handler.process_message(
            user_id="test_user",
            message="Hi",
            platform=Platform.TELEGRAM
        )
        
        assert response is not None
        assert response.response_type == ResponseType.BUTTONS
        assert len(response.buttons) > 0
    
    @pytest.mark.asyncio
    async def test_process_message_search(self):
        """Test processing a search message"""
        response = await self.handler.process_message(
            user_id="test_user",
            message="Search trains from NDLS to BCT tomorrow",
            platform=Platform.TELEGRAM
        )
        
        assert response is not None
        # Should return carousel or buttons
        assert response.response_type in [ResponseType.CAROUSEL, ResponseType.BUTTONS]
    
    @pytest.mark.asyncio
    async def test_process_message_pnr(self):
        """Test processing a PNR message"""
        response = await self.handler.process_message(
            user_id="test_user",
            message="Check PNR status",
            platform=Platform.TELEGRAM
        )
        
        assert response is not None
        # Should return form for PNR input
        assert response.response_type == ResponseType.FORM
    
    @pytest.mark.asyncio
    async def test_process_callback(self):
        """Test processing a callback (button click)"""
        response = await self.handler.process_callback(
            user_id="test_user",
            action="search_trains",
            value=None,
            platform=Platform.TELEGRAM
        )
        
        assert response is not None
    
    @pytest.mark.asyncio
    async def test_process_callback_sos(self):
        """Test processing SOS callback"""
        response = await self.handler.process_callback(
            user_id="test_user",
            action="sos",
            value=None,
            platform=Platform.TELEGRAM
        )
        
        assert response is not None
        assert response.response_type == ResponseType.ACTION
        assert response.primary_action == ActionType.EMERGENCY_SOS
    
    def test_get_stats(self):
        """Test getting handler stats"""
        stats = self.handler.get_stats()
        
        assert "conversation_manager" in stats
        assert "registered_actions" in stats
        assert "registered_platforms" in stats


class TestButtonStyles:
    """Tests for button styling"""
    
    def test_default_style(self):
        """Test default button style"""
        button = Button(text="Click me", action="click")
        assert button.style == "default"
    
    def test_primary_style(self):
        """Test primary button style"""
        button = Button(text="Primary", action="primary", style="primary")
        assert button.style == "primary"
    
    def test_danger_style(self):
        """Test danger button style"""
        button = Button(text="Delete", action="delete", style="danger")
        assert button.style == "danger"
    
    def test_success_style(self):
        """Test success button style"""
        button = Button(text="Success", action="success", style="success")
        assert button.style == "success"


class TestFormFields:
    """Tests for form fields"""
    
    def test_text_field(self):
        """Test text form field"""
        field = FormField(
            field_id="name",
            field_type="text",
            label="Name",
            required=True
        )
        assert field.field_type == "text"
        assert field.required is True
    
    def test_dropdown_field(self):
        """Test dropdown form field"""
        field = FormField(
            field_id="class",
            field_type="dropdown",
            label="Class",
            options=[
                {"value": "SL", "label": "Sleeper"},
                {"value": "3A", "label": "AC 3-Tier"}
            ]
        )
        assert field.field_type == "dropdown"
        assert len(field.options) == 2
    
    def test_number_field(self):
        """Test number form field"""
        field = FormField(
            field_id="count",
            field_type="number",
            label="Count",
            default_value=1
        )
        assert field.field_type == "number"
        assert field.default_value == 1
    
    def test_date_field(self):
        """Test date form field"""
        field = FormField(
            field_id="date",
            field_type="date",
            label="Date",
            required=True
        )
        assert field.field_type == "date"
        assert field.required is True


class TestCarouselItems:
    """Tests for carousel items"""
    
    def test_carousel_item_creation(self):
        """Test creating a carousel item"""
        item = CarouselItem(
            item_id="train1",
            title="Rajdhani Express",
            subtitle="NDLS → BCT",
            description="6h 15m • ₹1250"
        )
        
        assert item.item_id == "train1"
        assert item.title == "Rajdhani Express"
        assert len(item.buttons) == 0
    
    def test_carousel_item_with_buttons(self):
        """Test carousel item with buttons"""
        buttons = [
            Button(text="Book", action="book", style="primary")
        ]
        
        item = CarouselItem(
            item_id="train1",
            title="Train",
            buttons=buttons
        )
        
        assert len(item.buttons) == 1
    
    def test_carousel_item_with_metadata(self):
        """Test carousel item with metadata"""
        item = CarouselItem(
            item_id="train1",
            title="Train",
            metadata={"train_number": "12952", "fare": 1250}
        )
        
        assert item.metadata["train_number"] == "12952"
        assert item.metadata["fare"] == 1250


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])