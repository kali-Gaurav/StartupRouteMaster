# /innovate - NeuralForge Innovation Protocol

Use this workflow to prototype high-value, "Next-Gen" features in the **Innovation Lab** without touching production code.

## 🧪 Phase 1: Ideation (ARIA & MARCO)
1. **ARIA (CEO)**: Analyze the `master_experience.json` and the current `core_brain.graphml`.
2. **Identify Gaps**: Find a feature that doesn't exist but would provide 10x value (e.g., Predictive Routing, Crypto-Ticket, AR-Navigation).
3. **Draft the "Vibe"**: Write a one-page vision document in `.agent/lab/vision.md`.

## 🏗️ Phase 2: Feasibility (NEXUS)
1. **NEXUS (CTO)**: Run a `get_context` on the core brain for the targeted area.
2. **Audit**: Ensure the new idea can eventually be integrated.
3. **Constraints**: Define the "Safe Sandbox" limits for the prototype.

## 🛠️ Phase 3: Prototyping (Innovation Swarm)
1. **Generate**: Create a standalone folder in `.agent/lab/prototypes/[feature_name]/`.
2. **Code**: Write the MVP code. Use Mocks for external dependencies.
3. **DO NOT**: Modify any files outside of the `.agent/lab/` directory.

## 🎤 Phase 4: The Pitch
1. **Report Back**: Create a `PROTOTYPE_PITCH.md` in the lab folder.
2. **Founder Review**: Tag the Founder for a "Go/No-Go" decision.
3. **Integration Plan**: If approved, move to the `autonomous_dev` workflow for production integration.

---
// turbo-all
