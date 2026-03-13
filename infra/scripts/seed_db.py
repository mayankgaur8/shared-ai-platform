"""
Database Seed Script
Inserts default data needed to run the platform:
- Default admin user
- Core app registrations (EduAI, Interview Prep, Resume Builder, Health, Astrology)
- Default Ollama model provider + llama3.2 model
- All global prompt templates
- Default safety policies per app
"""
import asyncio
import uuid
import hashlib
import secrets
from datetime import datetime

# Minimal standalone seed — runs outside FastAPI app context
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")


async def seed():
    conn = await asyncpg.connect(DATABASE_URL)

    print("Seeding database...")

    # ── Admin User ──────────────────────────────────────────────────────────
    admin_id = str(uuid.uuid4())
    admin_email = "admin@saib.local"
    # In production use passlib. This is seed-only.
    hashed_pw = hashlib.sha256(b"admin123").hexdigest()

    await conn.execute("""
        INSERT INTO users (id, email, username, full_name, hashed_password, tier, is_admin)
        VALUES ($1, $2, 'admin', 'Platform Admin', $3, 'enterprise', true)
        ON CONFLICT (email) DO NOTHING
    """, admin_id, admin_email, hashed_pw)
    print(f"  ✓ Admin user: {admin_email}")

    # ── Ollama Provider ─────────────────────────────────────────────────────
    provider_id = str(uuid.uuid4())
    await conn.execute("""
        INSERT INTO model_providers (id, name, display_name, base_url, is_active)
        VALUES ($1, 'ollama', 'Ollama (Local)', 'http://ollama:11434', true)
        ON CONFLICT (name) DO NOTHING
    """, provider_id)

    # Fetch actual provider id (may already exist)
    provider_id = await conn.fetchval("SELECT id FROM model_providers WHERE name='ollama'")

    # ── Ollama Models ───────────────────────────────────────────────────────
    models = [
        ("llama3.2", "Llama 3.2 (3B)", "chat", 8192, ["fast", "chat", "instruction", "general"], True),
        ("llama3.1:8b", "Llama 3.1 (8B)", "chat", 32768, ["reasoning", "instruction", "long_context"], False),
        ("mistral", "Mistral 7B", "chat", 8192, ["fast", "instruction", "general"], False),
        ("nomic-embed-text", "Nomic Embed Text", "embedding", 8192, ["embedding"], False),
    ]

    for model_name, display, mtype, ctx, tags, is_default in models:
        model_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO model_registry
                (id, provider_id, model_name, display_name, model_type, context_window,
                 capability_tags, is_active, is_default, supports_streaming)
            VALUES ($1, $2, $3, $4, $5, $6, $7, true, $8, true)
            ON CONFLICT (provider_id, model_name) DO NOTHING
        """, model_id, provider_id, model_name, display, mtype, ctx, tags, is_default)
    print("  ✓ Ollama models registered")

    # ── Apps ─────────────────────────────────────────────────────────────────
    apps_data = [
        ("eduai",          "EduAI Platform",      "AI-powered education tools"),
        ("interview_prep", "Interview Prep",       "Interview preparation and mock interviews"),
        ("resume_builder", "Resume Builder",       "ATS resume analysis and optimization"),
        ("health_assist",  "Health Assistant",     "General health information chatbot"),
        ("astrology_app",  "Astrology App",        "Personalized astrology insights"),
    ]

    default_model_id = await conn.fetchval(
        "SELECT id FROM model_registry WHERE model_name='llama3.2' LIMIT 1"
    )

    app_ids = {}
    for app_name, display, desc in apps_data:
        app_id = str(uuid.uuid4())
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        await conn.execute("""
            INSERT INTO apps (id, name, display_name, description, api_key_hash, is_active, created_by)
            VALUES ($1, $2, $3, $4, $5, true, $6)
            ON CONFLICT (name) DO NOTHING
        """, app_id, app_name, display, desc, api_key_hash, admin_id)

        real_app_id = await conn.fetchval("SELECT id FROM apps WHERE name=$1", app_name)
        app_ids[app_name] = real_app_id

        await conn.execute("""
            INSERT INTO app_configs
                (id, app_id, default_model_id, max_tokens_per_request, rate_limit_rpm,
                 memory_enabled, rag_enabled)
            VALUES ($1, $2, $3, 4096, 60, true, false)
            ON CONFLICT (app_id) DO NOTHING
        """, str(uuid.uuid4()), real_app_id, default_model_id)

        print(f"  ✓ App registered: {app_name}  (API key printed once: {api_key[:12]}...)")

    # ── Safety Policies ──────────────────────────────────────────────────────
    # Health app gets strict policy
    health_policy_id = str(uuid.uuid4())
    import json
    health_rules = json.dumps([
        {"type": "topic_block", "topics": ["drug_synthesis", "self_harm_methods"], "action": "block"},
        {"type": "always_add_disclaimer", "disclaimer_key": "medical_advice"}
    ])
    health_disclaimers = json.dumps([
        {"trigger": "always", "text": "This information is for general wellness purposes only. Please consult a qualified healthcare professional for medical advice, diagnosis, or treatment."}
    ])
    await conn.execute("""
        INSERT INTO safety_policies
            (id, app_id, name, rules, blocked_topics, required_disclaimers,
             injection_detection_enabled, output_moderation_enabled, severity_threshold, action_on_flag, is_active, created_by)
        VALUES ($1, $2, 'health_strict_policy', $3::jsonb, $4, $5::jsonb, true, true, 'low', 'block', true, $6)
        ON CONFLICT DO NOTHING
    """, health_policy_id, app_ids.get("health_assist"), health_rules,
        ["drug_synthesis", "self_harm", "suicide_methods", "dangerous_medical_advice"],
        health_disclaimers, admin_id)

    # Astrology app disclaimer policy
    astro_policy_id = str(uuid.uuid4())
    astro_rules = json.dumps([{"type": "always_add_disclaimer", "disclaimer_key": "entertainment"}])
    astro_disclaimers = json.dumps([
        {"trigger": "always", "text": "Astrology readings are for entertainment and self-reflection purposes only."}
    ])
    await conn.execute("""
        INSERT INTO safety_policies
            (id, app_id, name, rules, blocked_topics, required_disclaimers,
             injection_detection_enabled, severity_threshold, action_on_flag, is_active, created_by)
        VALUES ($1, $2, 'astrology_disclaimer_policy', $3::jsonb, $4, $5::jsonb, true, 'medium', 'warn', true, $6)
        ON CONFLICT DO NOTHING
    """, astro_policy_id, app_ids.get("astrology_app"), astro_rules,
        ["financial_decisions_based_on_astrology"], astro_disclaimers, admin_id)

    print("  ✓ Safety policies created")

    await conn.close()
    print("\n✅ Database seeding complete!")
    print("   Default admin login: admin@saib.local / admin123")
    print("   (Change password immediately in production!)")


if __name__ == "__main__":
    asyncio.run(seed())
