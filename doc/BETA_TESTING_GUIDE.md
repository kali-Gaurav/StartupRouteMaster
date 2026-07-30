# 🧪 Diksha AI Beta Testing Guide

Follow these scenarios to validate the depth of the new AI Assistant integration.

## 1. Scenario: Emotional Safety Intelligence
*   **Action**: Open chat and type "I feel scared and unsafe at this station".
*   **Expected Result**: Diksha should immediately respond with emotional empathy and ask to activate Guardian Mode or SOS.
*   **Validation**: Check if `chatbot_emotional_risk_detected` appears in the Dev Debug Panel.

## 2. Scenario: Hands-Free SOS (Voice)
*   **Action**: While the chatbot is closed, say "Hey Diksha".
*   **Expected Result**: The chatbot should open automatically with a chime.
*   **Validation**: Say "Delhi to Mumbai" and verify it triggers a search.

## 3. Scenario: Proactive Late-Night Protection
*   **Action**: Set your system clock to 11:30 PM and start a journey search.
*   **Expected Result**: Within 2 minutes of the journey being "active" in memory, Diksha should proactively suggest enabling Guardian Mode.
*   **Validation**: Check `chatbot_proactive_suggestion_shown` metric.

## 4. Scenario: Persistent Memory Sync
*   **Action**: Search for a route, then refresh the page.
*   **Expected Result**: Open Diksha and ask "What was my last search?".
*   **Validation**: Verify Diksha remembers the source/destination from the last session.

## 5. Scenario: Critical Action Confirmation
*   **Action**: Type "Trigger SOS" in the chat.
*   **Expected Result**: Diksha should NOT trigger SOS immediately but show "Yes, Proceed" and "Cancel" buttons.
*   **Validation**: Confirm the SOS trigger only happens after the second click.

---
**Founder Tip**: Monitor the **Diksha AI Analytics** dashboard during these tests to see real-time funnel conversion.
