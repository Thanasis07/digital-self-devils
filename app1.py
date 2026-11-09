import random
import time
import streamlit as st
from groq import Groq
from supabase import create_client

# 1. Ρύθμιση Σελίδας
st.set_page_config(page_title="AI or Not", layout="centered")
st.title("AI or Not - Online Multiplayer")

# Εξαφάνιση του default μενού, του Deploy button και του footer του Streamlit
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 2. Ανάγνωση Secrets & Init
groq_key = st.secrets.get("GROQ_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

if not groq_key or not supabase_url or not supabase_key:
    st.error("Λείπουν διαπιστευτήρια στο .streamlit/secrets.toml")
    st.stop()

groq_client = Groq(api_key=groq_key)
supabase = create_client(supabase_url, supabase_key)


def generate_ai_reply(history_messages, system_instruction):
    time.sleep(random.uniform(1.5, 3.0))
    messages = [{"role": "system", "content": system_instruction}] + history_messages
    completion = groq_client.chat.completions.create(
        model="llama3-70b-8192",
        messages=messages,
        temperature=0.7,
        max_tokens=150
    )
    return completion.choices[0].message.content


# --- ΒΗΜΑ 1: Αρχική Είσοδος (Όνομα & Ρόλος) ---
if "user_name" not in st.session_state:
    st.subheader("1. Καλώς ήρθες!")
    name_input = st.text_input("Το όνομά σου:")
    role_input = st.selectbox("Επίλεξε το ρόλο σου:", ["Ανακριτής", "Δημιουργός Προφίλ"])

    if st.button("Είσοδος"):
        if name_input.strip():
            st.session_state["user_name"] = name_input.strip()
            st.session_state["user_role"] = role_input
            st.rerun()
        else:
            st.warning("Πρέπει να βάλεις ένα όνομα για να συνεχίσεις.")
    st.stop()

# Εμφάνιση του προφίλ στο Sidebar
with st.sidebar:
    st.write(f"**Παίκτης:** {st.session_state['user_name']}")
    st.write(f"**Ρόλος:** {st.session_state['user_role']}")
    if st.button("Αλλαγή Λογαριασμού"):
        st.session_state.clear()
        st.rerun()

# --- ΒΗΜΑ 2: Διαχείριση Lobby ---
if "current_room" not in st.session_state:
    st.subheader("2. Διαχείριση Lobby")

    if st.session_state["user_role"] == "Δημιουργός Προφίλ":
        st.write("### Δημιουργία Νέου Lobby")
        style_input = st.text_area("Στυλ & Χαρακτηριστικά του AI σου:", value="Μιλάω κοφτά, χρησιμοποιώ slang, πίνω πολύ καφέ.")
        room_code_input = st.text_input("Κωδικός Δωματίου:", value=f"ROOM{random.randint(1000, 9999)}").upper()
        is_priv = st.checkbox("Ιδιωτικό Δωμάτιο (Δεν θα φαίνεται στη δημόσια λίστα)")

        if st.button("Δημιουργία Lobby"):
            if not style_input.strip():
                st.warning("Γράψε λίγα χαρακτηριστικά για το προφίλ.")
            else:
                supabase.table("rooms").upsert({
                    "room_code": room_code_input,
                    "host_name": st.session_state["user_name"],
                    "host_style": style_input.strip(),
                    "is_private": is_priv,
                    "status": "waiting_guest",
                    "turn_status": "waiting_prompt", # waiting_prompt, waiting_answer, finished
                    "chat_history": [],            # Λίστα μηνυμάτων
                    "responder_choice": "AI"       # 'AI' ή 'Human' επιλεγμένο από τον Δημιουργό
                }).execute()
                st.session_state["current_room"] = room_code_input
                st.rerun()

    else:
        st.write("### Εύρεση Lobby")
        tab_pub, tab_priv = st.tabs(["Δημόσια Lobbies", "Ιδιωτικό Lobby"])

        with tab_pub:
            public_rooms = supabase.table("rooms").select("*").eq("is_private", False).eq("status", "waiting_guest").execute()
            if public_rooms.data:
                for r in public_rooms.data:
                    col_info, col_btn = st.columns([3, 1])
                    col_info.write(f"**Δωμάτιο:** {r['room_code']} (Δημιουργός: {r['host_name']})")
                    if col_btn.button("Σύνδεση", key=f"join_{r['room_code']}"):
                        supabase.table("rooms").update({
                            "guest_name": st.session_state["user_name"],
                            "status": "active"
                        }).eq("room_code", r['room_code']).execute()
                        st.session_state["current_room"] = r['room_code']
                        st.rerun()
            else:
                st.info("Δεν βρέθηκαν διαθέσιμα δημόσια lobbies.")

            if st.button("Ανανέωση Λίστας"):
                st.rerun()

        with tab_priv:
            priv_code = st.text_input("Βάλε τον κωδικό του δωματίου:").strip().upper()
            if st.button("Σύνδεση σε Ιδιωτικό"):
                if priv_code:
                    res = supabase.table("rooms").select("*").eq("room_code", priv_code).execute()
                    if res.data and res.data[0]["status"] == "waiting_guest":
                        supabase.table("rooms").update({
                            "guest_name": st.session_state["user_name"],
                            "status": "active"
                        }).eq("room_code", priv_code).execute()
                        st.session_state["current_room"] = priv_code
                        st.rerun()
                    else:
                        st.error("Το lobby δεν υπάρχει ή είναι ήδη γεμάτο.")
    st.stop()

# --- ΒΗΜΑ 3: Το Παιχνίδι (Live Refresh) ---
@st.fragment(run_every=2)
def play_game():
    room_code = st.session_state["current_room"]
    role = st.session_state["user_role"]

    res = supabase.table("rooms").select("*").eq("room_code", room_code).execute()

    if not res.data:
        st.warning("Το lobby έκλεισε ή διαγράφηκε.")
        if st.button("Επιστροφή στο Μενού"):
            st.session_state.pop("current_room", None)
            st.rerun()
        return

    room = res.data[0]

    if room["status"] == "waiting_guest":
        st.info(f"Αναμονή για Ανακριτή στο Lobby: **{room_code}**...")
        if st.button("Ακύρωση & Έξοδος"):
            supabase.table("rooms").delete().eq("room_code", room_code).execute()
            st.session_state.pop("current_room", None)
            st.rerun()
        return

    st.subheader(f"Lobby: {room_code} | Δημιουργός: {room['host_name']} vs Ανακριτής: {room['guest_name']}")

    col_empty, col_exit = st.columns([4, 1])
    with col_exit:
        if st.button("Exit Lobby"):
            supabase.table("rooms").delete().eq("room_code", room_code).execute()
            st.session_state.pop("current_room", None)
            st.rerun()

    st.divider()

    # Εμφάνιση Ιστορικού Συνομιλίας
    chat_history = room.get("chat_history", [])
    for msg in chat_history:
        if msg["role"] == "user":
            st.markdown(f"**🔍 Ανακριτής:** {msg['content']}")
        else:
            st.markdown(f"**🤖/👤 Προφίλ:** {msg['content']}")

    st.divider()

    # --- ΟΨΗ ΑΝΑΚΡΙΤΗ ---
    if role == "Ανακριτής":
        if room["turn_status"] != "finished":
            # 1. Πλαίσιο Υποβολής Ερώτησης
            if prompt := st.chat_input("Γράψε την επόμενη ερώτησή σου..."):
                chat_history.append({"role": "user", "content": prompt})
                
                # Αν ο δημιουργός είχε επιλέξει AI, απαντάει αυτόματα το ΑΙ.
                # Αν είχε επιλέξει Human, το θέτουμε σε αναμονή απάντησης από τον άνθρωπο.
                current_responder = room.get("responder_choice", "AI")
                
                if current_responder == "AI":
                    system_instruction = f"Είσαι το Digital Twin του {room['host_name']}. Στυλ: {room['host_style']}. Απάντα σε 1-2 προτάσεις στα ελληνικά."
                    reply = generate_ai_reply(chat_history[:-1], system_instruction)
                    chat_history.append({"role": "assistant", "content": reply})
                    next_status = "waiting_prompt"
                else:
                    next_status = "waiting_human_answer"

                supabase.table("rooms").update({
                    "chat_history": chat_history,
                    "turn_status": next_status
                }).eq("room_code", room_code).execute()
                st.rerun()

            if room["turn_status"] == "waiting_human_answer":
                st.info("Ο Δημιουργός πληκτρολογεί την απάντηση...")

            # 2. Κουμπιά Τελικής Απόφασης (Ο Ανακριτής μπορεί να αποφασίσει ανά πάσα στιγμή)
            st.write("### Τελική Απόφαση")
            st.write("Είσαι έτοιμος να μαντέψεις με ποιον μιλούσες σε όλη τη διάρκεια του διαλόγου;")
            col_btn_ai, col_btn_hu = st.columns(2)
            
            # Εδώ αποθηκεύουμε την πραγματική πηγή για να την ελέγξουμε. 
            # (Για απλότητα, αν έστω και μία φορά απάντησε ο άνθρωπος ή αν ήταν ορισμένο ως Human).
            if col_btn_ai.button("🤖 Ήταν τελικά AI"):
                # Έλεγχος αν όντως ήταν AI (π.χ. αν ο responder_choice ήταν AI συνεχώς ή βάσει καταγραφής)
                correct = (room.get("responder_choice") == "AI")
                supabase.table("rooms").update({"turn_status": "finished"}).eq("room_code", room_code).execute()
                st.session_state["res_msg"] = ("success" if correct else "error", "Σωστά! Ήταν το AI." if correct else "Λάθος! Ήταν ο αληθινός άνθρωπος.")
                st.rerun()

            if col_btn_hu.button("👤 Ήταν Αληθινός Άνθρωπος"):
                correct = (room.get("responder_choice") == "Human")
                supabase.table("rooms").update({"turn_status": "finished"}).eq("room_code", room_code).execute()
                st.session_state["res_msg"] = ("success" if correct else "error", "Σωστά! Ήταν ο αληθινός άνθρωπος." if correct else "Λάθος! Ήταν το AI.")
                st.rerun()

        else:
            # Τέλος παιχνιδιού / Αποτελέσματα
            if "res_msg" in st.session_state:
                tp, msg = st.session_state["res_msg"]
                st.success(msg) if tp == "success" else st.error(msg)

            if st.button("Rematch (Νέο Παιχνίδι)"):
                supabase.table("rooms").update({
                    "turn_status": "waiting_prompt",
                    "chat_history": [],
                    "responder_choice": "AI"
                }).eq("room_code", room_code).execute()
                st.session_state.pop("res_msg", None)
                st.rerun()

    # --- ΟΨΗ ΔΗΜΙΟΥΡΓΟΥ ΠΡΟΦΙΛ ---
    else:
        st.write("### Ρυθμίσεις Απάντησης")
        st.write("Επίλεξε ποιος θα απαντάει στις ερωτήσεις του Ανακριτή:")
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🤖 Απάντηση από AI", use_container_width=True):
                supabase.table("rooms").update({"responder_choice": "AI"}).eq("room_code", room_code).execute()
                st.rerun()
        with col_r2:
            if st.button("👤 Απάντηση από Εμένα (Άνθρωπος)", use_container_width=True):
                supabase.table("rooms").update({"responder_choice": "Human"}).eq("room_code", room_code).execute()
                st.rerun()

        current_choice = room.get("responder_choice", "AI")
        st.info(f"Τρέχουσα επιλογή απάντησης: **{'AI' if current_choice == 'AI' else 'Εσύ (Άνθρωπος)'}**")

        st.divider()

        if room["turn_status"] == "waiting_human_answer":
            st.warning("Ο Ανακριτής έκανε ερώτηση και περιμένει τη δική σου απάντηση!")
            h_ans = st.text_input("Γράψε την απάντησή σου ως άνθρωπος:")
            if st.button("Αποστολή Απάντησης"):
                if h_ans.strip():
                    chat_history.append({"role": "assistant", "content": h_ans.strip()})
                    supabase.table("rooms").update({
                        "chat_history": chat_history,
                        "turn_status": "waiting_prompt"
                    }).eq("room_code", room_code).execute()
                    st.rerun()
                else:
                    st.warning("Γράψε κάτι πριν το στείλεις.")
        elif room["turn_status"] == "finished":
            st.success("Ο γύρος ολοκληρώθηκε! Περίμενε τον Ανακριτή για Rematch.")
        else:
            st.info("Συνομιλία σε εξέλιξη... Περιμένεις νέα ερώτηση από τον Ανακριτή.")

play_game()