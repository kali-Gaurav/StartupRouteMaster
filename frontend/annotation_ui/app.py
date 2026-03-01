"""Annotation UI for verifying recorded scenes.

Streamlit app for human annotators to review and verify scene recordings.

Usage:
    streamlit run annotation_ui/app.py

Creates verified_examples.jsonl as output.
"""
import streamlit as st
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import base64


class AnnotationUI:
    def __init__(self, manifest_file: str = "datasets/labeling_manifest.jsonl", output_file: str = "datasets/verified_examples.jsonl"):
        self.manifest_file = Path(manifest_file)
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def load_manifest(self) -> List[Dict[str, Any]]:
        """Load all scenes from manifest."""
        scenes = []
        if self.manifest_file.exists():
            with open(self.manifest_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        scenes.append(json.loads(line))
        return scenes

    def load_verified(self) -> Dict[str, Dict[str, Any]]:
        """Load already-verified scenes."""
        verified = {}
        if self.output_file.exists():
            with open(self.output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        obj = json.loads(line)
                        verified[obj['scene_id']] = obj
        return verified

    def save_verified(self, scene_id: str, data: Dict[str, Any]):
        """Append verified scene to output file."""
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    def load_screenshot(self, path: str) -> Optional[str]:
        """Load image as base64."""
        try:
            p = Path(path)
            if p.exists():
                return base64.b64encode(p.read_bytes()).decode()
        except Exception:
            pass
        return None


def main():
    st.set_page_config(page_title="Scene Annotation", layout="wide")
    st.title("📋 Scene Annotation & Verification")

    annotator = AnnotationUI()
    scenes = annotator.load_manifest()
    verified = annotator.load_verified()

    st.sidebar.title("Status")
    st.sidebar.metric("Total Scenes", len(scenes))
    st.sidebar.metric("Verified", len(verified))
    st.sidebar.metric("Remaining", len(scenes) - len(verified))

    # Filter to unverified scenes
    unverified = [s for s in scenes if s['scene_id'] not in verified]

    if not unverified:
        st.success("✅ All scenes verified!")
        return

    # Scene selector
    col1, col2 = st.columns([3, 1])
    with col1:
        scene_ids = [s['scene_id'] for s in unverified]
        selected_idx = st.selectbox("Select Scene", range(len(scene_ids)), format_func=lambda i: scene_ids[i])
        scene = unverified[selected_idx]
    with col2:
        st.metric("Progress", f"{len(verified)}/{len(scenes)}", f"{int(100 * len(verified) / max(1, len(scenes)))}%")

    st.divider()

    # Display screenshot
    st.subheader("Screenshot")
    screenshot_path = scene.get('screenshot')
    if screenshot_path:
        b64 = annotator.load_screenshot(screenshot_path)
        if b64:
            st.image(f"data:image/png;base64,{b64}", use_column_width=True)
        else:
            st.warning("Could not load screenshot")

    st.divider()

    # Display steps (proposed actions)
    st.subheader("Proposed Actions")
    steps = scene.get('steps', [])

    if steps:
        # Summary table
        import pandas as pd
        step_data = []
        for s in steps:
            action = s.get('action', {})
            step_data.append({
                'Step': s.get('step'),
                'Type': action.get('type'),
                'Selector': action.get('selector', '')[:50],
                'Value': str(action.get('value', ''))[:20],
                'Strategy': s.get('meta', {}).get('strategy'),
                'Confidence': s.get('meta', {}).get('selector_confidence'),
                'Time (ms)': s.get('meta', {}).get('time_to_success_ms'),
            })
        df = pd.DataFrame(step_data)
        st.dataframe(df, use_container_width=True)

        # Step details
        with st.expander("Step Details"):
            for s in steps:
                with st.container():
                    action = s.get('action', {})
                    meta = s.get('meta', {})
                    st.write(f"**Step {s.get('step')}:** {action.get('type')} → {action.get('selector')}")
                    if action.get('value'):
                        st.write(f"  Value: `{action.get('value')}`")
                    st.write(f"  Strategy: {meta.get('strategy')} | Confidence: {meta.get('selector_confidence')} | Time: {meta.get('time_to_success_ms')}ms")
                    st.divider()

    else:
        st.warning("No steps recorded")

    st.divider()

    # Annotation controls
    st.subheader("Verification")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve", key=f"approve_{scene['scene_id']}", use_container_width=True):
            data = {
                'scene_id': scene['scene_id'],
                'status': 'approved',
                'steps': steps,
                'task': scene.get('task'),
                'screenshot': screenshot_path,
            }
            annotator.save_verified(scene['scene_id'], data)
            st.success("Scene approved!")
            st.rerun()

    with col2:
        if st.button("✏️ Edit & Approve", key=f"edit_{scene['scene_id']}", use_container_width=True):
            st.session_state.edit_mode = True
            st.rerun()

    with col3:
        if st.button("❌ Reject", key=f"reject_{scene['scene_id']}", use_container_width=True):
            data = {
                'scene_id': scene['scene_id'],
                'status': 'rejected',
                'reason': 'Manual rejection by annotator',
                'steps': steps,
                'task': scene.get('task'),
            }
            annotator.save_verified(scene['scene_id'], data)
            st.error("Scene rejected")
            st.rerun()

    # Edit mode
    if st.session_state.get('edit_mode'):
        st.divider()
        st.subheader("Edit Steps")
        st.info("Modify the JSON steps below if needed")

        edited_json = st.text_area("Steps JSON", value=json.dumps(steps, indent=2), height=300)
        try:
            edited_steps = json.loads(edited_json)
            if st.button("💾 Save & Approve", use_container_width=True):
                data = {
                    'scene_id': scene['scene_id'],
                    'status': 'approved_with_edits',
                    'steps': edited_steps,
                    'task': scene.get('task'),
                    'screenshot': screenshot_path,
                }
                annotator.save_verified(scene['scene_id'], data)
                st.success("Scene saved with edits!")
                st.session_state.edit_mode = False
                st.rerun()
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")


if __name__ == '__main__':
    main()
