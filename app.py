import streamlit as st
import streamlit.components.v1 as components
from gemini_helper import (
    extract_need,
    generate_volunteer_briefing,
    transcribe_audio,
    save_need,
    get_all_needs,
    resolve_need,
    add_volunteer_to_need
)
from streamlit_mic_recorder import mic_recorder

st.set_page_config(
    page_title="CommunityPulse",
    page_icon="🫀",
    layout="wide"
)

GOOGLE_MAPS_KEY = "AIzaSyBvOPSX0tm_BA3Tb68P4PRzLe3_T_2htzI"

CREDENTIALS = {
    "NGO Worker": "ngo123",
    "Office Coordinator": "office123",
    "Volunteer": "seva123"
}

if "role" not in st.session_state:
    st.session_state.role = None


def render_google_map(needs, api_key):
    markers_js = ""
    for need in needs:
        score = need.get("urgency_score", 0)
        color = "#FF0000" if score >= 70 else "#FF8C00" if score >= 40 else "#008000"
        label = "CRITICAL" if score >= 70 else "MODERATE" if score >= 40 else "LOW"
        location = need.get("location", "Unknown").replace("'", "")
        category = need.get("category", "General").replace("'", "")
        brief = need.get("crisis_brief", "").replace("'", "").replace('"', "")
        affected = need.get("affected_count", 0)
        volunteers = len(need.get("volunteers", []))
        lat = need.get("lat", 15.3647)
        lng = need.get("lng", 75.1240)

        markers_js += f"""
        {{
            lat: {lat},
            lng: {lng},
            color: "{color}",
            label: "{label}",
            info: "<div style='font-family:Arial;padding:10px;max-width:220px'><b>{location}</b><br><span style='color:{color}'>⬤ {label}</span><br>Category: {category}<br>Affected: {affected} people<br>Urgency: {score}/100<br>Volunteers: {volunteers} confirmed<br><hr style='margin:6px 0'>{brief}</div>"
        }},
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #map {{ height: 480px; width: 100%; border-radius: 12px; }}
            body {{ margin: 0; padding: 0; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            function initMap() {{
                const map = new google.maps.Map(document.getElementById("map"), {{
                    center: {{ lat: 15.3647, lng: 75.1240 }},
                    zoom: 8,
                    mapTypeControl: false,
                    streetViewControl: false
                }});
                const markers = [{markers_js}];
                const infoWindow = new google.maps.InfoWindow();
                markers.forEach(markerData => {{
                    const marker = new google.maps.Marker({{
                        position: {{ lat: markerData.lat, lng: markerData.lng }},
                        map: map,
                        icon: {{
                            path: google.maps.SymbolPath.CIRCLE,
                            scale: 14,
                            fillColor: markerData.color,
                            fillOpacity: 0.9,
                            strokeColor: "#ffffff",
                            strokeWeight: 2,
                        }}
                    }});
                    marker.addListener("click", () => {{
                        infoWindow.setContent(markerData.info);
                        infoWindow.open(map, marker);
                    }});
                }});
            }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap" async defer></script>
    </body>
    </html>
    """
    components.html(html, height=500)


