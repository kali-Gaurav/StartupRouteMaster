import os

def force_update_db_url(file_path):
    if not os.path.exists(file_path):
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    found = False
    new_url = "DATABASE_URL=postgresql+psycopg2://postgres:[YOUR_PASSWORD]@[YOUR_HOST]:6543/postgres
"
    
    for line in lines:
        if line.strip().startswith("DATABASE_URL="):
            new_lines.append(new_url)
            found = True
        else:
            new_lines.append(line)
            
    if not found:
        new_lines.append(new_url)
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Forced update of {file_path}")

if __name__ == "__main__":
    force_update_db_url('backend/.env')
    force_update_db_url('.env')
