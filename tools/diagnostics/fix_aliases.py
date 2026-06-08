with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the incomplete aliases section
if 'BACKWARD COMPATIBILITY ALIASES' in content:
    # Find and remove the aliases section
    start = content.find('# ==============================================================================')
    if start >= 0:
        content = content[:start]
        with open('backend/database/models.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print('Removed incomplete aliases')
else:
    print('No aliases found')