# ── LOGIN ──────────────────────────────────
if st.session_state.role is None:
    st.markdown("""
        <div style='text-align:center;padding:40px 0 10px 0'>
            <h1>🫀 CommunityPulse</h1>
            <p style='color:gray;font-size:18px'>
                Community Needs Aggregation + Volunteer Matching
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.subheader("Login to Continue")
        role = st.selectbox("Who are you?", list(CREDENTIALS.keys()))
        password = st.text_input("Password", type="password")
        if st.button("Login →", use_container_width=True):
            if password == CREDENTIALS[role]:
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Wrong password. Try again.")
    st.stop()


# ── SIDEBAR ────────────────────────────────
st.sidebar.title("🫀 CommunityPulse")
st.sidebar.success(f"Logged in as: **{st.session_state.role}**")
if st.sidebar.button("Logout"):
    st.session_state.role = None
    st.rerun()


# ── PAGE 1 — NGO WORKER ────────────────────
if st.session_state.role == "NGO Worker":
    st.title("📝 Report a Community Need")
    st.caption("Describe the situation in your own words. AI will handle the rest.")
    st.divider()

    st.subheader("🎙️ Option 1 — Speak Your Report")
    audio = mic_recorder(
        start_prompt="🔴 Start Recording",
        stop_prompt="⏹️ Stop Recording",
        key="mic"
    )

    transcribed_text = ""
    if audio:
        with st.spinner("Transcribing your voice..."):
            try:
                transcribed_text = transcribe_audio(audio["bytes"])
                st.success("✅ Voice transcribed!")
                st.info(f"📝 Heard: *{transcribed_text}*")
            except Exception as e:
                st.error(f"Transcription failed: {e}")

    st.divider()
    st.subheader("⌨️ Option 2 — Type Your Report")
    typed_text = st.text_area(
        "What is happening in your community?",
        placeholder="Example: 70 families in Shirol village near Dharwad have no clean water for 3 days. Borewell broke. Two elderly people sick. Children missing school.",
        height=140
    )

    final_text = transcribed_text if transcribed_text else typed_text

    st.divider()
    if st.button("🚨 Submit Report", use_container_width=True, type="primary"):
        if not final_text.strip():
            st.warning("Please type or speak your report first.")
        else:
            with st.spinner("Gemini AI is analyzing your report..."):
                try:
                    extracted = extract_need(final_text)
                    extracted["raw_report"] = final_text
                    extracted["volunteers"] = []
                    extracted["resolved"] = False
                    save_need(extracted)

                    st.success("✅ Report submitted successfully!")
                    st.divider()

                    col1, col2, col3 = st.columns(3)
                    col1.metric("📍 Location", extracted.get("location", "Unknown"))
                    col2.metric("👥 Affected", extracted.get("affected_count", 0))
                    col3.metric("🔥 Urgency Score", f"{extracted.get('urgency_score', 0)}/100")

                    st.error(f"🔴 **Crisis Brief:** {extracted.get('crisis_brief', '')}")

                    if extracted.get("risk_flags"):
                        flags = " | ".join([f"`{r}`" for r in extracted["risk_flags"]])
                        st.write(f"⚠️ **Risk Flags:** {flags}")

                except Exception as e:
                    st.error(f"Something went wrong: {e}")


# ── PAGE 2 — OFFICE COORDINATOR ────────────
elif st.session_state.role == "Office Coordinator":
    st.title("🗺️ Community Needs Dashboard")
    st.divider()

    with st.spinner("Loading dashboard..."):
        all_needs = get_all_needs()

    active_needs = [n for n in all_needs if not n.get("resolved", False)]
    resolved_needs = [n for n in all_needs if n.get("resolved", False)]

    if not all_needs:
        st.info("No needs reported yet. NGO workers will submit from the field.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📋 Total Reported", len(all_needs))
        col2.metric("🔴 Active Needs", len(active_needs))
        col3.metric("✅ Resolved", len(resolved_needs))
        col4.metric("🤝 Volunteers Out",
            sum(len(n.get("volunteers", [])) for n in active_needs))

        st.divider()

        st.markdown(
            "🔴 **Critical** (70+) &nbsp;&nbsp; 🟡 **Moderate** (40–69)"
            " &nbsp;&nbsp; 🟢 **Low** (below 40)"
        )

        render_google_map(active_needs, GOOGLE_MAPS_KEY)

        st.divider()
        st.subheader("📋 Active Needs — Sorted by Urgency")

        sorted_active = sorted(
            active_needs,
            key=lambda x: x.get("urgency_score", 0),
            reverse=True
        )

        for need in sorted_active:
            score = need.get("urgency_score", 0)
            badge = "🔴 CRITICAL" if score >= 70 else "🟡 MODERATE" if score >= 40 else "🟢 LOW"

            with st.expander(
                f"{badge} | {need.get('location','Unknown')} | {need.get('category','General')} | Score: {score}/100"
            ):
                st.write(f"**Crisis Brief:** {need.get('crisis_brief', '')}")
                st.write(f"**Affected:** {need.get('affected_count', 0)} people")
                st.write(f"**Risk Flags:** {', '.join(need.get('risk_flags', []))}")
                st.write(f"**Volunteers:** {', '.join(need.get('volunteers', [])) or 'None yet'}")

                if st.button("✅ Mark as Resolved", key=f"resolve_{need['doc_id']}"):
                    resolve_need(need["doc_id"])
                    st.success("Marked as resolved!")
                    st.rerun()


# ── PAGE 3 — VOLUNTEER ─────────────────────
elif st.session_state.role == "Volunteer":
    st.title("🤝 Volunteer Portal")
    st.caption("Find tasks near you and make a real difference today.")
    st.divider()

    with st.spinner("Loading tasks..."):
        all_needs = get_all_needs()

    active_needs = [n for n in all_needs if not n.get("resolved", False)]

    if not active_needs:
        st.info("No active needs right now. Check back soon.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            volunteer_name = st.text_input("Your Name")
        with col2:
            volunteer_skill = st.selectbox(
                "Your Skill",
                ["General Assistance", "Medical", "Logistics",
                 "Teaching/Awareness", "Engineering/Repair"]
            )

        category_filter = st.selectbox(
            "Filter by Need Type",
            ["All", "Water", "Food", "Medical", "Infrastructure", "Education"]
        )

        st.divider()
        st.subheader("📌 Open Tasks Near You")

        filtered = [
            n for n in active_needs
            if category_filter == "All" or n.get("category") == category_filter
        ]
        filtered = sorted(
            filtered,
            key=lambda x: x.get("urgency_score", 0),
            reverse=True
        )

        if not filtered:
            st.info("No tasks match your filter.")

        for need in filtered:
            score = need.get("urgency_score", 0)
            badge = "🔴" if score >= 70 else "🟡" if score >= 40 else "🟢"

            with st.expander(
                f"{badge} {need.get('location','Unknown')} — {need.get('category','General')} | Urgency: {score}/100"
            ):
                st.write(f"**Situation:** {need.get('crisis_brief', '')}")
                st.write(f"**Affected:** {need.get('affected_count', 0)} people")
                st.write(f"**Volunteers so far:** {len(need.get('volunteers', []))}")

                if volunteer_name:
                    if st.button(
                        "✅ Register for this task",
                        key=f"reg_{need['doc_id']}"
                    ):
                        added = add_volunteer_to_need(need["doc_id"], volunteer_name)
                        if added:
                            with st.spinner("Generating your personal briefing..."):
                                briefing = generate_volunteer_briefing(
                                    need, volunteer_name, volunteer_skill
                                )
                            st.success("You're registered! 🎉")
                            st.info(f"📋 **Your Task Briefing:**\n\n{briefing}")
                        else:
                            st.warning("You're already registered for this task.")
                else:
                    st.warning("Enter your name above to register.")