# Quick Start: Gemini API Configuration

## 3-Minute Setup

### 1. Create `.env` file

```bash
# Linux/Mac
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

### 2. Edit `.env` and add your API keys

Open `.env` in your editor and replace:

```env
GEMINI_API_KEY1=your_actual_key_1
GEMINI_API_KEY2=your_actual_key_2
# ... add up to 5 keys
```

Or just one key:

```env
GEMINI_API_KEY=your_actual_key
```

### 3. Done! ✅

The system automatically loads keys from `.env` on startup.

---

## Verify Configuration

```bash
# Run Python and check if keys are loaded
python -c "from routemaster_agent.config import print_config; print_config()"
```

Should show:
```
=== RouteMaster Agent Configuration ===

Gemini API Keys: 3 key(s) configured
  - Model: gemini-pro-vision
  - Enabled: True
  - Timeout: 30s
```

---

## Using in Your Code

```python
from routemaster_agent.ai.gemini_client import GeminiClient

# Automatically loads keys from .env
client = GeminiClient()

# Use the client
result = await client.analyze_page_layout(screenshot)
```

---

## Multiple Keys (Load Balancing)

Add 2-5 keys for automatic load balancing and failover:

```env
GEMINI_API_KEY1=key_1
GEMINI_API_KEY2=key_2
GEMINI_API_KEY3=key_3
GEMINI_API_KEY4=key_4
GEMINI_API_KEY5=key_5
```

Benefits:
- ✅ Automatic rate limit handling
- ✅ Distributed quota usage
- ✅ Failover if one key is exhausted
- ✅ Better performance under load

---

## Getting API Keys

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key
4. Add to `.env`

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "GEMINI_API_KEY not set" | Create `.env` file with keys |
| "google-generativeai not installed" | Run `pip install google-generativeai` |
| "Rate limited" | Add more API keys to `GEMINI_API_KEY2`, etc. |
| Keys not loading | Ensure `.env` is in project root |

---

## Security Checklist

- ✅ `.env` is in `.gitignore`
- ✅ Never commit `.env` to git
- ✅ Never share API keys
- ✅ Keep keys out of logs
- ✅ Rotate keys regularly

---

## Troubleshooting

### Check if `.env` is loading:

```python
import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv('GEMINI_API_KEY1'))  # Should print your key
```

### View all configuration:

```bash
python -c "from routemaster_agent.config import print_config; print_config()"
```

### Check API usage:

Visit [Google AI Studio - Billing](https://makersuite.google.com/app/billing/overview)

---

## What's Next?

- Read [GEMINI_API_SETUP.md](GEMINI_API_SETUP.md) for detailed documentation
- Check [README_V2_START_HERE.md](README_V2_START_HERE.md) for overall setup
- Start using the RouteMaster Agent!

---

**Questions?** Check the troubleshooting section above or the detailed setup guide.
