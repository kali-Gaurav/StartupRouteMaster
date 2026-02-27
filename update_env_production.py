import os

def update_env(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    found_db = False
    found_env = False
    found_offline = False

    # Template for Supabase Pooler
    # [YOUR_PASSWORD] should be replaced by the user
    # [YOUR_HOST] should be replaced by the user (usually aws-0-ap-south-1.pooler.supabase.com)
    db_url_template = "DATABASE_URL=postgresql+psycopg2://postgres:[YOUR_PASSWORD]@[YOUR_HOST]:6543/postgres\n"

    for line in lines:
        if line.strip().startswith('DATABASE_URL='):
            new_lines.append(db_url_template)
            found_db = True
        elif line.strip().startswith('ENVIRONMENT='):
            new_lines.append("ENVIRONMENT=production\n")
            found_env = True
        elif line.strip().startswith('OFFLINE_MODE='):
            new_lines.append("OFFLINE_MODE=false\n")
            found_offline = True
        else:
            new_lines.append(line)

    if not found_db:
        new_lines.append(db_url_template)
    if not found_env:
        new_lines.append("ENVIRONMENT=production\n")
    if not found_offline:
        new_lines.append("OFFLINE_MODE=false\n")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Updated {file_path}")

if __name__ == "__main__":
    update_env('backend/.env')
    update_env('.env')
