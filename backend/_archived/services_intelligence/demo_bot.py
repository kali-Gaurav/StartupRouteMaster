"""
Demo Interactive Chatbot
=========================

Demonstrates the interactive chatbot functionality with examples.
Run this script to test the chatbot responses.

Usage:
    python -m services.demo_interactive_chatbot

Author: RouteMaster Team
Version: 1.0.0
"""

import asyncio
from services.intelligence.bot_handler import InteractiveBotHandler, Platform
from services.intelligence.conversation import ConversationManager, Intent
from services.intelligence.response_types import (
    InteractiveResponseBuilder, ResponseType, ActionType, Button, CarouselItem
)


async def demo_basic_responses():
    """Demo basic interactive responses"""
    print("\n" + "="*60)
    print("DEMO: Basic Interactive Responses")
    print("="*60)
    
    handler = InteractiveBotHandler()
    
    # Demo 1: Greeting
    print("\n1. User says: 'Hi'")
    response = await handler.process_message(
        user_id="demo_user_1",
        message="Hi",
        platform=Platform.TELEGRAM
    )
    print(f"   Response Type: {response.response_type.value}")
    print(f"   Title: {response.title}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")
    
    # Demo 2: Search trains
    print("\n2. User says: 'Search trains from NDLS to BCT tomorrow'")
    response = await handler.process_message(
        user_id="demo_user_2",
        message="Search trains from NDLS to BCT tomorrow",
        platform=Platform.TELEGRAM
    )
    print(f"   Response Type: {response.response_type.value}")
    print(f"   Carousel Items: {len(response.carousel_items)}")
    for item in response.carousel_items:
        print(f"   - {item.title}: {len(item.buttons)} buttons")
    
    # Demo 3: Check PNR
    print("\n3. User says: 'Check PNR status'")
    response = await handler.process_message(
        user_id="demo_user_3",
        message="Check PNR status",
        platform=Platform.TELEGRAM
    )
    print(f"   Response Type: {response.response_type.value}")
    print(f"   Form Fields: {len(response.form_fields)}")
    for field in response.form_fields:
        print(f"   - {field.label} ({field.field_type})")
    
    # Demo 4: Track train
    print("\n4. User says: 'Track train 12952'")
    response = await handler.process_message(
        user_id="demo_user_4",
        message="Track train 12952",
        platform=Platform.TELEGRAM
    )
    print(f"   Response Type: {response.response_type.value}")
    print(f"   Title: {response.title}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")


async def demo_button_clicks():
    """Demo button click handling"""
    print("\n" + "="*60)
    print("DEMO: Button Click Handling")
    print("="*60)
    
    handler = InteractiveBotHandler()
    
    # Simulate user clicking "Search Trains" button
    print("\n1. User clicks 'Search Trains' button")
    response = await handler.process_callback(
        user_id="demo_user_5",
        action="search_trains",
        value=None,
        conversation_id=None,
        platform=Platform.TELEGRAM
    )
    print(f"   Response Type: {response.response_type.value}")
    print(f"   Content: {response.content[:100]}...")
    
    # Simulate user clicking "Emergency SOS"
    print("\n2. User clicks 'Emergency SOS' button")
    response = await handler.process_callback(
        user_id="demo_user_6",
        action="sos",
        value=None,
        conversation_id=None,
        platform=Platform.TELEGRAM
    )
    print(f"   Response Type: {response.response_type.value}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")


async def demo_conversation_flow():
    """Demo multi-turn conversation flow"""
    print("\n" + "="*60)
    print("DEMO: Multi-Turn Conversation Flow")
    print("="*60)
    
    handler = InteractiveBotHandler()
    user_id = "demo_user_7"
    
    # Turn 1: Initial request
    print("\n--- Turn 1 ---")
    print("User: 'I want to book a ticket'")
    response = await handler.process_message(
        user_id=user_id,
        message="I want to book a ticket",
        platform=Platform.TELEGRAM
    )
    print(f"Bot: {response.title}")
    print(f"State: Requesting booking details")
    
    # Turn 2: Provide some details
    print("\n--- Turn 2 ---")
    print("User: 'From NDLS to BCT'")
    response = await handler.process_message(
        user_id=user_id,
        message="From NDLS to BCT",
        platform=Platform.TELEGRAM
    )
    print(f"Bot: {response.title or 'Response'}")
    print(f"State: Still collecting details")
    
    # Turn 3: Complete booking
    print("\n--- Turn 3 ---")
    print("User: 'Tomorrow in 3A class'")
    response = await handler.process_message(
        user_id=user_id,
        message="Tomorrow in 3A class",
        platform=Platform.TELEGRAM
    )
    print(f"Bot: {response.title}")
    print(f"Response Type: {response.response_type.value}")


