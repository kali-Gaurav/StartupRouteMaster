# Telegram Bot System

Production-grade Telegram bot with full website integration.

## Features

### Core Features
- **Command Handling**: `/start`, `/help`, `/search`, `/book`, `/bookings`, `/pnr`, `/profile`, `/wallet`, `/sos`
- **Natural Language Processing**: Intent classification with entity extraction
- **Multi-step Workflows**: Booking flow, search flow, profile management
- **Context-aware Conversations**: Redis-backed session management

### Advanced Features
- **SOS Emergency**: One-tap emergency alerts with location sharing
- **PNR Tracking**: Real-time PNR status checks
- **Booking Management**: Complete booking flow with payment integration
- **User Profiles**: Account management and wallet integration

### Technical Features
- **Resilience Patterns**: Circuit breaker, retry policies, rate limiting
- **Full Observability**: Metrics, health checks, structured logging
- **Production Ready**: Webhook and polling modes
- **Test Coverage**: Unit, integration, and E2E tests

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot System                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Polling   │  │  Webhook    │  │  Command Router     │  │
│  │   Manager   │  │  Handler    │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │               │                    │               │
│         └───────────────┴────────────────────┘               │
│                           │                                  │
│                    ┌──────▼──────┐                           │
│                    │   Bot Core  │                           │
│                    │             │                           │
│                    └──────┬──────┘                           │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Handlers                           │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────┐ │   │
│  │  │ Start  │ │ Search │ │ Booking│ │  PNR   │ │ SOS│ │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────┘ │   │
│  │  ┌────────┐ ┌────────┐ ┌────────────────────────┐  │   │
│  │  │Profile │ │  Help  │ │  Intent Classifier     │  │   │
│  │  └────────┘ └────────┘ └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Services                           │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────────┐ │   │
│  │  │   Dispatcher│ │   Session   │ │  User Service  │ │   │
│  │  │             │ │   Manager   │ │                │ │   │
│  │  └─────────────┘ └─────────────┘ └────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_TOKEN="your_bot_token"
export TELEGRAM_WEBHOOK_URL="https://your-domain.com"
```

## Usage

### Run in Polling Mode (Development)
```bash
python -m telegram_bot.main --mode polling
```

### Run in Webhook Mode (Production)
```bash
# Setup webhook
python -m telegram_bot.main --setup-webhook

# Start server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Run Tests
```bash
# Run all tests
pytest backend/tests/test_telegram_bot.py -v

# Run integration tests
pytest backend/tests/test_telegram_integration.py -v

# Run with coverage
pytest --cov=telegram_bot
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_TOKEN` | Bot API token | Required |
| `TELEGRAM_BOT_MODE` | polling/webhook | polling |
| `TELEGRAM_WEBHOOK_URL` | Webhook URL | Optional |
| `TELEGRAM_MAX_CONCURRENT` | Max concurrent updates | 10 |
| `TELEGRAM_SESSION_TTL` | Session TTL (hours) | 24 |
| `TELEGRAM_ENABLE_NLP` | Enable NLP | true |
| `TELEGRAM_ENABLE_CONTEXT` | Enable context memory | true |
| `TELEGRAM_RATE_LIMIT` | Messages per minute | 30 |
| `TELEGRAM_MAX_RETRIES` | Max retry attempts | 3 |

## Module Structure

```
telegram_bot/
├── __init__.py          # Package exports
├── bot.py               # Main bot class
├── main.py              # Entry point
├── config.py            # Configuration
├── schemas.py           # Pydantic models
├── dispatcher.py        # Telegram API client
├── command_router.py    # Intent routing
├── intent_classifier.py # NLP intent detection
├── user_session_manager.py  # Session management
├── keyboards.py         # UI components
├── polling.py           # Long polling manager
├── webhook.py           # Webhook handler
├── handlers/            # Command handlers
│   ├── __init__.py
│   ├── start_handler.py
│   ├── search_handler.py
│   ├── booking_handler.py
│   ├── pnr_handler.py
│   ├── profile_handler.py
│   ├── sos_handler.py
│   └── help_handler.py
└── tests/               # Tests
    ├── conftest.py
    ├── test_telegram_bot.py
    └── test_telegram_integration.py
```

## API Endpoints

### Webhook Mode
- `POST /webhooks/telegram` - Telegram webhook endpoint
- `GET /webhooks/telegram/health` - Health check
- `GET /webhooks/telegram/info` - Bot info

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help |
| `/search` | Search trains |
| `/book` | Book a ticket |
| `/bookings` | View bookings |
| `/pnr <number>` | Check PNR status |
| `/profile` | View profile |
| `/wallet` | View wallet |
| `/sos` | Emergency assistance |

## Natural Language Examples

```
User: "Trains from Mumbai to Delhi tomorrow"
Bot:  Shows train options

User: "Check PNR 1234567890"
Bot:  Shows PNR status

User: "Book a ticket from Bangalore to Chennai"
Bot:  Starts booking flow

User: "I'm in danger SOS"
Bot:  Shows emergency options
```

## Resilience Patterns

### Circuit Breaker
- Prevents cascade failures
- Auto-recovery after timeout
- Configurable thresholds

### Retry Policy
- Exponential backoff with jitter
- Selective retry conditions
- Configurable attempts

### Rate Limiting
- Message rate limiting
- Sliding window algorithm
- Configurable limits

## Monitoring

### Health Check
```python
from telegram_bot.bot import telegram_bot
health = telegram_bot.get_health()
```

### Metrics
```python
from telegram_bot.bot import telegram_bot
metrics = telegram_bot.get_metrics()
```

## Integration with Website

The bot integrates with all existing services:

- **Search Service**: Train search and availability
- **Booking Service**: Ticket booking and management
- **PNR Service**: PNR status tracking
- **User Service**: User management
- **Payment Service**: Payment processing
- **SOS Service**: Emergency handling

## License

MIT License