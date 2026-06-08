import os

def replace_in_file(file_path, search_text, replace_text):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if search_text in content:
            new_content = content.replace(search_text, replace_text)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Fixed: {file_path}")
            return True
    except Exception as e:
        print(f"Error in {file_path}: {e}")
    return False

def main():
    root_dir = r"c:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend"
    search_text = "core.resilience.retry"
    replace_text = "core.resilience.retry"
    
    count = 0
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if replace_in_file(file_path, search_text, replace_text):
                    count += 1
    
    print(f"Finished. Replaced in {count} files.")

if __name__ == "__main__":
    main()
