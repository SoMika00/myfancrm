import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_DB_PATH = os.environ.get("MYFANCRM_DB_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "myfancrm.sqlite3",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                persona_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                bot_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE SET NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS script_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                step_type TEXT NOT NULL,
                title TEXT,
                script_text TEXT NOT NULL,
                media_desc TEXT,
                is_paywall INTEGER NOT NULL DEFAULT 0,
                price TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )

        # Migration légère (ajout colonne price)
        step_cols = {r["name"] for r in conn.execute("PRAGMA table_info(script_steps)")}
        if "price" not in step_cols:
            conn.execute("ALTER TABLE script_steps ADD COLUMN price TEXT")

        if "title" not in step_cols:
            conn.execute("ALTER TABLE script_steps ADD COLUMN title TEXT")

        # Migration logique: si anciennes étapes paywall (is_paywall=1), les convertir en step_type paywall_*
        conn.execute(
            """
            UPDATE script_steps
            SET step_type = CASE
                WHEN step_type = 'media_text' THEN 'paywall_media_text'
                ELSE 'paywall_text'
            END
            WHERE is_paywall = 1 AND step_type NOT LIKE 'paywall_%'
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id INTEGER NOT NULL,
                bot_id INTEGER NOT NULL,
                script_id INTEGER,
                mode TEXT NOT NULL,
                current_step INTEGER NOT NULL DEFAULT 1,
                paywall_unlocked INTEGER NOT NULL DEFAULT 0,
                script_started INTEGER NOT NULL DEFAULT 0,
                paywall_counter INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subscriber_id) REFERENCES subscribers(id) ON DELETE CASCADE,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                FOREIGN KEY(script_id) REFERENCES scripts(id) ON DELETE SET NULL
            )
            """
        )

        # Migration légère (si DB existante créée avant ces colonnes)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(conversations)")}
        if "script_started" not in cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN script_started INTEGER NOT NULL DEFAULT 0")
        if "paywall_counter" not in cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN paywall_counter INTEGER NOT NULL DEFAULT 0")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_script_pos ON script_steps(script_id, position)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conversation_id, id)"
        )

        _ensure_single_creator(conn)


def _default_creator_persona() -> Dict[str, Any]:
    # Valeurs minimales compatibles avec Sinhome_llm (sliders requis)
    return {
        "name": "Créatrice",
        "base_prompt": "",
        "dominance": 3,
        "audacity": 3,
        "sales_tactic": 2,
        "tone": 2,
        "emotion": 3,
        "initiative": 3,
        "vocabulary": 3,
        "emojis": 3,
        "imperfection": 1,
    }


def _ensure_single_creator(conn: sqlite3.Connection) -> None:
    now = _utc_now_iso()
    bots = list(conn.execute("SELECT id, updated_at FROM bots ORDER BY updated_at DESC, id DESC"))

    if not bots:
        payload = json.dumps(_default_creator_persona(), ensure_ascii=False)
        conn.execute(
            "INSERT INTO bots(name, persona_json, created_at, updated_at) VALUES(?, ?, ?, ?)",
            ("Créatrice", payload, now, now),
        )
        return

    keep_id = int(bots[0]["id"])
    other_ids = [int(b["id"]) for b in bots[1:]]
    if other_ids:
        placeholders = ",".join(["?"] * len(other_ids))
        conn.execute(
            f"UPDATE conversations SET bot_id = ? WHERE bot_id IN ({placeholders})",
            (keep_id, *other_ids),
        )
        conn.execute(f"DELETE FROM bots WHERE id IN ({placeholders})", tuple(other_ids))

    # Normalise le nom affiché
    conn.execute(
        "UPDATE bots SET name = ?, updated_at = ? WHERE id = ?",
        ("Créatrice", now, keep_id),
    )


# --- Bots ---

def list_bots() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return list(conn.execute("SELECT * FROM bots ORDER BY updated_at DESC, id DESC"))


