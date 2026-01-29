import uuid
import os

import streamlit as st

from app.db import (
    add_message,
    build_history,
    get_bot,
    create_conversation,
    get_default_bot_id,
    delete_conversation,
    list_conversations,
    list_messages,
    list_scripts,
    list_steps,
    parse_persona_json,
    reset_conversation,
    increment_paywall_counter,
    set_paywall_counter,
    set_script_started,
    update_conversation_mode,
    update_conversation_state,
    upsert_subscriber,
)
from app.sinhome_client import SinhomeClientError, personality_chat, script_chat, script_media, unpersona_chat

st.set_page_config(page_title="Conversations Abonnés", layout="wide")

st.title("Conversations Abonnés")

api_url = os.environ.get("SINHOME_API_URL") or "http://127.0.0.1:8001"

# --- Layout ---
left, right = st.columns([1, 2])

with left:
    st.subheader("Conversations")
    conversations = list_conversations()

    if "selected_conversation_id" not in st.session_state:
        st.session_state["selected_conversation_id"] = None

    if conversations:
        for c in conversations:
            row_l, row_r = st.columns([6, 1])
            with row_l:
                if st.button(f"{c['subscriber_username']}", key=f"conv_{c['id']}"):
                    st.session_state["selected_conversation_id"] = int(c["id"])
                    st.rerun()
            with row_r:
                if st.button("✕", key=f"conv_x_{c['id']}"):
                    delete_conversation(int(c["id"]))
                    if st.session_state.get("selected_conversation_id") == int(c["id"]):
                        st.session_state["selected_conversation_id"] = None
                    st.rerun()
    else:
        st.info("Aucune conversation.")

    st.divider()
    st.subheader("+")
    conv_name = st.text_input("Nom", key="new_conv_name")
    if st.button("Créer", type="primary"):
        default_bot_id = get_default_bot_id()
        if not conv_name.strip():
            st.error("Nom requis")
        else:
            # On utilise 'subscriber.username' comme nom de conversation
            subscriber_id = upsert_subscriber(None, conv_name.strip(), "")
            new_id = create_conversation(subscriber_id=subscriber_id, bot_id=int(default_bot_id), mode="free", script_id=None)
            st.session_state["selected_conversation_id"] = int(new_id)
            st.rerun()


selected_conversation_id = st.session_state.get("selected_conversation_id")
if not selected_conversation_id:
    with right:
        st.info("Clique une conversation à gauche, ou crée-en une.")
    st.stop()

conversation_id = int(selected_conversation_id)

conv = st.session_state.get("conv")
if not conv or conv.get("id") != conversation_id:
    st.session_state["conv"] = {"id": conversation_id, "session_id": str(uuid.uuid4())}

conv_row = None
from app.db import get_conversation
conv_row = get_conversation(conversation_id)

active_mode = (
    "Free Talking"
    if (conv_row and conv_row["mode"] == "free")
    else ("Chloé" if (conv_row and conv_row["mode"] == "chloe") else "Script Mode")
)
active_script_id = int(conv_row["script_id"]) if (conv_row and conv_row["script_id"]) else None
active_bot_id = int(conv_row["bot_id"]) if conv_row else None

script_started = bool(int(conv_row["script_started"])) if conv_row and "script_started" in conv_row.keys() else False
paywall_counter = int(conv_row["paywall_counter"]) if conv_row and "paywall_counter" in conv_row.keys() else 0

bot_row = get_bot(active_bot_id) if active_bot_id else None
persona_data = parse_persona_json(bot_row) if bot_row else {}

