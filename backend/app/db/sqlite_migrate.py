"""
One-off database fixes for dev databases created before UserRole.ceo was added.

SQLite: legacy CHECK constraint rebuild.
PostgreSQL: ALTER TYPE userrole ADD VALUE 'ceo' if missing.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _migrate_pg_userrole_enum(engine: Engine) -> None:
    """
    Add 'ceo' to the native PostgreSQL userrole enum if it is absent.
    Safe to call multiple times — skips if the value already exists.
    """
    with engine.begin() as conn:
        # Check whether the native enum type exists at all
        type_exists = conn.execute(
            text("SELECT 1 FROM pg_type WHERE typname = 'userrole'")
        ).fetchone()
        if not type_exists:
            return

        # Check whether 'ceo' is already a member
        ceo_exists = conn.execute(
            text(
                "SELECT 1 FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'userrole' AND e.enumlabel = 'ceo'"
            )
        ).fetchone()
        if ceo_exists:
            return

        print("[MIGRATE] Adding 'ceo' to PostgreSQL enum type userrole…")
        conn.execute(text("ALTER TYPE userrole ADD VALUE 'ceo'"))
        print("[MIGRATE] userrole enum updated.")


def migrate_sqlite_profiles_role_if_needed(engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        _migrate_pg_userrole_enum(engine)
        return

    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='profiles'")
        ).fetchone()
        if not row:
            return

        # ── Step 1: add missing columns (ALTER TABLE ADD COLUMN is safe to run ──
        # multiple times only if we guard with PRAGMA first).
        existing_cols = {
            r[1] for r in conn.execute(text("PRAGMA table_info(profiles)")).fetchall()
        }
        missing_cols = {
            "department_id": "VARCHAR REFERENCES departments(id)",
            "is_setup_done": "BOOLEAN NOT NULL DEFAULT 0",
        }
        for col, col_def in missing_cols.items():
            if col not in existing_cols:
                print(f"[MIGRATE] SQLite profiles: adding missing column '{col}'…")
                conn.execute(text(f'ALTER TABLE profiles ADD COLUMN "{col}" {col_def}'))

        # ── Step 2: rebuild table only if there is a legacy role CHECK constraint ──
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='profiles'")
        ).scalar() or ""

        needs_rebuild = (
            "check" in ddl.upper()
            and "ceo" not in ddl.lower()
        )
        if not needs_rebuild:
            return

        print(
            "[MIGRATE] SQLite table `profiles` has a legacy role CHECK. "
            "Rebuilding table so 'ceo' and string roles work…"
        )

        cols = conn.execute(text("PRAGMA table_info(profiles)")).fetchall()
        col_parts: list[str] = []
        select_parts: list[str] = []
        col_names: list[str] = []

        for _cid, name, col_type, notnull, _dflt_value, pk in cols:
            col_names.append(f'"{name}"')
            ctype = "VARCHAR(32)" if name == "role" else (col_type or "TEXT")
            nn = " NOT NULL" if notnull else ""
            pkc = " PRIMARY KEY" if pk else ""
            col_parts.append(f'"{name}" {ctype}{nn}{pkc}')

            if name == "role":
                select_parts.append(
                    """CASE "role"
                        WHEN 'EMPLOYEE' THEN 'employee'
                        WHEN 'MANAGER' THEN 'manager'
                        WHEN 'CEO' THEN 'ceo'
                        ELSE COALESCE("role", 'employee') END"""
                )
            else:
                select_parts.append(f'"{name}"')

        conn.execute(text(f'CREATE TABLE profiles__new ({", ".join(col_parts)})'))
        dest_cols = ", ".join(col_names)
        src_sel = ", ".join(select_parts)
        conn.execute(
            text(f"INSERT INTO profiles__new ({dest_cols}) SELECT {src_sel} FROM profiles")
        )
        conn.execute(text("DROP TABLE profiles"))
        conn.execute(text("ALTER TABLE profiles__new RENAME TO profiles"))
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_profiles_user_id ON profiles (user_id)")
        )

    print("[MIGRATE] profiles table updated successfully.")