def get_bot(bot_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()


def upsert_bot(bot_id: Optional[int], name: str, persona_data: Dict[str, Any]) -> int:
    now = _utc_now_iso()
    payload = json.dumps(persona_data, ensure_ascii=False)
    with get_conn() as conn:
        if bot_id:
            conn.execute(
                "UPDATE bots SET name = ?, persona_json = ?, updated_at = ? WHERE id = ?",
                (name, payload, now, bot_id),
            )
            return bot_id
        cur = conn.execute(
            "INSERT INTO bots(name, persona_json, created_at, updated_at) VALUES(?, ?, ?, ?)",
            (name, payload, now, now),
        )
        return int(cur.lastrowid)


def create_conversation(
    subscriber_id: int,
    bot_id: int,
    mode: str = "free",
    script_id: Optional[int] = None,
) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO conversations(subscriber_id, bot_id, script_id, mode, current_step, paywall_unlocked, script_started, paywall_counter, created_at, updated_at)
            VALUES(?, ?, ?, ?, 1, 0, 0, 0, ?, ?)
            """,
            (subscriber_id, bot_id, script_id, mode, now, now),
        )
        return int(cur.lastrowid)


def delete_bot(bot_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))


def parse_persona_json(bot_row: sqlite3.Row) -> Dict[str, Any]:
    try:
        return json.loads(bot_row["persona_json"] or "{}")
    except Exception:
        return {}


# --- Scripts ---

def list_scripts() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return list(conn.execute("SELECT * FROM scripts ORDER BY updated_at DESC, id DESC"))


def list_scripts_for_bot(bot_id: int) -> List[sqlite3.Row]:
    with get_conn() as conn:
        return list(
            conn.execute(
                "SELECT * FROM scripts WHERE bot_id = ? ORDER BY updated_at DESC, id DESC",
                (bot_id,),
            )
        )


def get_script(script_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()


def upsert_script(script_id: Optional[int], name: str, description: str, bot_id: Optional[int]) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        if script_id:
            conn.execute(
                "UPDATE scripts SET name = ?, description = ?, bot_id = ?, updated_at = ? WHERE id = ?",
                (name, description, bot_id, now, script_id),
            )
            return script_id
        cur = conn.execute(
            "INSERT INTO scripts(name, description, bot_id, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
            (name, description, bot_id, now, now),
        )
        return int(cur.lastrowid)


def delete_script(script_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))


# --- Steps ---

def list_steps(script_id: int) -> List[sqlite3.Row]:
    with get_conn() as conn:
        return list(
            conn.execute(
                "SELECT * FROM script_steps WHERE script_id = ? ORDER BY position ASC",
                (script_id,),
            )
        )


def _get_max_position(conn: sqlite3.Connection, script_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(position), 0) AS max_pos FROM script_steps WHERE script_id = ?",
        (script_id,),
    ).fetchone()
    return int(row["max_pos"] if row else 0)


def add_step(
    script_id: int,
    step_type: str,
    title: Optional[str],
    script_text: str,
    media_desc: Optional[str],
    price: Optional[str],
) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        pos = _get_max_position(conn, script_id) + 1
        is_paywall = 1 if str(step_type).startswith("paywall_") else 0
        cur = conn.execute(
            """
            INSERT INTO script_steps(script_id, position, step_type, title, script_text, media_desc, is_paywall, price, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (script_id, pos, step_type, title, script_text, media_desc, is_paywall, price, now, now),
        )
        return int(cur.lastrowid)


def update_step(
    step_id: int,
    step_type: str,
    title: Optional[str],
    script_text: str,
    media_desc: Optional[str],
    price: Optional[str],
) -> None:
    now = _utc_now_iso()
    is_paywall = 1 if str(step_type).startswith("paywall_") else 0
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE script_steps
            SET step_type = ?, title = ?, script_text = ?, media_desc = ?, is_paywall = ?, price = ?, updated_at = ?
            WHERE id = ?
            """,
            (step_type, title, script_text, media_desc, is_paywall, price, now, step_id),
        )


def delete_step(step_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM script_steps WHERE id = ?", (step_id,))


def move_step(script_id: int, step_id: int, direction: str) -> None:
    if direction not in ("up", "down"):
        return
    with get_conn() as conn:
        steps = list(
            conn.execute(
                "SELECT id, position FROM script_steps WHERE script_id = ? ORDER BY position ASC",
                (script_id,),
            )
        )
        idx = next((i for i, s in enumerate(steps) if int(s["id"]) == int(step_id)), None)
        if idx is None:
            return
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if swap_idx < 0 or swap_idx >= len(steps):
            return
        a = steps[idx]
        b = steps[swap_idx]
        conn.execute(
            "UPDATE script_steps SET position = ? WHERE id = ?",
            (int(b["position"]), int(a["id"])),
        )
        conn.execute(
            "UPDATE script_steps SET position = ? WHERE id = ?",
            (int(a["position"]), int(b["id"])),
        )


# --- Subscribers ---

def list_subscribers() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return list(conn.execute("SELECT * FROM subscribers ORDER BY created_at DESC, id DESC"))


def get_subscriber(subscriber_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM subscribers WHERE id = ?", (subscriber_id,)).fetchone()


def upsert_subscriber(subscriber_id: Optional[int], username: str, display_name: str) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        if subscriber_id:
            conn.execute(
                "UPDATE subscribers SET username = ?, display_name = ? WHERE id = ?",
                (username, display_name, subscriber_id),
            )
            return subscriber_id
        existing = conn.execute(
            "SELECT id FROM subscribers WHERE username = ?",
            (username,),
        ).fetchone()
        if existing:
            sid = int(existing["id"])
            conn.execute(
                "UPDATE subscribers SET display_name = ? WHERE id = ?",
                (display_name, sid),
            )
            return sid

        try:
            cur = conn.execute(
                "INSERT INTO subscribers(username, display_name, created_at) VALUES(?, ?, ?)",
                (username, display_name, now),
            )
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            # Concurrence / double click: retombe sur l'existant
            row = conn.execute(
                "SELECT id FROM subscribers WHERE username = ?",
                (username,),
            ).fetchone()
            if not row:
                raise
            return int(row["id"])


def delete_subscriber(subscriber_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM subscribers WHERE id = ?", (subscriber_id,))


def list_conversations() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return list(
            conn.execute(
                """
                SELECT
                    c.*, 
                    s.username AS subscriber_username,
                    COALESCE(s.display_name, '') AS subscriber_display_name,
                    b.name AS bot_name,
                    COALESCE(sc.name, '') AS script_name
                FROM conversations c
                JOIN subscribers s ON s.id = c.subscriber_id
                JOIN bots b ON b.id = c.bot_id
                LEFT JOIN scripts sc ON sc.id = c.script_id
                ORDER BY c.updated_at DESC, c.id DESC
                """
            )
        )


def get_default_bot_id() -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM bots ORDER BY updated_at DESC, id DESC LIMIT 1").fetchone()
        return int(row["id"]) if row else None


def get_creator_bot_id() -> Optional[int]:
    # Alias explicite
    return get_default_bot_id()


# --- Conversations ---

def get_or_create_conversation(
    subscriber_id: int,
    bot_id: int,
    mode: str,
    script_id: Optional[int],
) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM conversations
            WHERE subscriber_id = ? AND bot_id = ? AND mode = ? AND (script_id IS ? OR script_id = ?)
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (subscriber_id, bot_id, mode, script_id, script_id),
        ).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            """
            INSERT INTO conversations(subscriber_id, bot_id, script_id, mode, current_step, paywall_unlocked, created_at, updated_at)
            VALUES(?, ?, ?, ?, 1, 0, ?, ?)
            """,
            (subscriber_id, bot_id, script_id, mode, now, now),
        )
        return int(cur.lastrowid)


def get_conversation(conversation_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()


def delete_conversation(conversation_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


def update_conversation_state(
    conversation_id: int,
    current_step: int,
    paywall_unlocked: bool,
) -> None:
    now = _utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET current_step = ?, paywall_unlocked = ?, updated_at = ? WHERE id = ?",
            (current_step, 1 if paywall_unlocked else 0, now, conversation_id),
        )


def update_conversation_mode(
    conversation_id: int,
    mode: str,
    script_id: Optional[int],
) -> None:
    now = _utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET mode = ?, script_id = ?, current_step = 1, paywall_unlocked = 0, script_started = 0, paywall_counter = 0, updated_at = ?
            WHERE id = ?
            """,
            (mode, script_id, now, conversation_id),
        )