with left:
    st.divider()
    st.subheader("Réglages")

    selected_mode = st.radio(
        "Mode",
        options=["Free Talking", "Script Mode", "Chloé"],
        index=(0 if active_mode == "Free Talking" else (2 if active_mode == "Chloé" else 1)),
        horizontal=True,
    )

    scripts = list_scripts()
    script_options = ["(Aucun)"] + [f"#{s['id']} - {s['name']}" for s in scripts]
    current_script_label = "(Aucun)"
    if active_script_id:
        match = next((s for s in scripts if int(s["id"]) == int(active_script_id)), None)
        if match:
            current_script_label = f"#{match['id']} - {match['name']}"

    selected_script_label = st.selectbox(
        "Script",
        options=script_options,
        index=script_options.index(current_script_label) if current_script_label in script_options else 0,
        disabled=(selected_mode != "Script Mode") or script_started,
    )

    desired_mode = "free" if selected_mode == "Free Talking" else ("chloe" if selected_mode == "Chloé" else "script")
    desired_script_id = None
    if selected_mode == "Script Mode" and selected_script_label != "(Aucun)":
        desired_script_id = int(selected_script_label.split("-")[0].strip().lstrip("#"))
    if selected_mode == "Chloé":
        desired_script_id = None

    can_apply_change = (not script_started) or (desired_mode != "script")
    if can_apply_change:
        if conv_row and (
            desired_mode != conv_row["mode"]
            or desired_script_id != (int(conv_row["script_id"]) if conv_row["script_id"] else None)
        ):
            update_conversation_mode(conversation_id, desired_mode, desired_script_id)
            st.rerun()

    if st.button("Reset conversation"):
        reset_conversation(conversation_id)
        st.rerun()

with right:
    if active_mode == "Script Mode" and active_script_id:
        steps = list_steps(active_script_id)
    else:
        steps = []

    from app.db import get_conversation as _get_conversation_ui

    conv_row_ui = _get_conversation_ui(conversation_id)
    paywall_counter_ui = int(conv_row_ui["paywall_counter"]) if (conv_row_ui and "paywall_counter" in conv_row_ui.keys()) else 0

    messages = list_messages(conversation_id, limit=200)
    for m in messages:
        with st.chat_message(m["role"]):
            content = m["content"] or ""
            marker = "[[PAYWALL::"
            if m["role"] == "assistant" and marker in content and content.strip().endswith("]]" ):
                main_text, meta = content.rsplit(marker, 1)
                meta = meta[:-2]
                parts = meta.split("::")
                title_ui = (parts[0] if len(parts) > 0 else "Paywall").strip() or "Paywall"
                price_ui = (parts[1] if len(parts) > 1 else "").strip()
                st.write(main_text.strip())

                # Afficher le bouton payer si on est toujours bloqué sur un paywall
                show_pay = False
                unlocked_ui = False
                if active_mode == "Script Mode" and active_script_id and script_started and steps and conv_row_ui:
                    current_step_ui = int(conv_row_ui["current_step"])
                    idx_ui = max(0, current_step_ui - 1)
                    if idx_ui >= len(steps):
                        idx_ui = len(steps) - 1
                    step_ui = steps[idx_ui]
                    is_paywall_ui = str(step_ui["step_type"]).startswith("paywall_")
                    unlocked_ui = bool(int(conv_row_ui["paywall_unlocked"]))
                    show_pay = is_paywall_ui and (not unlocked_ui)

                st.divider()
                st.markdown(f"**{title_ui}**")
                if price_ui:
                    st.caption(f"Prix: {price_ui}")
                if st.button("Payer", key=f"paywall_pay_msg_{m['id']}", type="primary", disabled=(not show_pay)):
                    if conv_row_ui:
                        update_conversation_state(conversation_id, int(conv_row_ui["current_step"]), True)
                    set_paywall_counter(conversation_id, 0)
                    st.rerun()
            else:
                st.write(content)

    user_text = st.chat_input("Ton message")

if active_mode == "Script Mode" and active_script_id and not steps:
    st.warning("Ce script n'a pas d'étapes.")

