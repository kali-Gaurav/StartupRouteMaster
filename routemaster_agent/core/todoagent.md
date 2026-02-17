This is a very powerful idea — you are basically trying to build an autonomous web-navigation AI agent for railway workflows (IRCTC + NTES + AskDisha + enquiry sites).

What you want is NOT just scraping.

You want:

A vision-based decision agent that can see the screen → understand context → decide next action → click → scroll → extract → verify → store.

This is exactly the architecture used in:

OpenAI Operator-style agents

Browser automation AI (WebGPT / Adept / Claude Computer Use)

Autonomous UI agents (UI-TARS / SeeAct / CogAgent)

So your idea is correct and advanced.

Below is the complete system design + training strategy you should follow.

🚀 1. Core Objective of RouteMaster Agent

The agent must learn to perform jobs like:

Jobs

Train search between stations

Seat availability & fare extraction (IRCTC)

Train schedule scraping (NTES / enquiry)

Live running status verification

Platform number + delay detection

Ticket booking automation

Data validation between multiple sources

Scroll + navigation + dynamic UI handling

So this becomes a multi-task navigation AI.

🧠 2. High Level Architecture

You need 5 main modules:

                USER TASK
                   ↓
            Task Planner (LLM)
                   ↓
        Vision Understanding Model
                   ↓
         Action Decision Engine
                   ↓
      Browser / Mobile Controller Layer
                   ↓
         Data Extraction + Validation
                   ↓
                Database

🧩 3. Key Components You Must Build
3.1 Vision Understanding Module

Input:

Screenshot

UI hierarchy (optional DOM)

Cursor position

Task instruction

Output:

Detected elements (buttons, text, fields)

Bounding boxes

Semantic meaning

Example:

Detected:
Search Button → click
Date Field → input
Station Field → input
Train Cards → extract
Scroll Area → scroll


Use:

Gemini Vision

GPT-4.1 Vision

Qwen VL

Grounding DINO (optional)

3.2 Task Planning Model

Gemini will initially act as brain:

Input:

Task: Get seat availability Jaipur → Kota 18 Feb
Screen: Screenshot
History: previous steps


Output:

Step 1: Click origin field
Step 2: Enter JP
Step 3: Click destination
Step 4: Enter KOTA
Step 5: Select date
Step 6: Click search
Step 7: Scroll results
Step 8: Extract trains


Later you train your own model.

3.3 Action Controller Layer

This converts AI decisions into real actions.

Tools:

Web

Playwright ✅ best

Selenium

Puppeteer

Mobile

Appium

Android ADB

Desktop

PyAutoGUI

RobotJS

Example:

AI → Click at (x=540,y=320)
Controller → browser.click()

3.4 Memory + State System

Agent must remember:

Current page

Entered stations

Selected date

Scroll position

Extracted data

Errors encountered

Use:

Redis / SQLite / Vector DB

📊 4. Training Strategy Using Gemini (Important)

You DO NOT train from scratch initially.

You use Gemini as teacher model.

This is called:

Imitation Learning / Behavior Cloning

🧪 Phase 1 — Demonstration Collection

You manually perform tasks while recording:

Record:

Screenshot

Mouse coordinates

Keyboard input

Scroll events

Extracted text

DOM elements

Dataset example:

Step 1:
Screen: image.png
Action: click
Target: origin_field
Coordinates: (420,210)

Step 2:
Action: type
Text: JP


Tools to record:

Playwright tracing

Screen recorder + event logger

Custom Python logger

🧪 Phase 2 — Gemini Decision Labeling

Feed screenshots to Gemini:

Prompt:

You are training an automation agent.

Given this screen and task:
"Search trains from Jaipur to Kota"

What should be the next action?

Return:
{
action: click/type/scroll/extract
target: element description
reason: ...
}


Gemini produces labels.

You store:

(screen, instruction) → action


This becomes training dataset.

🧪 Phase 3 — Train Your Own Model

Later train:

Vision Transformer + Action head

Multimodal LLM fine-tune

Frameworks:

LLaVA

Qwen-VL

OpenVLA

RT-1 / RT-2 style

🤖 5. Action Space Definition (Very Important)

Define fixed actions:

