# Interactive Chatbot System Documentation

## Overview

The RouteMaster Interactive Chatbot System transforms simple text-based conversations into rich, functional interactions. Instead of plain text responses, the chatbot provides interactive elements like buttons, carousels, forms, and actionable widgets that perform real work—similar to how Gemini assists users in Gmail or Google Drive.

## Key Features

### 1. Rich Interactive Responses

The chatbot supports multiple response types that go beyond simple text:

- **Buttons**: Quick action buttons for common tasks
- **Carousels**: Horizontal scrolling lists of options (train results, etc.)
- **Forms**: Multi-field data collection with validation
- **Cards**: Rich information cards with action buttons
- **SOS Emergency**: One-tap emergency services access
- **Payment Widgets**: Integrated payment flow
- **Feedback Requests**: Rating and feedback collection
- **Redirects**: Seamless navigation to web features
- **Progress Updates**: Real-time operation status

### 2. Multi-Turn Conversations

The system maintains conversation context across multiple interactions:

- **State Tracking**: Remembers where the user is in the conversation flow
- **Entity Extraction**: Automatically extracts relevant information (stations, dates, PNR, etc.)
- **Intent Detection**: Understands user intent from natural language
- **Context Persistence**: Maintains context for the duration of a conversation

### 3. Action-Oriented Design

Every interaction performs actual work:

- **Book Tickets**: Complete booking flow with class selection
- **Track Trains**: Live train status with refresh capabilities
- **Check PNR**: Real-time PNR status with action buttons
- **Cancel/Reschedule**: One-click modification options
- **Download Tickets**: Direct ticket download links
- **Add to Calendar**: Calendar integration
- **Share Itinerary**: Easy sharing via WhatsApp, email, etc.
- **Emergency SOS**: One-tap access to emergency services

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Interactive Chatbot System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────┐  │
│  │   User       │───▶│  Telegram/Web API  │───▶│  Message    │  │
│  │  Platform    │    │  (interactive_     │    │  Processor  │  │
│  │  (Telegram,  │    │   bot_api.py)      │    │             │  │
│  │   Web, etc.) │◀───│                    │◀───│             │  │
│  └──────────────┘    └────────────────────┘    └──────┬──────┘  │
│                                                        │         │
│                                                        ▼         │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────┐  │
│  │  Response    │◀───│  Conversation      │◀───│  Intent     │  │
│  │  Renderer    │    │  Manager           │    │  Detection  │  │
│  │              │    │  (conversation_    │    │             │  │
│  │              │    │   manager.py)      │    │             │  │
│  └──────┬───────┘    └────────────────────┘    └─────────────┘  │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐    ┌────────────────────┐                    │
│  │ Interactive  │───▶│  Action Handlers   │                    │
│  │ Response     │    │  (booking, track,  │                    │
│  │ Types        │    │   sos, etc.)       │                    │
│  └──────────────┘    └────────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Response Types

### Button Response

For quick actions with predefined options:

```python
from services.interactive_response_types import InteractiveResponseBuilder, Button

response = (InteractiveResponseBuilder()
    .buttons(
        content="What would you like to do?",
        buttons=[
            Button(text="🔍 Search Trains", action="search_trains", style="primary"),
            Button(text="📋 My Bookings", action="my_bookings", style="default"),
            Button(text="🚨 Emergency SOS", action="sos", style="danger")
        ],
        title="Main Menu"
    )
    .build())
```

### Carousel Response

For displaying multiple options (train search results, etc.):

```python
from services.interactive_response_types import InteractiveResponseBuilder, CarouselItem, Button

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
            Button(text="Book CC", action="book_cc", value="CC", style="primary")
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
```

### Form Response

For collecting user input with validation:

```python
from services.interactive_response_types import InteractiveResponseBuilder, FormField

response = (InteractiveResponseBuilder()
    .form(
        content="Please provide booking details:",
        fields=[
            FormField(
                field_id="from_station",
                field_type="text",
                label="From Station",
                required=True,
                placeholder="e.g., NDLS"
            ),
            FormField(
                field_id="to_station",
                field_type="text",
                label="To Station",
                required=True,
                placeholder="e.g., BCT"
            ),
            FormField(
                field_id="date",
                field_type="date",
                label="Travel Date",
                required=True
            ),
            FormField(
                field_id="class",
                field_type="dropdown",
                label="Class",
                required=True,
                options=[
                    {"value": "SL", "label": "Sleeper (SL)"},
                    {"value": "3A", "label": "AC 3-Tier (3A)"},
                    {"value": "2A", "label": "AC 2-Tier (2A)"}
                ]
            )
        ],
        action=ActionType.BOOK_TICKET
    )
    .build())
```

### Card Response

For rich information display with actions:

```python
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
            Button(text="📥 Download Ticket", action="download_ticket", style="primary"),
            Button(text="📅 Add to Calendar", action="add_to_calendar", style="default"),
            Button(text="🔍 Track Live", action="track_train", style="default")
        ]
    )
    .build())
```

### SOS Emergency Response

For emergency situations:

```python
response = (InteractiveResponseBuilder()
    .sos(
        location="Mumbai Central",
        train_info={"train_number": "12952", "train_name": "Rajdhani Express"}
    )
    .build())
```

