import random
import time
import streamlit as st
from groq import Groq
from supabase import create_client

# Ρύθμιση Σελίδας
st.set_page_config(page_title="AI or Not", layout="centered")
st.title("AI or Not - Online Multiplayer")

# Εξαφάνιση του default μενού
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Ανάγνωση Secrets & Init
groq_key = st.secrets.get("GROQ_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

if not groq_key or not supabase_url or not supabase_key:
    st.error("Λείπουν διαπιστευτήρια στο .streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=groq_key)
supabase = create_client(supabase_url, supabase_key)


def generate_ai_reply(history_messages, system_instruction):
    # ΕΔΩ: Αφαιρέθηκε το try/except. Αν σκάσει, θα φανεί το κανονικό error!
    messages = [{"role": "system", "content": system_instruction}
                ] + history_messages
    completion = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=0.7,
        max_tokens=150
    )
    time.sleep(random.uniform(1.5, 3.0))  # Καθυστέρηση για ρεαλισμό
    return completion.choices[0].message.content


# --- ΒΗΜΑ 1: Αρχική Είσοδος ---
if "user_name" not in st.session_state:
    st.subheader("1. Καλώς ήρθες!")
    name_input = st.text_input("Το όνομά σου:")
    role_input = st.selectbox("Επίλεξε το ρόλο σου:", ["Ανακριτής", "Ύποπτος"])

    if st.button("Είσοδος"):
        if name_input.strip():
            st.session_state["user_name"] = name_input.strip()
            st.session_state["user_role"] = role_input
            st.rerun()
        else:
            st.warning("Πρέπει να βάλεις ένα όνομα.")
    st.stop()

with st.sidebar:
    st.write(f"Παίκτης: {st.session_state['user_name']}")
    st.write(f"Ρόλος: {st.session_state['user_role']}")
    if st.button("Αλλαγή Λογαριασμού"):
        st.session_state.clear()
        st.rerun()

# --- ΒΗΜΑ 2: Διαχείριση Lobby ---
if "current_room" not in st.session_state:
    st.subheader("2. Διαχείριση Lobby")

    if st.session_state["user_role"] == "Ύποπτος":
        st.write("Δημιουργία Νέου Lobby")
        room_name_input = st.text_input(
            "Όνομα Δωματίου (π.χ. To_Dwmatiaki):").strip()
        style_input = st.text_area(
            "Στυλ & Χαρακτηριστικά:", value="Μιλάω κοφτά, χρησιμοποιώ slang, πίνω πολύ καφέ.")
        is_priv = st.checkbox("Ιδιωτικό Δωμάτιο")

        room_pass = ""
        if is_priv:
            room_pass = st.text_input("Κωδικός Δωματίου (Password):").strip()

        if st.button("Δημιουργία Lobby"):
            if not room_name_input:
                st.warning("Παρακαλώ βάλε ένα όνομα δωματίου.")
            elif not style_input.strip():
                st.warning("Γράψε λίγα χαρακτηριστικά.")
            elif is_priv and not room_pass:
                st.warning("Έβαλες Ιδιωτικό, πρέπει να ορίσεις έναν κωδικό.")
            else:
                # Upsert για να δημιουργηθεί το δωμάτιο στη βάση
                supabase.table("rooms").upsert({
                    "room_name": room_name_input,
                    "room_password": room_pass,
                    "host_name": st.session_state["user_name"],
                    "host_style": style_input.strip(),
                    "is_private": is_priv,
                    "status": "waiting_guest",
                    "turn_status": "waiting_suspect_choice",
                    "chat_history": [],
                    "round_count": 1,
                    "interrogator_score": 0,
                    "suspect_score": 0,
                    "questions_in_round": 0
                }).execute()
                st.session_state["current_room"] = room_name_input
                st.rerun()
    else:
        st.write("Εύρεση Lobby")
        tab_pub, tab_priv = st.tabs(["Δημόσια Lobbies", "Ιδιωτικό Lobby"])

        with tab_pub:
            public_rooms = supabase.table("rooms").select(
                "*").eq("is_private", False).eq("status", "waiting_guest").execute()
            if public_rooms.data:
                for r in public_rooms.data:
                    col_info, col_btn = st.columns([3, 1])
                    col_info.write(
                        f"Δωμάτιο: **{r['room_name']}** (Ύποπτος: {r['host_name']})")
                    if col_btn.button("Σύνδεση", key=f"join_{r['room_name']}"):
                        supabase.table("rooms").update({
                            "guest_name": st.session_state["user_name"],
                            "status": "active"
                        }).eq("room_name", r['room_name']).execute()
                        st.session_state["current_room"] = r['room_name']
                        st.rerun()
            else:
                st.info("Δεν βρέθηκαν δημόσια lobbies.")

            if st.button("Ανανέωση Λίστας"):
                st.rerun()

        with tab_priv:
            priv_name = st.text_input("Όνομα Ιδιωτικού Δωματίου:").strip()
            priv_pass = st.text_input("Κωδικός:").strip()
            if st.button("Σύνδεση σε Ιδιωτικό"):
                if priv_name and priv_pass:
                    res = supabase.table("rooms").select(
                        "*").eq("room_name", priv_name).eq("room_password", priv_pass).execute()
                    if res.data and res.data[0]["status"] == "waiting_guest":
                        supabase.table("rooms").update({
                            "guest_name": st.session_state["user_name"],
                            "status": "active"
                        }).eq("room_name", priv_name).execute()
                        st.session_state["current_room"] = priv_name
                        st.rerun()
                    else:
                        st.error(
                            "Λάθος Όνομα/Κωδικός ή το δωμάτιο είναι γεμάτο/ανύπαρκτο.")
    st.stop()

# --- ΒΗΜΑ 3: Παιχνίδι (Μέχρι 5 ερωτήσεις) ---


@st.fragment(run_every=2)
def play_game():
    room_name = st.session_state["current_room"]
    role = st.session_state["user_role"]

    res = supabase.table("rooms").select(
        "*").eq("room_name", room_name).execute()

    if not res.data:
        st.warning("Το lobby έκλεισε ή διαγράφηκε.")
        if st.button("Επιστροφή"):
            st.session_state.pop("current_room", None)
            st.rerun()
        return

    room = res.data[0]

    if room["status"] == "waiting_guest":
        st.info(f"Αναμονή για Ανακριτή στο δωμάτιο: **{room_name}**...")
        if st.button("Ακύρωση & Έξοδος"):
            supabase.table("rooms").delete().eq(
                "room_name", room_name).execute()
            st.session_state.pop("current_room", None)
            st.rerun()
        return

    st.subheader(f"Lobby: {room_name}")
    st.write(
        f"Γύρος: **{room['round_count']} / 3** | Σκορ Ανακριτή: {room['interrogator_score']} - Σκορ Υπόπτου: {room['suspect_score']}")

    col_empty, col_exit = st.columns([4, 1])
    with col_exit:
        if st.button("Exit Lobby"):
            supabase.table("rooms").delete().eq(
                "room_name", room_name).execute()
            st.session_state.pop("current_room", None)
            st.rerun()

    st.divider()

    # Εμφάνιση Ιστορικού Chat
    chat_history = room.get("chat_history", [])
    for msg in chat_history:
        role_label = "Ανακριτής" if msg["role"] == "user" else "Ύποπτος"
        st.markdown(f"**{role_label}:** {msg['content']}")

    st.divider()

    # Συνάρτηση ελέγχου μαντεψιάς (Κλείνει τον γύρο)
    def process_guess(guess_val):
        correct = (guess_val == room["current_responder"])
        i_score = room["interrogator_score"] + (1 if correct else 0)
        s_score = room["suspect_score"] + (0 if correct else 1)

        if room["round_count"] >= 3:
            next_status = "finished"
            next_round = room["round_count"]
        else:
            next_status = "waiting_suspect_choice"
            next_round = room["round_count"] + 1

        supabase.table("rooms").update({
            "interrogator_score": i_score,
            "suspect_score": s_score,
            "chat_history": [],
            "turn_status": next_status,
            "round_count": next_round,
            "questions_in_round": 0,
            "current_responder": ""
        }).eq("room_name", room_name).execute()
        st.rerun()

    # --- ΟΨΗ ΑΝΑΚΡΙΤΗ ---
    if role == "Ανακριτής":
        if room["turn_status"] == "waiting_suspect_choice":
            st.info(
                "Αναμονή... Ο Ύποπτος επιλέγει αν θα απαντήσει ο ίδιος ή το AI σε αυτόν τον γύρο.")

        elif room["turn_status"] == "waiting_prompt":
            st.write(
                f"*Έχεις κάνει {room['questions_in_round']} / 5 ερωτήσεις.*")

            # Κουμπιά Μαντεψιάς (Εμφανίζονται από την 1η ερώτηση και μετά)
            if room["questions_in_round"] > 0:
                st.write("---")
                st.write("### Έτοιμος; Μάντεψε ποιος σου απαντάει!")
                col1, col2 = st.columns(2)
                if col1.button("🤖 Είναι το AI"):
                    process_guess("AI")
                if col2.button("👤 Είναι Άνθρωπος"):
                    process_guess("Human")

            # Πεδίο ερώτησης (αν δεν έχει φτάσει τις 5)
            if room["questions_in_round"] < 5:
                if prompt := st.chat_input("Γράψε την ερώτησή σου..."):
                    chat_history.append({"role": "user", "content": prompt})
                    new_q_count = room["questions_in_round"] + 1

                    if room["current_responder"] == "AI":
                        with st.spinner("Ο Ύποπτος πληκτρολογεί..."):
                            system_instruction = f"Είσαι ο {room['host_name']}. Στυλ: {room['host_style']}. Μίλα εντελώς φυσικά και ρεαλιστικά στα Ελληνικά σαν αληθινός άνθρωπος. Απάντα κοφτά, 1-2 προτάσεις το πολύ."
                            reply = generate_ai_reply(
                                chat_history, system_instruction)
                            chat_history.append(
                                {"role": "assistant", "content": reply})

                            supabase.table("rooms").update({
                                "chat_history": chat_history,
                                "questions_in_round": new_q_count
                            }).eq("room_name", room_name).execute()
                            st.rerun()
                    else:
                        supabase.table("rooms").update({
                            "chat_history": chat_history,
                            "questions_in_round": new_q_count,
                            "turn_status": "waiting_human_answer"
                        }).eq("room_name", room_name).execute()
                        st.rerun()
            else:
                st.warning(
                    "Έφτασες το όριο των 5 ερωτήσεων! Πρέπει να πάρεις την τελική σου απόφαση για αυτόν τον γύρο.")

        elif room["turn_status"] == "waiting_human_answer":
            st.info("Ο Ύποπτος πληκτρολογεί την απάντησή του...")

        elif room["turn_status"] == "finished":
            st.write("### Τελικό Αποτέλεσμα")
            if room["interrogator_score"] > room["suspect_score"]:
                st.success(
                    "Νίκησες! Ανακάλυψες την αλήθεια στους περισσότερους γύρους.")
            else:
                st.error("Έχασες! Ο Ύποπτος κατάφερε να σε ξεγελάσει.")

            if st.button("Rematch (Νέο Παιχνίδι)"):
                supabase.table("rooms").update({
                    "turn_status": "waiting_suspect_choice",
                    "chat_history": [],
                    "round_count": 1,
                    "interrogator_score": 0,
                    "suspect_score": 0,
                    "questions_in_round": 0,
                    "current_responder": ""
                }).eq("room_name", room_name).execute()
                st.rerun()

    # --- ΟΨΗ ΥΠΟΠΤΟΥ ---
    else:
        if room["turn_status"] == "waiting_suspect_choice":
            st.write(f"### Γύρος {room['round_count']}: Ποιος θα απαντήσει;")
            col_ai, col_hu = st.columns(2)
            if col_ai.button("Απάντηση από AI"):
                supabase.table("rooms").update({"current_responder": "AI", "turn_status": "waiting_prompt"}).eq(
                    "room_name", room_name).execute()
                st.rerun()
            if col_hu.button("Απάντηση από Εμένα"):
                supabase.table("rooms").update({"current_responder": "Human", "turn_status": "waiting_prompt"}).eq(
                    "room_name", room_name).execute()
                st.rerun()

        elif room["turn_status"] == "waiting_prompt":
            st.info(
                "Ο Ανακριτής σκέφτεται την επόμενη ερώτησή του ή ετοιμάζεται να μαντέψει...")

        elif room["turn_status"] == "waiting_human_answer":
            # Εδώ παίρνουμε την τελευταία ερώτηση από το ιστορικό
            last_q = chat_history[-1]["content"] if chat_history else ""
            st.warning(f"Ερώτηση Ανακριτή: {last_q}")
            h_ans = st.text_input("Η απάντησή σου:")
            if st.button("Αποστολή Απάντησης"):
                if h_ans.strip():
                    chat_history.append(
                        {"role": "assistant", "content": h_ans.strip()})
                    supabase.table("rooms").update({
                        "chat_history": chat_history,
                        "turn_status": "waiting_prompt"
                    }).eq("room_name", room_name).execute()
                    st.rerun()

        elif room["turn_status"] == "finished":
            st.write("### Τελικό Αποτέλεσμα")
            if room["suspect_score"] > room["interrogator_score"]:
                st.success("Νίκησες! Κατάφερες να ξεγελάσεις τον Ανακριτή.")
            else:
                st.error("Έχασες! Ο Ανακριτής βρήκε την αλήθεια.")
            st.info("Αναμονή για Rematch από τον Ανακριτή.")


play_game()
