# 🛡️ RouteMaster: End-to-End SOS & Passenger Safety Pipeline (50 Tasks)

This document outlines the ultra-specific, high-priority 50 tasks required to build a world-class, 24/7 autonomous emergency response system for Indian Railways.

---

## 📡 Phase 1: Multi-Modal Triggering & Ingestion (10 Tasks)
*Goal: Allow passengers to trigger an SOS in any situation, using any medium, even with low connectivity.*

1. **One-Tap Widget Integration**: Finalize the global red SOS floating action button across all frontend pages.
2. **Offline SMS Trigger Parser**: Build a webhook to receive offline SOS SMS payloads and inject them into the active SOS queue.
3. **Voice-Activated SOS (Wake Word)**: Integrate continuous background listening for a safe word (e.g., "Help Diksha") to trigger SOS without touching the phone.
4. **WhatsApp/Telegram Bot Trigger**: Allow users to trigger SOS by sending a specific emoji (🆘) or keyword to our official WhatsApp/Telegram bots.
5. **Silent Photo/Video Capture**: When SOS is triggered, secretly capture 3 front/back camera frames and 5 seconds of audio to provide context to responders.
6. **Multi-lingual Distress NLP**: Train an NLP model to detect panic or distress in text/voice chats (e.g., "koi mera bag chheen raha hai") and auto-escalate to SOS.
7. **Hardware Button Integration**: Allow SOS trigger via volume-button sequences (e.g., pressing Volume Up + Down simultaneously 3 times) using Android native APIs.
8. **Wearable Integration (Smartwatches)**: Build a lightweight companion app for Apple Watch / WearOS for wrist-based SOS triggering.
9. **Zero-Connectivity Bluetooth Mesh**: If no cellular network is available, broadcast SOS via Bluetooth Low Energy (BLE) to nearby RouteMaster users to relay the message.
10. **False-Alarm Mitigation Protocol**: Implement a 10-second cancel window with haptic feedback to prevent accidental triggers.

---

## 🧠 Phase 2: Autonomous Intelligence & Routing (10 Tasks)
*Goal: Instantly understand the crisis and route it to the exact right authority.*

11. **Threat Classification Engine (AI)**: Use LLMs to classify the SOS into categories: Medical, Theft, Harassment, Derailment, or Fire based on context/audio.
12. **Nearest Authority Geofencing**: Build a spatial query to find the nearest RPF post, GRP station, or partnered hospital based on live train coordinates.
13. **Live Train Synchronization**: Map the passenger's live GPS to the exact train coach and current track segment.
14. **Automated RPF Dispatch**: Auto-generate an official complaint payload and route it to the RailMadad / RPF API system automatically.
15. **Medical Emergency Protocol**: If medical, automatically query the upcoming station's facilities to check for ambulance availability and notify the Station Master.
16. **High-Risk Passenger Profiling**: Cross-reference the passenger with our `profiles` table to pull critical medical data (blood type, allergies) or vulnerability status (solo female traveler).
17. **Dynamic Escalation Matrix**: If a Level 1 responder doesn't acknowledge within 60 seconds, auto-escalate to Level 2 (Regional Admin) and Level 3 (National HQ).
18. **Crowdsourced Responder Ping**: Alert trusted/verified RouteMaster users traveling in the same train or adjacent coaches to assist immediately.
19. **Predictive Connectivity Buffer**: If the train is approaching a dead zone, preemptively download local police station contacts to the user's device.
20. **Priority Network QoS**: (Future) Partner with telcos to give SOS data packets highest QoS routing.

---

## 🎧 Phase 3: 24/7 Automated Call Center & Empathy Layer (10 Tasks)
*Goal: Establish immediate human-like contact to calm the passenger and gather info.*

