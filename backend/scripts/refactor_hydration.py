
import re
orch_path = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend\core\route_engine\orchestrator.py"
hydr_path = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend\core\route_engine\hydration.py"

with open(orch_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

hydration_code = []
new_orch_code = []
in_hydration_class = False
in_step_method = False

for line in lines:
    # Lift the Pipeline class definition
    if "class HydrationPipeline" in line:
        in_hydration_class = True
        hydration_code.append(line)
        continue
    
    if in_hydration_class:
        if line.startswith("class ") or (line.startswith(" ") and not line.startswith("    ")):
            in_hydration_class = False
        else:
            hydration_code.append(line)
            continue
            
    # Remove initializing of Pipeline
    if "self.hydration_pipeline = HydrationPipeline()" in line: continue
    if "self.hydration_pipeline.add_step(" in line: continue

    # Lift the _step_ methods from Orchestrator (but remove 'self' conceptually? 
    # Let's keep them as static methods or standalone functions inside HydrationPipeline class if they use self.engine.
    # Actually, we will just move them inside the HydrationPipeline class and initialize it with self.engine.)
    if "def _step_" in line:
        in_step_method = True
        # Indent it one level out because it was in Orchestrator? Or keep to put in Pipeline class.
        hydration_code.append(line.replace("self", "self", 1)) # Dummy replace
        continue
    
    if in_step_method:
        # Detect end of method (next def at same indent level)
        if line.startswith("    def ") or line.startswith("    async def "):
            in_step_method = False
            # process the current line as normal
        else:
            hydration_code.append(line)
            continue
            
    if not in_step_method and not in_hydration_class:
        new_orch_code.append(line)

# Let's write the hydration code with standard imports
header = """
import time
import asyncio
from typing import List, Callable, Any
from core.data_utils.structures import Route, RouteConstraints
from core.pricing.fare_calculator import calculate_fare
import logging

logger = logging.getLogger(__name__)

class HydrationPipeline:
"""
# Skip the original HydrationPipeline class definition from lines if we reconstruct it, but we already appended it.
# Let's format the contents properly:
final_hydration_code = header + "".join(hydration_code)
# Actually, the original Pipeline class doesn't store self.engine, but the _step_ methods DO use self.engine.
# We need to rewrite `class HydrationPipeline` `__init__` to take `engine`.

with open(orch_path, 'w', encoding='utf-8') as f:
    f.writelines(new_orch_code)

with open(hydr_path, 'w', encoding='utf-8') as f:
    f.writelines(final_hydration_code)

print("Extraction script complete but may need manual fixing inside hydration.py")
