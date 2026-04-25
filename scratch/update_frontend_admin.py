import os

# Define files to update
files = [
    "AdminAI.tsx",
    "AdminAudit.tsx",
    "AdminAuth.tsx",
    "AdminDashboard.tsx",
    "AdminFinance.tsx",
    "AdminGrowth.tsx",
    "AdminInventory.tsx",
    "AdminOperations.tsx",
    "AdminSettings.tsx",
    "AdminSystem.tsx"
]

pages_dir = "frontend/src/pages"

for fname in files:
    fpath = os.path.join(os.getcwd(), pages_dir, fname)
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace /admin/ with /v2/admin/
        # Using specific patterns to avoid over-replacing
        new_content = content.replace('fetchWithAuth("/admin/', 'fetchWithAuth("/v2/admin/')
        new_content = new_content.replace('fetchWithAuth(`/admin/', 'fetchWithAuth(`/v2/admin/')
        
        if new_content != content:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {fname}")
    else:
        print(f"Skipped: {fname} (Not found)")
