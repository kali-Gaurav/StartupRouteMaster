import os, json
from datetime import datetime
from pathlib import Path
from routemaster_agent.intelligence import selector_registry

p = Path(r'C:/Users/Gaurav Nagar/AppData/Local/Temp/pytest-of-Gaurav Nagar/pytest-81/test_promotion_cooldown0/selector_registry.json')
print('exists', p.exists())
print('content before:')
print(p.read_text())
os.environ['RMA_SELECTOR_REGISTRY'] = str(p)
for i in range(10):
    selector_registry.record_selector_result('ntes_schedule','table.bad', False)
print('\ncontent after recordings:')
print(p.read_text())
print('\nevaluate_promotion returns:', selector_registry.evaluate_promotion('ntes_schedule'))
print('\ncontent after evaluate_promotion:')
print(p.read_text())
