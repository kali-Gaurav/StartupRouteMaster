# Gemini API Configuration Guide

This guide explains how to securely configure Gemini API keys for the RouteMaster Agent.

## ⚠️ Security Best Practices

**NEVER commit API keys to git!** API keys are sensitive credentials that grant access to your account and can incur charges. Always:

1. ✅ Store API keys in `.env` file (which is in `.gitignore`)
2. ✅ Use environment variables to load keys at runtime
3. ✅ Rotate keys regularly
4. ✅ Monitor API usage for unusual activity
5. ❌ DON'T hardcode keys in source files
6. ❌ DON'T share keys in emails, chat, or documentation
7. ❌ DON'T commit `.env` file to git

## Setup Instructions

### Step 1: Create Your `.env` File

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Or on Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

### Step 2: Add Your Gemini API Keys

Edit the `.env` file and replace the placeholder values with your actual API keys:

```env
# Individual API keys (up to 5 for load balancing)
GEMINI_API_KEY1=AIzaSyCBTKUZVmsK0zL-UV0iMeX4xl7pcEFrjo8
GEMINI_API_KEY2=AIzaSyD9Ll7S77-bH6LKvt5iMOPd4VOoSC5nuhQ
GEMINI_API_KEY3=AIzaSyAWkHqxe2k7qH1DLiAs2W5IN0x7HDzb1_w
GEMINI_API_KEY4=AIzaSyD9Ll7S77-bH6LKvt5iMOPd4VOoSC5nuhQ
GEMINI_API_KEY5=AIzaSyAmDE_MmY8PyeoNGIIcIJYjVrs_PazfZGo

# Or use a single API key
GEMINI_API_KEY=AIzaSyCBTKUZVmsK0zL-UV0iMeX4xl7pcEFrjo8
```

### Step 3: Verify `.env` is in `.gitignore`

The `.env` file should already be in `.gitignore`. Verify:

```bash
grep -E "^\.env$" .gitignore
```

### Step 4: Install Dependencies

Ensure you have the required Python packages:

```bash
pip install -r routemaster_agent/requirements.txt
```

Key packages:
- `python-dotenv` - Load environment variables from `.env`
- `google-generativeai` - Gemini API client

### Step 5: Load Environment Variables in Your Code

The code automatically loads environment variables when the module is imported:

```python
from routemaster_agent.ai.gemini_client import GeminiClient

# Automatically loads from GEMINI_API_KEY1-5 or GEMINI_API_KEY
client = GeminiClient()
```

If you need to explicitly load the `.env` file first:

```python
from dotenv import load_dotenv
load_dotenv()  # Load from .env file

from routemaster_agent.ai.gemini_client import GeminiClient
client = GeminiClient()
```

## Multiple API Keys (Load Balancing)

The updated `GeminiClient` supports multiple API keys for:

1. **Rate limit handling** - Automatically switches to next key when rate limited
2. **Quota management** - Distributes requests across keys
3. **Failover** - Falls back to next key if one is exhausted

### How It Works

1. Keys are loaded from `GEMINI_API_KEY1` through `GEMINI_API_KEY5`
2. On each API call, the current key is used
3. If a rate limit error (429, 403, or "quota exceeded") occurs, automatically switches to the next key
4. After switching, retries the request with the new key
5. Falls back to deterministic scrapers if all keys are exhausted

### Example Configuration

```env
# Keys will be used in rotation
GEMINI_API_KEY1=your_first_key
GEMINI_API_KEY2=your_second_key
GEMINI_API_KEY3=your_third_key
# GEMINI_API_KEY4 and GEMINI_API_KEY5 are optional
```

## Fallback to Single Key

If you only have one API key, use `GEMINI_API_KEY`:

```env
GEMINI_API_KEY=your_single_api_key
```

The client will automatically detect and use it.

## Getting a Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the generated key
4. Add it to your `.env` file

## Troubleshooting

### "GEMINI_API_KEY not set" Warning

This warning appears if no API keys are found. Check:

1. `.env` file exists in project root
2. `.env` file has `GEMINI_API_KEY` or `GEMINI_API_KEY1-5` set
3. Run `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GEMINI_API_KEY1'))"` to verify loading

### "google-generativeai not installed" Warning

Install the package:

```bash
pip install google-generativeai
```

### Rate Limit Errors

If you see "Rate limited" messages:

1. Add more API keys to `GEMINI_API_KEY2`, `GEMINI_API_KEY3`, etc.
2. Each additional key increases your quota
3. The client automatically rotates between keys

### API Key Invalid

Verify your key:

1. Check for typos in `.env` file
2. Ensure the key is from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. Keys have a quota limit; check [usage stats](https://makersuite.google.com/app/billing/overview)

## Logging API Key Status

When the app starts, you'll see logs like:

```
✓ Gemini client initialized (model: gemini-pro-vision, 3 key(s) available)
```

This shows:
- ✓ Gemini is enabled
- `gemini-pro-vision` is the model being used
- `3 key(s) available` means keys 1-3 are configured

## Production Deployment

For production, use secure secret management:

1. **AWS Secrets Manager** - Store keys in AWS
2. **HashiCorp Vault** - Enterprise secret management
3. **Environment variables** - Set directly in production environment
4. **GCP Secret Manager** - If using Google Cloud Platform

Never store `.env` files in production repositories.

## API Key Rotation

To rotate API keys:

1. Create new keys in [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Update `.env` with new keys
3. Restart the application
4. Delete old keys from Google AI Studio

## Monitoring API Usage

Monitor your usage at:
- [Google AI Studio - Billing](https://makersuite.google.com/app/billing/overview)
- Check daily and monthly quotas
- Monitor request counts and errors

## Support

If you encounter issues:

1. Check the [Google Gemini API documentation](https://ai.google.dev/)
2. Review logs in `logs/routemaster.log`
3. Check the troubleshooting section above

---

**Remember:** Keep your API keys private and secure! 🔐
