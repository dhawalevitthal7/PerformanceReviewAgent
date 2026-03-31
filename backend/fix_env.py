"""
Fix .env file by ensuring DATABASE_URL is properly formatted.
This script removes any 'psql ' prefix and extra quotes from DATABASE_URL.
"""
import os
import re
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

def fix_env_file():
    """Fix the .env file DATABASE_URL."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    
    if not os.path.exists(env_path):
        # Copy from .env.example if it exists; otherwise print guidance only.
        example_path = os.path.join(os.path.dirname(__file__), ".env.example")
        if os.path.exists(example_path):
            import shutil
            shutil.copy(example_path, env_path)
            print("[OK] .env created from .env.example — fill in your real values before running.")
        else:
            print(
                "[ERROR] .env file not found.\n"
                "Create backend/.env based on backend/.env.example and fill in:\n"
                "  DATABASE_URL  — your PostgreSQL / SQLite connection string\n"
                "  SECRET_KEY    — a strong random string\n"
                "  AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT  — from Azure portal\n"
            )
        return
    
    print("Reading existing .env file...")
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    lines = content.split("\n")
    fixed_lines = []
    fixed = False
    
    for line in lines:
        if line.startswith("DATABASE_URL="):
            # Extract the URL part after =
            url_part = line.split("=", 1)[1].strip()
            original_url = url_part
            
            # Remove surrounding quotes if present (both double and single)
            url_part = url_part.strip('"').strip("'").strip()
            
            # Remove 'psql ' prefix if present (check after removing quotes)
            if url_part.startswith("psql "):
                url_part = url_part[5:].strip()
                fixed = True
            
            # Remove any remaining quotes
            url_part = url_part.strip('"').strip("'").strip()
            
            # Check if we made any changes
            if original_url != url_part:
                fixed = True
            
            # Ensure it starts with postgresql://
            if not url_part.startswith("postgresql://"):
                print(f"Warning: DATABASE_URL doesn't start with postgresql://")
                print(f"  Found: {url_part[:50]}...")
            
            fixed_lines.append(f"DATABASE_URL={url_part}")
        else:
            fixed_lines.append(line)
    
    if fixed:
        print("Fixing DATABASE_URL (removing 'psql ' prefix and quotes)...")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(fixed_lines))
        print("[OK] .env file fixed successfully!")
    else:
        print("[OK] .env file is already correctly formatted.")
    
    # Verify the URL
    print("\nVerifying DATABASE_URL format...")
    for line in fixed_lines:
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip()
            if url.startswith("postgresql://"):
                print(f"[OK] DATABASE_URL is correctly formatted")
                print(f"  URL: {url[:60]}...")
            else:
                print(f"[ERROR] DATABASE_URL format is incorrect")
                print(f"  Found: {url[:60]}...")

if __name__ == "__main__":
    fix_env_file()