# --- Script controls (si mode script) ---
if active_mode == "Script Mode" and active_script_id:
    unlocked = bool(int(conv_row["paywall_unlocked"])) if conv_row else False
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        if not script_started:
            lock_disabled = (not steps)
            if st.button("Lock", disabled=lock_disabled, type="primary"):
                set_script_started(conversation_id, True)
                set_paywall_counter(conversation_id, 0)
                update_conversation_state(conversation_id, 1, False)
                st.rerun()
        else:
            if st.button("Unlock"):
                set_script_started(conversation_id, False)
                st.rerun()
    with c2:
        if st.button("Payer", disabled=(not script_started) or unlocked):
            current_step = int(conv_row["current_step"]) if conv_row else 1
            update_conversation_state(conversation_id, current_step, True)
            set_paywall_counter(conversation_id, 0)
            st.rerun()

send_as = "user"


def _call_llm(user_msg: str) -> str:
    history = build_history(conversation_id, limit=20)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == user_msg:
        history = history[:-1]
    session_id = st.session_state["conv"]["session_id"]

    # état conversation à jour (évite le stale après paiement / progression)
    from app.db import get_conversation as _get_conversation

    conv_row_live = _get_conversation(conversation_id)
    current_step_live = int(conv_row_live["current_step"]) if conv_row_live else 1
    paywall_unlocked_live = bool(int(conv_row_live["paywall_unlocked"])) if conv_row_live else False

    if active_mode == "Chloé":
        return unpersona_chat(api_url, session_id, user_msg, history, None)

    if active_mode == "Free Talking" or not active_script_id:
        return personality_chat(api_url, session_id, user_msg, history, persona_data)

    # En script mode, on force une validation via Lock (évite les changements accidentels)
    if not script_started:
        return "Verrouille le script avec 'Lock' avant de discuter."

    if not steps:
        return "Le script n'a pas d'étapes."

    current_step = current_step_live
    idx = max(0, current_step_live - 1)
    if idx >= len(steps):
        idx = len(steps) - 1
    step = steps[idx]

    step_script = step["script_text"]
    is_paywall = str(step["step_type"]).startswith("paywall_")
    unlocked = paywall_unlocked_live

    if is_paywall and not unlocked:
        # tant que non payé: on discute, et tous les 3 messages user on renvoie le paywall
        c = increment_paywall_counter(conversation_id)
        if c == 1 or (c % 3 == 0):
            title_marker = ((step["title"] if (hasattr(step, "keys") and "title" in step.keys()) else "") or "Paywall").strip() or "Paywall"
            price_marker = ((step["price"] if (hasattr(step, "keys") and "price" in step.keys()) else "") or "").strip()
            if step["step_type"] in ("media_text", "paywall_media_text"):
                resp = script_media(api_url, session_id, user_msg, history, persona_data, step_script, step["media_desc"] or "")
            else:
                resp = script_chat(api_url, session_id, user_msg, history, persona_data, step_script)
            return f"{resp}\n\n[[PAYWALL::{title_marker}::{price_marker}]]"
        return personality_chat(api_url, session_id, user_msg, history, persona_data)

    # pas paywall (ou unlock): on répond selon le type
    if step["step_type"] in ("media_text", "paywall_media_text"):
        resp = script_media(api_url, session_id, user_msg, history, persona_data, step_script, step["media_desc"] or "")
    else:
        resp = script_chat(api_url, session_id, user_msg, history, persona_data, step_script)

    # avance automatiquement d'une étape après chaque échange
    next_step = current_step + 1
    if next_step > len(steps):
        next_step = len(steps)
    # Si on entre dans un paywall, on reset le compteur pour afficher le paywall immédiatement au prochain message
    if next_step != current_step and steps:
        try:
            step_next = steps[max(0, next_step - 1)]
            if str(step_next["step_type"]).startswith("paywall_"):
                set_paywall_counter(conversation_id, 0)
        except Exception:
            pass
    # Après une réponse script (paywall ou non), on reset le flag unlock
    update_conversation_state(conversation_id, next_step, False)
    return resp

if user_text:
    add_message(conversation_id, send_as, user_text)
    try:
        ai_text = _call_llm(user_text)
    except SinhomeClientError as e:
        ai_text = f"Erreur API: {e}"
    add_message(conversation_id, "assistant", ai_text)
    st.rerun()
