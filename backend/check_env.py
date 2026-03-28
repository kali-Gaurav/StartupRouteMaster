import os
from dotenv import load_dotenv

load_dotenv()

def check(name, env_var):
    val = os.getenv(env_var)
    if not val:
        print(f"❌ {name} ({env_var}) is NOT SET.")
    else:
        print(f"✅ {name} ({env_var}) is SET.")
        if env_var == "REDIS_URL":
            if "@" not in val and ":" in val[9:]: # redis://...
                 print("  ⚠️ REDIS_URL seems to lack authentication credentials.")
            if "upstash.io" in val and not val.startswith("rediss://"):
                 print("  ⚠️ REDIS_URL for Upstash should start with rediss:// (SSL).")

check("Supabase URL", "SUPABASE_URL")
check("Supabase Key", "SUPABASE_SERVICE_ROLE_KEY")
check("Redis URL", "REDIS_URL")
check("R2 Account ID", "CLOUDFLARE_R2_ACCOUNT_ID")
check("R2 S3 API", "CLOUDFLARE_R2_S3_API")
check("R2 Key ID", "CLOUDFLARE_R2_ACCESS_KEY_ID")