def set_script_started(conversation_id: int, started: bool) -> None:
    now = _utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET script_started = ?, updated_at = ? WHERE id = ?",
            (1 if started else 0, now, conversation_id),
        )


def set_paywall_counter(conversation_id: int, counter: int) -> None:
    now = _utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET paywall_counter = ?, updated_at = ? WHERE id = ?",
            (int(counter), now, conversation_id),
        )


def increment_paywall_counter(conversation_id: int) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT paywall_counter FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        current = int(row["paywall_counter"] if row else 0)
        new_val = current + 1
        conn.execute(
            "UPDATE conversations SET paywall_counter = ?, updated_at = ? WHERE id = ?",
            (new_val, now, conversation_id),
        )
        return new_val


def reset_conversation(conversation_id: int) -> None:
    now = _utc_now_iso()
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute(
            "UPDATE conversations SET current_step = 1, paywall_unlocked = 0, script_started = 0, paywall_counter = 0, updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


# --- Messages ---

def add_message(conversation_id: int, role: str, content: str) -> int:
    now = _utc_now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES(?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        return int(cur.lastrowid)


def list_messages(conversation_id: int, limit: int = 100) -> List[sqlite3.Row]:
    with get_conn() as conn:
        rows = list(
            conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            )
        )
        return list(reversed(rows))


def build_history(conversation_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    rows = list_messages(conversation_id, limit=limit)
    history: List[Dict[str, Any]] = []
    for r in rows:
        history.append({"role": r["role"], "content": r["content"]})
    return history
