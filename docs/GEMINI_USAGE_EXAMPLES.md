# Gemini API Usage Examples

Your Gemini API keys are configured and ready to use. Here are practical examples for the RouteMaster Agent.

---

## Quick Start

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def main():
    # Initialize client - keys automatically loaded from .env
    client = GeminiClient()
    
    if not client.enabled:
        print("Gemini is not enabled - check your .env file")
        return
    
    print(f"✅ Gemini enabled with {len(client.api_keys)} keys")
    print(f"   Model: {client.model}")

asyncio.run(main())
```

---

## Example 1: Analyze Page Layout

Use this to understand the structure of a webpage.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def analyze_page():
    client = GeminiClient()
    
    # Load a screenshot of NTES website
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    # Analyze the layout
    result = await client.analyze_page_layout(
        screenshot=screenshot,
        context="NTES train booking website"
    )
    
    print(f"Layout Type: {result.get('layout_type')}")
    print(f"Confidence: {result.get('layout_confidence')}")
    print(f"Tables Found: {len(result.get('tables', []))}")
    print(f"Forms Found: {len(result.get('forms', []))}")
    print(f"Buttons Found: {len(result.get('buttons', []))}")

asyncio.run(analyze_page())
```

---

## Example 2: Detect Form Fields

Automatically detect all form fields on a page.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def detect_fields():
    client = GeminiClient()
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    # Detect form fields
    fields = await client.detect_form_fields(
        screenshot=screenshot,
        hint="Train booking search form"
    )
    
    print(f"Detected {len(fields)} form fields:\n")
    for field in fields:
        print(f"  - {field['label']}")
        print(f"    Type: {field['type']}")
        print(f"    Required: {field['required']}")
        print(f"    Confidence: {field['confidence']}\n")

asyncio.run(detect_fields())
```

---

## Example 3: Extract Table Structure

Extract data table structure and sample rows.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def extract_table():
    client = GeminiClient()
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    # Extract table structure
    table = await client.extract_table_structure(
        screenshot=screenshot,
        hint="Train schedule with stations and timings"
    )
    
    if not table:
        print("No table found")
        return
    
    print(f"Headers: {table.get('headers')}")
    print(f"Rows: {table.get('row_count')}")
    print(f"Paginated: {table.get('is_paginated')}")
    print(f"\nSample Data:")
    for row in table.get('sample_rows', []):
        print(f"  {row}")

asyncio.run(extract_table())
```

---

## Example 4: Extract Specific Field

Extract a specific field value from a screenshot.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def extract_field():
    client = GeminiClient()
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    html = """
    <form>
        <label>Train Name:</label>
        <input id="train-name" value="Rajdhani Express"/>
    </form>
    """
    
    # Extract a specific field
    result = await client.extract_field(
        screenshot=screenshot,
        html=html,
        field_name="Train Name",
        expected_type="text"
    )
    
    if result and result.get('found'):
        print(f"✅ Found: {result.get('value')}")
        print(f"   Confidence: {result.get('confidence')}")
    else:
        print("❌ Field not found")

asyncio.run(extract_field())
```

---

## Example 5: Infer Data Schema

Automatically determine what data fields are on a page.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def infer_schema():
    client = GeminiClient()
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    # Infer the data schema
    schema = await client.infer_data_schema(
        screenshot=screenshot,
        hint="Train schedule page"
    )
    
    print("Inferred Schema:")
    for field, field_type in schema.items():
        print(f"  {field}: {field_type}")

asyncio.run(infer_schema())
```

---

## Example 6: Detect Buttons

Find all clickable buttons on a page.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def detect_buttons():
    client = GeminiClient()
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    # Detect buttons
    buttons = await client.detect_buttons(
        screenshot=screenshot,
        hint="Train booking form"
    )
    
    print(f"Found {len(buttons)} buttons:\n")
    for button in buttons:
        print(f"  Text: {button['text']}")
        print(f"  Intent: {button['intent']}")
        print(f"  Region: {button['region']}")
        print(f"  Confidence: {button['confidence']}\n")

asyncio.run(detect_buttons())
```

---

## Example 7: Analyze Page Intent

Understand what a page is for.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def analyze_intent():
    client = GeminiClient()
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    # Analyze page intent
    intent = await client.analyze_page_intent(
        screenshot=screenshot,
        url="https://www.ntes.in/TrainAvailability"
    )
    
    print(f"Page Type: {intent.get('page_type')}")
    print(f"Primary Intent: {intent.get('primary_intent')}")
    print(f"Expected Fields: {intent.get('expected_fields')}")
    print(f"Expected Actions: {intent.get('expected_actions')}")

asyncio.run(analyze_intent())
```

---

## Example 8: Detect Layout Changes

Detect if a page layout has changed between two screenshots.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def detect_changes():
    client = GeminiClient()
    
    # Load two screenshots
    with open('screenshot_old.png', 'rb') as f:
        old = f.read()
    
    with open('screenshot_new.png', 'rb') as f:
        new = f.read()
    
    # Detect changes
    changes = await client.detect_layout_changes(
        current_screenshot=new,
        previous_screenshot=old
    )
    
    if changes.get('changed'):
        print("⚠️  Layout has changed!")
        print(f"   Type: {changes.get('change_type')}")
        print(f"   Changes: {changes.get('changes_detected')}")
        print(f"   Recommendation: {changes.get('recommendation')}")
    else:
        print("✅ Layout is unchanged")

