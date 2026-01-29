import streamlit as st

from app.db import (
    add_step,
    delete_script,
    delete_step,
    get_script,
    list_scripts,
    list_steps,
    move_step,
    update_step,
    upsert_script,
)

st.set_page_config(page_title="Builder de Scripts", layout="wide")

st.title("Builder de Scripts")

if "script_edit_id" not in st.session_state:
    st.session_state["script_edit_id"] = None

left, right = st.columns([1, 2])

with left:
    st.subheader("Scripts")
    scripts = list_scripts()

    if st.button("+", type="primary"):
        st.session_state["script_edit_id"] = None
        st.rerun()

    if not scripts:
        st.info("Aucun script")
    else:
        for s in scripts:
            row_l, row_r = st.columns([6, 1])
            with row_l:
                if st.button(s["name"], key=f"pick_{s['id']}"):
                    st.session_state["script_edit_id"] = int(s["id"])
                    st.rerun()
            with row_r:
                if st.button("✕", key=f"x_{s['id']}"):
                    delete_script(int(s["id"]))
                    if st.session_state.get("script_edit_id") == int(s["id"]):
                        st.session_state["script_edit_id"] = None
                    st.rerun()


with right:
    selected_id = st.session_state.get("script_edit_id")
    script_row = get_script(int(selected_id)) if selected_id else None

    if not script_row:
        st.subheader("Nouveau script")
        name = st.text_input("Nom du script", value="")
        description = st.text_area("Description", value="", height=90)
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("Enregistrer", type="primary"):
                new_id = upsert_script(None, name.strip() or "Script", description, None)
                st.session_state["script_edit_id"] = int(new_id)
                st.rerun()
        st.stop()

    st.subheader(f"Édition: {script_row['name']}")
    name = st.text_input("Nom du script", value=script_row["name"], key="edit_name")
    description = st.text_area("Description", value=script_row["description"] or "", height=90, key="edit_desc")

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        if st.button("Sauver", type="primary"):
            upsert_script(int(script_row["id"]), name.strip() or "Script", description, None)
            st.rerun()
    with c2:
        if st.button("Supprimer"):
            delete_script(int(script_row["id"]))
            st.session_state["script_edit_id"] = None
            st.rerun()

    steps = list_steps(int(script_row["id"]))
    st.divider()
    st.subheader("Étapes")

    for s in steps:
        with st.container(border=True):
            l, r = st.columns([4, 1])
            with l:
                st.markdown(f"### Étape {int(s['position'])}")
                price_label = (s["price"] or "").strip()
                title_label = ""
                try:
                    if hasattr(s, "keys") and "title" in s.keys():
                        title_label = (s["title"] or "").strip()
                except Exception:
                    title_label = ""
                st.caption(
                    f"type={s['step_type']}"
                    + (f" | titre={title_label}" if title_label else "")
                    + (f" | prix={price_label}" if price_label else "")
                )

                edit_type = st.selectbox(
                    "Type",
                    options=["text", "media_text", "paywall_text", "paywall_media_text"],
                    index=["text", "media_text", "paywall_text", "paywall_media_text"].index(s["step_type"]),
                    key=f"type_{s['id']}",
                )
                edit_title = None
                if edit_type in ("paywall_text", "paywall_media_text"):
                    edit_title = st.text_input(
                        "Titre",
                        value=((s["title"] if (hasattr(s, "keys") and "title" in s.keys()) else "") or ""),
                        key=f"title_{s['id']}",
                    )
                edit_text = st.text_area(
                    "Script",
                    value=s["script_text"],
                    height=100,
                    key=f"text_{s['id']}",
                )
                edit_media = None
                if edit_type in ("media_text", "paywall_media_text"):
                    edit_media = st.text_area(
                        "Media desc",
                        value=s["media_desc"] or "",
                        height=70,
                        key=f"media_{s['id']}",
                    )
                edit_price = None
                if edit_type in ("paywall_text", "paywall_media_text"):
                    edit_price = st.text_input(
                        "Prix",
                        value=(s["price"] or ""),
                        key=f"price_{s['id']}",
                    )

            with r:
                if st.button("↑", key=f"up_{s['id']}"):
                    move_step(int(script_row["id"]), int(s["id"]), "up")
                    st.rerun()
                if st.button("↓", key=f"down_{s['id']}"):
                    move_step(int(script_row["id"]), int(s["id"]), "down")
                    st.rerun()
                if st.button("Sauver", key=f"save_{s['id']}", type="primary"):
                    if not edit_text.strip():
                        st.error("Script vide.")
                    else:
                        update_step(int(s["id"]), edit_type, edit_title, edit_text.strip(), edit_media, edit_price)
                        st.rerun()
                if st.button("Supprimer", key=f"del_{s['id']}"):
                    delete_step(int(s["id"]))
                    st.rerun()

    with st.expander("+ Ajouter une étape", expanded=(len(steps) == 0)):
        step_type = st.selectbox(
            "Type",
            options=["text", "media_text", "paywall_text", "paywall_media_text"],
            key="new_step_type",
        )
        title = None
        if step_type in ("paywall_text", "paywall_media_text"):
            title = st.text_input("Titre", value="", key="new_step_title")
        script_text = st.text_area("Texte / phrase-modèle (script)", height=120, key="new_step_text")
        media_desc = None
        if step_type in ("media_text", "paywall_media_text"):
            media_desc = st.text_area("Description du média (photo/vidéo)", height=80, key="new_step_media")
        price = None
        if step_type in ("paywall_text", "paywall_media_text"):
            price = st.text_input("Prix", value="", key="new_step_price")
        if st.button("Ajouter", type="primary", key="add_step"):
            if not script_text.strip():
                st.error("Le texte de l'étape est requis.")
            else:
                add_step(int(script_row["id"]), step_type, title, script_text.strip(), media_desc, price)
                st.rerun()
