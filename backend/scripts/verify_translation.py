import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.translator import MultiLingualBridge

def test_translation():
    print("--- Multi-lingual Translation Verification ---")
    
    # 1. Test Hindi to English
    hindi_msg = "मुझे मुंबई के लिए ट्रेन चाहिए"
    print(f"\n[Test 1] Translating: '{hindi_msg}'")
    en_text, lang = MultiLingualBridge.detect_and_translate(hindi_msg)
    print(f"Detected Lang: {lang}")
    print(f"Translated (EN): {en_text}")
    
    if lang == "hi" and ("mumbai" in en_text.lower() or "train" in en_text.lower()):
        print("[PASS] Hindi detected and correctly translated.")
    else:
        print("[FAIL] Hindi detection or translation error.")

    # 2. Test English to Hindi (Back-translation)
    en_reply = "I found 5 trains for Mumbai Central today."
    print(f"\n[Test 2] Translating back: '{en_reply}' to '{lang}'")
    hi_reply = MultiLingualBridge.translate_to(en_reply, lang)
    print(f"Translated (HI): {hi_reply}")
    
    if hi_reply != en_reply:
        print("[PASS] Reply successfully translated back.")
    else:
        print("[FAIL] Reply translation failed.")

if __name__ == "__main__":
    test_translation()