asyncio.run(detect_changes())
```

---

## Example 9: Using with RouteMaster Agent

Integrate Gemini client into the RouteMaster Agent's AI loop.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
from routemaster_agent.ai.reasoning_controller import ReasoningController
import asyncio

async def advanced_analysis():
    # Initialize both client and controller
    client = GeminiClient()
    controller = ReasoningController()
    
    # Use Gemini for vision tasks
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    layout = await client.analyze_page_layout(screenshot)
    intent = await client.analyze_page_intent(screenshot)
    
    # Use controller for reasoning
    task = {
        'type': 'extract_train_schedule',
        'train_number': '12951',
        'page_layout': layout,
        'page_intent': intent
    }
    
    result = await controller.execute_task(task)
    print(f"Task Result: {result}")

asyncio.run(advanced_analysis())
```

---

## Example 10: Error Handling with Automatic Retry

The client automatically handles rate limits, but here's how to handle other errors.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio

async def safe_analysis():
    client = GeminiClient()
    
    if not client.enabled:
        print("⚠️  Gemini is not enabled")
        print("   Add API keys to .env file")
        return None
    
    with open('screenshot.png', 'rb') as f:
        screenshot = f.read()
    
    try:
        result = await client.analyze_page_layout(screenshot)
        
        if result:
            print(f"✅ Success: {result.get('layout_type')}")
            return result
        else:
            print("⚠️  No result returned")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        # Fall back to deterministic analysis
        print("   Falling back to deterministic scrapers...")
        return None

asyncio.run(safe_analysis())
```

---

## Example 11: Batch Processing

Process multiple screenshots with key rotation.

```python
from routemaster_agent.ai.gemini_client import GeminiClient
import asyncio
from pathlib import Path

async def batch_process():
    client = GeminiClient()
    
    # Process all PNGs in a directory
    screenshots = list(Path("screenshots").glob("*.png"))
    results = []
    
    for i, screenshot_path in enumerate(screenshots):
        print(f"Processing {i+1}/{len(screenshots)}: {screenshot_path.name}")
        
        try:
            with open(screenshot_path, 'rb') as f:
                screenshot = f.read()
            
            result = await client.analyze_page_layout(
                screenshot=screenshot,
                context="NTES website"
            )
            
            results.append({
                'file': screenshot_path.name,
                'layout': result.get('layout_type'),
                'confidence': result.get('layout_confidence')
            })
            
            # Show current key being used
            print(f"   Using Key #{client.current_key_index + 1}")
            
        except Exception as e:
            print(f"   Error: {e}")
    
    # Summary
    print(f"\nProcessed {len(results)} screenshots")
    for r in results:
        print(f"  {r['file']}: {r['layout']} ({r['confidence']})")

asyncio.run(batch_process())
```

---

## Monitoring Key Usage

```python
from routemaster_agent.config import GeminiConfig

# Check configuration
keys = GeminiConfig.get_api_keys()
print(f"API Keys: {len(keys)}")
print(f"Model: {GeminiConfig.get_model()}")
print(f"Timeout: {GeminiConfig.get_timeout()}s")
print(f"Enabled: {GeminiConfig.is_enabled()}")

# Monitor during usage
from routemaster_agent.ai.gemini_client import GeminiClient

client = GeminiClient()
print(f"Current Key Index: {client.current_key_index}")
print(f"Available Keys: {len(client.api_keys)}")

# The index will increment when rate limits occur
```

---

## Debugging

### Enable Debug Logging

```python
import logging

# Set to DEBUG for detailed logs
logging.basicConfig(level=logging.DEBUG)

# Now run your code - you'll see:
# - Which key is being used
# - When keys are switched
# - All API responses
# - Error details
```

### Log Output Example

```
DEBUG:routemaster_agent.ai.gemini_client:✓ Gemini client initialized (model: gemini-pro-vision, 5 key(s) available)
DEBUG:routemaster_agent.ai.gemini_client:✓ Page layout analyzed: table
DEBUG:routemaster_agent.ai.gemini_client:Rate limited on key 1/5. Switching to next key... (1/3)
DEBUG:routemaster_agent.ai.gemini_client:✓ Page layout analyzed: table
```

---

## Production Tips

1. **Never hardcode keys**: Always use `.env` file
2. **Monitor usage**: Check Google AI Studio regularly
3. **Log key transitions**: Enable debug logging in production for troubleshooting
4. **Implement caching**: Cache results to reduce API calls
5. **Set rate limits**: Implement request throttling if needed
6. **Monitor costs**: Track API usage and costs
7. **Rotate keys**: Monthly rotation is recommended

---

## Troubleshooting

### Gemini Not Enabled
```python
from routemaster_agent.ai.gemini_client import GeminiClient

client = GeminiClient()
if not client.enabled:
    print("ERROR: Gemini not enabled")
    print("Solution: Add GEMINI_API_KEY1-5 to .env file")
```

### All Keys Rate Limited
```python
# This shouldn't happen with 5 keys, but if it does:
# 1. Check API usage at Google AI Studio
# 2. Verify keys are valid and have quota
# 3. Implement request throttling
# 4. Consider implementing caching

# Check key status
from routemaster_agent.ai.gemini_client import GeminiClient
client = GeminiClient()
print(f"Keys available: {len(client.api_keys)}")
print(f"Current key index: {client.current_key_index}")
```

---

## Next Steps

1. ✅ Run `python test_gemini_setup.py` to verify setup
2. ✅ Try one of the examples above
3. ✅ Integrate into your RouteMaster Agent code
4. ✅ Monitor API usage at Google AI Studio
5. ✅ Implement caching for frequently used analyses

---

## Support

- Check logs: Look for DEBUG messages showing key usage
- Test setup: `python test_gemini_setup.py`
- Read guides: See `GEMINI_API_SETUP.md` for detailed info
- API docs: Visit [Google Gemini API](https://ai.google.dev/)

---

**Ready to analyze webpages with AI!** 🚀