This creates buttons for:
- 🚨 Call Emergency
- 📞 Contact Railway
- 🏥 Medical Help
- 👮 Police
- ❌ Cancel

### Payment Response

For payment processing:

```python
response = (InteractiveResponseBuilder()
    .payment(
        amount=1250.00,
        currency="INR",
        description="Rajdhani Express - 3AC"
    )
    .build())
```

### Feedback Response

For collecting user feedback:

```python
response = (InteractiveResponseBuilder()
    .feedback(
        journey_id="journey_123",
        question="How was your journey?"
    )
    .build())
```

## Conversation Flow

### Multi-Turn Conversation Example

```
User: "I want to book a ticket"
Bot:  [Form] Please provide booking details:
      - From Station
      - To Station
      - Date
      - Class

User: "From NDLS to BCT"
Bot:  [Acknowledges, continues collecting other details]

User: "Tomorrow in 3A class"
Bot:  [Shows search results as carousel]
      [User selects a train]

User: [Clicks "Book 3A" button]
Bot:  [Shows booking confirmation card]
      [Buttons: Download, Calendar, Track]

User: [Clicks "Download Ticket"]
Bot:  [Redirects to download page]
```

### Intent Detection

The system automatically detects user intent from natural language:

| User Message | Detected Intent |
|--------------|-----------------|
| "Search trains from NDLS to BCT" | SEARCH_TRAINS |
| "Check PNR status" | CHECK_PNR |
| "Where is train 12952?" | TRACK_TRAIN |
| "Book a ticket" | BOOK_TICKET |
| "Cancel my booking" | CANCEL_BOOKING |
| "Emergency! I need help" | EMERGENCY_SOS |
| "Hi" | GREETING |
| "Thanks" | THANK_YOU |

### Entity Extraction

Automatically extracts entities from user messages:

- **Station Codes**: NDLS, BCT, ADI, etc.
- **Dates**: "tomorrow", "25 Dec 2024", "today"
- **PNR Numbers**: 10-digit PNR
- **Train Numbers**: 4-5 digit train numbers
- **Passenger Count**: "2 passengers", "3 people"
- **Class Preference**: "3A", "2A", "SL", etc.

## API Endpoints

### Process Message

```http
POST /api/bot/message
Content-Type: application/json

{
    "user_id": "user123",
    "message": "Search trains from NDLS to BCT tomorrow",
    "platform": "telegram",
    "chat_id": "123456789"
}
```

### Process Callback

```http
POST /api/bot/callback
Content-Type: application/json

{
    "user_id": "user123",
    "action": "book_3a",
    "value": "3A",
    "conversation_id": "conv_123",
    "platform": "telegram"
}
```

### Telegram Webhook

```http
POST /api/bot/telegram/webhook
Content-Type: application/json

{
    "update_id": 123456789,
    "message": {
        "message_id": 123,
        "from": {"id": 123456789},
        "chat": {"id": 123456789},
        "text": "Hello"
    }
}
```

### Quick Actions

```http
GET /api/bot/quick/search?user_id=user123&from_station=NDLS&to_station=BCT&date=tomorrow
GET /api/bot/quick/pnr/2815473690?user_id=user123
GET /api/bot/quick/track/12952?user_id=user123
```

### Conversation Management

```http
GET /api/bot/conversation/{user_id}
POST /api/bot/conversation/end
GET /api/bot/conversation/{user_id}/history
```

## Telegram Integration

### Setting Up Webhook

```python
from services.telegram_interactive_handler import telegram_interactive_handler

# Set webhook
await telegram_interactive_handler.set_webhook(
    webhook_url="https://your-domain.com/api/bot/telegram/webhook",
    secret_token="your-secret-token"
)
```

### Handling Updates

```python
from services.telegram_interactive_handler import TelegramInteractiveHandler

handler = TelegramInteractiveHandler()

# Process incoming update
result = await handler.handle_update(update)
```

### Inline Keyboard Format

Buttons are sent as Telegram inline keyboards:

```json
{
    "inline_keyboard": [
        [
            {"text": "🔍 Search Trains", "callback_data": "search_trains|"},
            {"text": "📋 My Bookings", "callback_data": "my_bookings|"}
        ],
        [
            {"text": "🚨 SOS", "callback_data": "sos|"}
        ]
    ]
}
```

Callback data format: `action|value`

## Usage Examples

### Basic Message Processing

```python
from services.interactive_bot_handler import InteractiveBotHandler, Platform

handler = InteractiveBotHandler()

# Process a user message
response = await handler.process_message(
    user_id="user123",
    message="Search trains from NDLS to BCT tomorrow",
    platform=Platform.TELEGRAM,
    chat_id="123456789"
)

print(f"Response Type: {response.response_type.value}")
print(f"Content: {response.content}")
```

### Handling Button Clicks

```python
# Process a button click
response = await handler.process_callback(
    user_id="user123",
    action="book_3a",
    value="3A",
    conversation_id="conv_123",
    platform=Platform.TELEGRAM,
    chat_id="123456789"
)
```

