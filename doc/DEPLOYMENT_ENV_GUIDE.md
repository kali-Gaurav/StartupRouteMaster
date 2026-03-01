# 🚀 RouteMaster Environment Variable Guide

To ensure security and prevent leaks, follow this separation strictly.

## 🟢 Frontend (Browser-Safe)
**Where to put them:** Vercel Dashboard -> Project Settings -> Environment Variables.
**Prefix:** Must start with `VITE_`.

| Variable | Description |
|----------|-------------|
| `RAILWAY_BACKEND_URL` | The URL of your **Railway** backend (e.g. `https://xxx.up.railway.app`) |
| `VITE_SUPABASE_URL` | Your Supabase Project URL |
| `VITE_SUPABASE_ANON_KEY` | Your Supabase **Anon/Public** Key |
| `VITE_VAPID_PUBLIC_KEY` | Public key for Push Notifications |

---

## 🔴 Backend (Secret - DO NOT EXPOSE)
**Where to put them:** Railway Dashboard -> Service Settings -> Variables.
**Prefix:** None.

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase Postgres Connection String (Session/Transaction mode) |
| `REDIS_URL` | Upstash or Railway Redis connection string |
| `SUPABASE_KEY` | Your Supabase **Service Role** Key (Admin access) |
| `OPENROUTER_API_KEY` | AI Key for Diksha Assistant |
| `RAPIDAPI_KEY` | Key for IRCTC/Train data |
| `VAPID_PRIVATE_KEY` | Private key for Push Notifications |

---

## 🛠️ How to generate VAPID keys?
If you haven't generated them yet, run this in your terminal:
```bash
npx web-push generate-vapid-keys
```
Put the **Public** key in Frontend and **Private** key in Backend.

## ⚠️ Critical Security Warning
- **NEVER** put `SUPABASE_KEY` (Service Role) or `DATABASE_URL` in a file starting with `VITE_`.
- If you leak the `DATABASE_URL` to the frontend, anyone can delete your whole database.
