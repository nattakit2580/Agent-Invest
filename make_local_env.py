"""
Generate backend/.env for local runs (SQLite, no Postgres required).

Only runs when backend/.env does not exist yet. Copies backend/.env.example
and overrides two keys so the app works out of the box on any machine:

  DATABASE_URL  -> local SQLite file (the example ships a Postgres URL,
                   which requires a running Postgres server)
  RAG_ENABLED   -> false (RAG similarity search uses a pgvector-only SQL
                   operator that does not exist in SQLite; the `pgvector`
                   Python package is installed regardless of DB engine, so
                   the app's own fallback check does not catch this case)

Everything else (API keys, Telegram tokens, feature flags) is left blank /
as shipped in .env.example, unchanged.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_PATH = os.path.join(HERE, "backend", ".env.example")
ENV_PATH = os.path.join(HERE, "backend", ".env")

OVERRIDES = {
    "DATABASE_URL": "sqlite:///./agent_invest.db",
    "RAG_ENABLED": "false",
}


def main() -> None:
    if os.path.isfile(ENV_PATH):
        print("backend/.env already exists, leaving it as-is.")
        return

    with open(EXAMPLE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    seen = set()
    for line in lines:
        stripped = line.rstrip("\n")
        key = stripped.split("=", 1)[0] if "=" in stripped and not stripped.startswith("#") else None
        if key in OVERRIDES:
            out.append(f"{key}={OVERRIDES[key]}\n")
            seen.add(key)
        else:
            out.append(line)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(out)

    print("Created backend/.env for local SQLite mode.")
    print("  DATABASE_URL -> sqlite:///./agent_invest.db (no Postgres needed)")
    print("  RAG_ENABLED  -> false (RAG needs Postgres/pgvector; disabled for local SQLite runs)")
    print("Edit backend/.env and set OPENROUTER_API_KEY to enable AI analysis.")


if __name__ == "__main__":
    main()
