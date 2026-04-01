import sys

fname = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend\core\route_engine\orchestrator.py"
with open(fname, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # Fix the extra 16 spaces indentation added at line 680
    # Between lines 680 and 738
    if 680 <= (i + 1) <= 738:
        if line.startswith(" " * 32):
            new_lines.append(line[16:])
        elif line.startswith(" " * 16) and "async def wrapped_search" in line:
            new_lines.append(line)
        else:
            if len(line) > 16 and not line.strip() == "":
                # Attempt heuristic deduplication of extra 16 spaces if they exist
                if line.startswith(" " * 32):
                    new_lines.append(line[16:])
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
    elif "temporal_tasks[t_name] = asyncio.create_task" in line and (i+1) == 819:
        # line 819 has extra spaces
        new_lines.append(" " * 39 + "temporal_tasks[t_name] = asyncio.create_task(wrapped_search(name, priority=5))\n")
    else:
        new_lines.append(line)

with open(fname, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Repaired indentation.")