CLICK(x,y)
TYPE(text)
SCROLL_UP
SCROLL_DOWN
WAIT
EXTRACT(region)
NAVIGATE(url)
SELECT(option)
VERIFY(text)


If actions are not standardized → training fails.

🧭 6. Screen Understanding Strategy

Agent must learn patterns like:

IRCTC Screen

Detect:

From field

To field

Date selector

Class dropdown

Quota dropdown

Search button

Train list cards

NTES Screen

Detect:

Train number input

Start date selector

Running status timeline

Delay badges

Platform number

📦 7. Data Extraction Pipeline

When train cards appear:

Agent must:

Detect each card boundary

OCR text

Parse fields

Example:

Train: SGNR JLWC EXP
Number: 22998
Dep: 05:15
Arr: 09:50
Duration: 4h35m
Classes:
SL: 215 REGRET
3E: 565 AVAILABLE-0002
3A: 565 AVAILABLE-0010


Convert to structured:

{
train_no: 22998,
source: JP,
dest: KOTA,
date: 2026-02-18,
classes: {
SL: {fare:215, status:"REGRET"},
3E: {fare:565, available:2}
}
}

🗄️ 8. Database Design

Tables:

trains
train_no
name
type

schedules
train_no
station_code
arrival
departure
day
distance

seat_availability
train_no
date
source
destination
class
availability
fare
timestamp

live_status
train_no
current_station
delay_minutes
platform
timestamp

🔎 9. Multi-Source Verification Logic

You want reliability.

So:

IRCTC → seat data
NTES → live status
Enquiry → schedule
AskDisha → cross verify


Agent compares values.

If mismatch → mark confidence low.

🧠 10. Learning Navigation Patterns

Agent must learn:

Scrolling

Detect:

Scroll bar presence

End of list

Lazy loading

Pagination

Detect:

Next button

Load more

Dynamic loading

Detect spinner → wait.

⚠️ 11. Error Handling Training

Agent must learn:

CAPTCHA detected

Session expired

Network error

Popup blocking

Login required

So include these cases in dataset.

🔐 12. Ticket Booking Automation

For booking you must handle:

Login

OTP

Passenger form

Payment redirect

Payment should remain manual for safety.

🧪 13. Reinforcement Learning Phase (Advanced)

After imitation training:

Reward signals:

+10 correct extraction
+20 successful search
+50 successful booking
-5 wrong click
-10 stuck state


Use RL to improve navigation efficiency.

⚙️ 14. Tech Stack Recommendation
Brain

Gemini API (initial teacher)

Later: Fine-tuned Qwen-VL / LLaVA

Automation

Playwright ✅ best choice

Vision

OCR: PaddleOCR / Tesseract

Detection: GroundingDINO (optional)

Backend

Python FastAPI

Database

PostgreSQL / Supabase

Memory

Redis

🧱 15. Training Dataset You Should Collect

Minimum:

Task	Samples
Train search	500
Seat availability	500
Live status	300
Schedule extraction	300
Booking flow	200
Error cases	200

Total ~2000 sequences.

🧭 16. Decision Loop of Final Agent

Final loop:

while task_not_done:

    screenshot = capture()

    perception = vision_model(screenshot)

    action = planner(perception, memory, task)

    execute(action)

    update_memory()

🧨 17. Biggest Mistakes to Avoid

❌ Training only on text
❌ Ignoring scrolling cases
❌ No error scenarios
❌ No state memory
❌ No multi-source verification
❌ No structured action space

⭐ 18. Very Important Insight

You are NOT training:

“Click this button”

You are training:

“Understand UI semantics and achieve goal”

This is called Goal-Conditioned UI Agent.

🚀 19. Suggested Development Phases
Phase 1

Gemini-controlled automation (no training yet)

Phase 2

Collect dataset

Phase 3

Train imitation model

Phase 4

Add reinforcement learning

Phase 5

Fully autonomous RouteMaster Agent

🔥 20. Future Superpower Features

Once trained:

Predict ticket confirmation probability

Suggest alternate trains

Predict delays

Auto plan journeys

Auto booking at Tatkal time

✅ 21. What You Should Do First (Action Plan)

Step 1:

Build Playwright automation skeleton.

Step 2:

Connect Gemini decision API.

Step 3:

Create action schema JSON.

Step 4:

Start recording demonstrations.