21. **Instant Callback Webhook (Twilio/Exotel)**: Within 5 seconds of an SOS, our system automatically initiates a phone call to the passenger.
22. **AI Voice Agent (Vapi.ai / ElevenLabs)**: Deploy an empathetic AI voice bot that speaks in the user's native language to assess the situation ("Aap theek hain? Humne police ko inform kar diya hai").
23. **Call Recording & Transcription**: Record the entire emergency call and stream real-time transcription to the Admin Dashboard.
24. **Keyword Extraction from Call**: Real-time extraction of entities (e.g., "Coach S4", "Bleeding", "Knife") from the audio stream to update the crisis level.
25. **Conference Call Bridging**: Automatically patch in the nearest RPF officer or a human doctor into the active AI call.
26. **Silent Mode Chat Interface**: If the user drops the call or cannot speak, immediately switch to a specialized covert WhatsApp/Telegram chat.
27. **Periodic Status Check-Ins**: Post-incident, auto-schedule SMS or WhatsApp pings every 15 minutes asking "Are you safe now?" until marked resolved.
28. **Family Emergency Broadcast**: Auto-dial the user's saved emergency contacts, playing an AI voice message with live tracking instructions.
29. **Emotional State Analysis**: Analyze vocal pitch and tone during the call to assess panic levels and prioritize dashboard visibility.
30. **Human Handover Protocol**: Seamlessly hand over the AI call to a human support agent when complex intervention is needed.

---

## 🖥️ Phase 4: Developer Ops Dashboard (God Mode) (10 Tasks)
*Goal: A single pane of glass for you (the admin) to monitor, manage, and resolve all incidents globally.*

31. **Real-time Incident Map**: A full-screen Mapbox/Leaflet UI showing all active trains and pulsing red dots for active SOS alerts.
32. **Incident Triage Queue**: A Kanban-style board (New, Active, Responding, Resolved, Inactive) for SOS events.
33. **Live Passenger Telemetry View**: Click on an incident to see live GPS, speed, battery level, network strength, and exact coach position.
34. **Live Audio/Transcript Feed**: A panel to listen to the live AI call or read the real-time transcription.
35. **One-Click Authority Dispatch**: Buttons to instantly trigger police, ambulance, or railway staff dispatch directly from the dashboard.
36. **Direct Secure Chat**: A chat window to communicate directly with the passenger, bypassing the AI.
37. **Alert List & Ban Management**: Ability to flag abusive users, ban false-alarm accounts, or mark specific PNRs as "High Alert".
38. **Audit Trail & Playback**: A DVR-style playback feature to review the timeline of an incident (when triggered, when called, when resolved) for legal compliance.
39. **Admin Push Notifications**: High-priority push notifications and loud sirens on the admin's desktop/phone when a critical SOS arrives.
40. **Resolution & Reporting module**: Form to generate post-incident reports (PDF) for railway authorities or legal records.

---

## 🛡️ Phase 5: Resilience, Legal & Compliance Verification (10 Tasks)
*Goal: Ensure the system never fails and complies with data protection laws.*

41. **Multi-Region Database Failover**: Ensure `transit_graph.db` and SOS queues have real-time replicas to prevent downtime during an emergency.
42. **End-to-End Encryption**: Encrypt all captured audio, photos, and medical profiles at rest using AES-256.
43. **Data Retention Policies**: Automatically purge non-critical audio/video recordings after 72 hours to comply with DPDP Act.
44. **Chaos Engineering (SOS Injection)**: Create scripts that inject 1000 simultaneous fake SOS alerts to test dashboard lag and call center capacity.
45. **Telecom Gateway Redundancy**: Implement fallback between Twilio, Exotel, and RouteMobile if one SMS/Voice gateway goes down.
46. **Consent & Privacy Prompts**: Ensure legally binding consent is captured during "Guardian Mode" activation for continuous tracking.
47. **Automated System Health Pings**: A cron job that triggers a silent, simulated SOS every hour to ensure the entire pipeline is responsive.
48. **Offline Map Caching**: Ensure the admin dashboard caches map tiles so tracking continues even if external map APIs fail.
49. **Action Accountability Logs**: Log every action taken by the admin (e.g., "Admin X clicked Dispatch Police") with timestamps.
50. **Public Safety KPI Dashboard**: A public-facing (sanitized) dashboard showing metrics like "Average Response Time: 3 mins" to build trust.