### Creating Custom Responses

```python
from services.interactive_response_types import (
    InteractiveResponseBuilder,
    Button,
    CarouselItem
)

# Create a custom carousel
items = [
    CarouselItem(
        item_id="train1",
        title="🚂 Rajdhani Express",
        subtitle="NDLS → BCT",
        description="6h 15m • ₹1250",
        buttons=[
            Button(text="Book Now", action="book", value="train1", style="primary")
        ]
    )
]

response = (InteractiveResponseBuilder()
    .carousel(
        items=items,
        title="Train Options",
        content="Select a train to book"
    )
    .build())
```

### Running the Demo

```bash
cd backend
python -m services.demo_interactive_chatbot
```

This will demonstrate all the interactive response types and conversation flows.

## Action Types

The system supports the following action types:

| Action Type | Description |
|-------------|-------------|
| `BOOK_TICKET` | Initiate ticket booking |
| `CHECK_PNR` | Check PNR status |
| `TRACK_TRAIN` | Track train live status |
| `CANCEL_BOOKING` | Cancel a booking |
| `RESCHEDULE` | Reschedule a booking |
| `VIEW_BOOKINGS` | View user's bookings |
| `GET_AMENITIES` | Get station amenities |
| `BOOK_WAITING` | Book waiting lounge |
| `EMERGENCY_SOS` | Emergency assistance |
| `DOWNLOAD_TICKET` | Download ticket PDF |
| `ADD_TO_CALENDAR` | Add to calendar |
| `SHARE_ITINERARY` | Share itinerary |
| `REQUEST_REFUND` | Request refund |
| `RATE_JOURNEY` | Rate journey |
| `REPORT_ISSUE` | Report an issue |
| `OPEN_DASHBOARD` | Open web dashboard |

## Best Practices

### 1. Use Appropriate Response Types

- Use **buttons** for quick actions (max 6 buttons)
- Use **carousels** for multiple options (max 10 items)
- Use **forms** for data collection with validation
- Use **cards** for information display with actions
- Use **SOS** for emergencies only

### 2. Maintain Conversation Context

The conversation manager maintains context automatically. Use the conversation ID to continue conversations:

```python
# Get existing conversation
conv = handler.conversation_manager.get_user_conversation(user_id)

# Continue conversation
response = handler.process_message(
    user_id=user_id,
    message="user response",
    context=conv
)
```

### 3. Handle Errors Gracefully

Always handle errors and provide fallback responses:

```python
try:
    response = await handler.process_message(...)
except Exception as e:
    response = (InteractiveResponseBuilder()
        .card(
            title="⚠️ Error",
            content="Something went wrong. Please try again.",
            buttons=[
                Button(text="🔄 Retry", action="retry", style="primary"),
                Button(text="🆘 Help", action="help", style="default")
            ]
        )
        .build())
```

### 4. Use Action Handlers

Register action handlers for custom functionality:

```python
from services.interactive_bot_handler import InteractiveBotHandler
from services.interactive_response_types import ActionType

handler = InteractiveBotHandler()

@handler.register_action_handler(ActionType.CUSTOM_ACTION)
async def handle_custom_action(action, conv):
    # Custom logic
    return (InteractiveResponseBuilder()
        .text("Action completed!")
        .build())
```

## Comparison: Simple Text vs Interactive

### Simple Text Response (Old Way)
```
User: "Check PNR 2815473690"
Bot: "PNR 2815473690: CONFIRMED
      Train: Rajdhani Express
      Date: 25 Dec 2024
      Class: 3A"
```

### Interactive Response (New Way)
```
User: "Check PNR 2815473690"
Bot: [Card with full details + action buttons]
     ┌─────────────────────────────────┐
     │ ✅ PNR Status: CONFIRMED        │
     │ 🎫 PNR: 2815473690             │
     │ 🚂 Rajdhani Express            │
     │ 📍 NDLS → BCT                  │
     │ 🪑 3AC - Side Lower            │
     │                                │
     │ [🔍 Track] [📅 Calendar]       │
     │ [📤 Share] [🔄 Refresh]        │
     └─────────────────────────────────┘
     
     User clicks "🔍 Track"
     Bot: [Shows live train tracking with map]
```

## Integration with Existing System

The interactive chatbot integrates with existing services:

1. **Travel Planning API**: Uses existing search and booking services
2. **Telegram Dispatcher**: Leverages existing Telegram infrastructure
3. **Database Models**: Uses existing user and booking models
4. **Circuit Breaker**: Inherits resilience patterns

## Performance Considerations

- Conversations expire after 30 minutes of inactivity
- Maximum conversation history: 20 messages
- Rate limiting: 30 requests/second (Telegram limit)
- Circuit breaker protection for external APIs

## Future Enhancements

- Voice input support
- Multi-language support
- AI-powered conversation suggestions
- Integration with more platforms (WhatsApp, Web, etc.)
- Advanced analytics and insights
- Custom bot personalities

## Support

For issues or questions, refer to:
- Code comments in each module
- Demo script for usage examples
- API endpoint documentation

---

**Version**: 1.0.0  
**Author**: RouteMaster Team  
**Last Updated**: 2024