async def demo_response_types():
    """Demo all response types"""
    print("\n" + "="*60)
    print("DEMO: Response Types")
    print("="*60)
    
    # Text response
    print("\n1. Text Response:")
    response = (InteractiveResponseBuilder()
        .text("Your booking has been confirmed!", title="Booking Confirmed")
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Content: {response.content}")
    
    # Buttons response
    print("\n2. Buttons Response:")
    response = (InteractiveResponseBuilder()
        .buttons(
            content="What would you like to do next?",
            buttons=[
                Button(text="🔍 Search", action="search", style="primary"),
                Button(text="📋 Bookings", action="bookings", style="default"),
                Button(text="🆘 Help", action="help", style="default")
            ],
            title="Options"
        )
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")
    
    # Carousel response
    print("\n3. Carousel Response:")
    items = [
        CarouselItem(
            item_id="1",
            title="🚂 Rajdhani Express",
            subtitle="NDLS → BCT",
            description="6h 15m • ₹1250",
            buttons=[
                Button(text="Book 3A", action="book_3a", value="3A", style="primary"),
                Button(text="Book 2A", action="book_2a", value="2A", style="default")
            ]
        ),
        CarouselItem(
            item_id="2",
            title="🚂 Shatabdi Express",
            subtitle="NDLS → BCT",
            description="5h 45m • ₹1100",
            buttons=[
                Button(text="Book CC", action="book_cc", value="CC", style="primary"),
                Button(text="Book EC", action="book_ec", value="EC", style="default")
            ]
        )
    ]
    response = (InteractiveResponseBuilder()
        .carousel(
            items=items,
            title="Available Trains",
            content="2 trains found"
        )
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Items: {len(response.carousel_items)}")
    
    # Card response
    print("\n4. Card Response:")
    response = (InteractiveResponseBuilder()
        .card(
            title="🎫 Booking Confirmed",
            content="""
PNR: 2815473690
Train: Rajdhani Express
From: NDLS
To: BCT
Date: 25 Dec 2024
Class: 3A
Fare: ₹1250
            """,
            buttons=[
                Button(text="📥 Download", action="download", style="primary"),
                Button(text="📅 Calendar", action="calendar", style="default")
            ]
        )
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Title: {response.title}")
    
    # SOS response
    print("\n5. SOS Response:")
    response = (InteractiveResponseBuilder()
        .sos(location="Mumbai Central", train_info={"train_number": "12952", "train_name": "Rajdhani"})
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")
    
    # Payment response
    print("\n6. Payment Response:")
    response = (InteractiveResponseBuilder()
        .payment(amount=1250.00, description="Rajdhani Express - 3AC")
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Amount: ₹{response.metadata.get('amount', 0)}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")
    
    # Feedback response
    print("\n7. Feedback Response:")
    response = (InteractiveResponseBuilder()
        .feedback(journey_id="journey_123", question="How was your journey?")
        .build())
    print(f"   Type: {response.response_type.value}")
    print(f"   Buttons: {[b.text for b in response.buttons]}")


async def demo_intent_detection():
    """Demo intent detection"""
    print("\n" + "="*60)
    print("DEMO: Intent Detection")
    print("="*60)
    
    manager = ConversationManager()
    
    test_messages = [
        "Hi, I need help",
        "Search trains from NDLS to BCT",
        "Check my PNR status",
        "Where is train 12952?",
        "Book a ticket for tomorrow",
        "I want to cancel my booking",
        "Emergency! I need help",
        "Thanks for your help",
        "Show me my bookings",
        "What stations have lounges?"
    ]
    
    print("\nIntent Detection Results:")
    for message in test_messages:
        intent = manager.detect_intent(message)
        entities = manager.extract_entities(message)
        entity_types = [e.entity_type for e in entities]
        print(f"\n  '{message}'")
        print(f"    → Intent: {intent.value}")
        if entity_types:
            print(f"    → Entities: {', '.join(entity_types)}")


async def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("INTERACTIVE CHATBOT DEMONSTRATION")
    print("="*60)
    
    await demo_basic_responses()
    await demo_button_clicks()
    await demo_conversation_flow()
    await demo_response_types()
    await demo_intent_detection()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
