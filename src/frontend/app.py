import os
import streamlit as st
import httpx
import pandas as pd

# Page setup
st.set_page_config(
    page_title="KruschLaw | Air-Gapped Legal Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8085")

# Cyber-Legal Design Aesthetics
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    .stApp {
        background: radial-gradient(circle at 50% 0%, #0d1527, #030712 100%);
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, sans-serif;
    }

    /* Top Nav Container */
    .brand-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.25rem 2rem;
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 14px;
        margin-bottom: 1.75rem;
    }
    .brand-title {
        font-size: 1.85rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60a5fa, #38bdf8, #22d3ee);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.03em;
    }
    .brand-subtitle {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-left: 12px;
        font-weight: 500;
    }
    .badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(14, 165, 233, 0.12);
        color: #38bdf8;
        border: 1px solid rgba(14, 165, 233, 0.35);
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }

    /* Disclaimer Alert Box */
    .disclaimer-card {
        background: rgba(30, 41, 59, 0.45);
        border-left: 4px solid #f59e0b;
        padding: 0.9rem 1.25rem;
        border-radius: 8px;
        font-size: 0.85rem;
        color: #cbd5e1;
        line-height: 1.5;
        margin-bottom: 1.5rem;
    }

    /* Law Card Styling */
    .law-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-left: 4px solid #38bdf8;
        padding: 1.25rem;
        border-radius: 10px;
        margin-bottom: 1.15rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .law-card:hover {
        border-color: rgba(56, 189, 248, 0.5);
    }
    .law-card-header {
        font-weight: 700;
        color: #38bdf8;
        font-size: 1.05rem;
        margin-bottom: 0.35rem;
    }
    .law-card-meta {
        font-size: 0.82rem;
        color: #94a3b8;
        margin-bottom: 0.65rem;
        font-family: 'JetBrains Mono', monospace;
    }
    .law-card-body {
        font-size: 0.92rem;
        line-height: 1.55;
        color: #e2e8f0;
    }
    .sim-badge {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.35);
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    /* Input Fields & Buttons */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background-color: rgba(15, 23, 42, 0.75) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(59, 130, 246, 0.25) !important;
        border-radius: 8px !important;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2) !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #2563eb, #0284c7) !important;
        color: #ffffff !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    }
    </style>
""", unsafe_allow_html=True)

# Top Brand Header
st.markdown("""
    <div class="brand-container">
        <div>
            <span class="brand-title">⚖️ KRUSCHLAW</span>
            <span class="brand-subtitle">Private, Air-Gapped Legal RAG & Ordinance Engine</span>
        </div>
        <div style="display: flex; gap: 10px;">
            <div class="badge-pill">🛡️ Air-Gapped</div>
            <div class="badge-pill">🔒 Zero Cloud Leakage</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Ethical & Legal Compliance Notice
st.markdown("""
    <div class="disclaimer-card">
        ⚖️ <strong>Legal & Ethical Notice:</strong> KruschLaw is an open-source, offline AI assistant designed for preliminary legal research, statutory cross-referencing, and issue-spotting. It does <strong>not</strong> provide binding legal advice or establish an attorney-client relationship. All citations and reasoning must be reviewed by a licensed attorney.
    </div>
""", unsafe_allow_html=True)


# --- Helper: Backend Health & Diagnostics ---
def check_backend_health():
    try:
        resp = httpx.get(f"{BACKEND_URL}/health", timeout=3.0)
        return resp.status_code == 200, resp.json() if resp.status_code == 200 else None
    except Exception:
        return False, None

is_healthy, health_info = check_backend_health()

# --- Sidebar: Control Plane ---
with st.sidebar:
    st.markdown("### 🏛️ Control Plane")
    
    if is_healthy:
        st.success(f"🟢 Backend Online (`{health_info.get('models', {}).get('reasoning')}`)")
    else:
        st.error(f"🔴 Backend Offline at `{BACKEND_URL}`")
        st.caption("Verify the backend service is running via `docker compose up backend`.")

    st.markdown("---")
    st.markdown("#### 📥 Ingestion Center")
    st.caption("Seed or expand the on-premise statutory knowledge base.")

    # California Seed Ingestion
    if st.button("🚀 Seed California Ordinances", use_container_width=True):
        with st.spinner("Embedding and ingesting municipal tenant & noise rules..."):
            try:
                resp = httpx.post(f"{BACKEND_URL}/api/ingest/mock", timeout=60.0)
                if resp.status_code == 200:
                    inserted = resp.json().get("inserted_records", 0)
                    st.success(f"Ingested {inserted} California ordinance provisions!")
                else:
                    st.error(f"Ingestion failed: {resp.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    st.markdown("---")
    st.markdown("#### 📦 LOCUS Parquet Ingestion")
    parquet_path = st.text_input("Parquet Path on Host/Container", placeholder="/app/data/locus_ordinances.parquet")
    limit_num = st.number_input("Max Records to Embed", min_value=10, max_value=5000, value=100)

    if st.button("⚡ Ingest Parquet Dataset", use_container_width=True):
        if not parquet_path:
            st.warning("Please specify a valid Parquet file path.")
        else:
            with st.spinner(f"Ingesting up to {limit_num} records into vector store..."):
                try:
                    resp = httpx.post(
                        f"{BACKEND_URL}/api/ingest/parquet",
                        json={"file_path": parquet_path, "limit": limit_num},
                        timeout=300.0
                    )
                    if resp.status_code == 200:
                        st.success(f"Successfully inserted {resp.json().get('inserted_records')} records!")
                    else:
                        st.error(f"Ingestion error: {resp.text}")
                except Exception as e:
                    st.error(f"Pipeline error: {e}")

    st.markdown("---")
    st.markdown(
        "<div style='font-size: 0.78rem; color: #64748b; line-height: 1.4;'>"
        "<strong>KruschLaw v1.0.0</strong><br>"
        "Open-source local legal intelligence.<br>"
        "Released under the MIT License."
        "</div>",
        unsafe_allow_html=True
    )


# --- Main Dashboard Tabs ---
tab1, tab2, tab3 = st.tabs([
    "📁 Matter Portfolio",
    "⚖️ Precedent Consultation & Brief",
    "🔍 Statutory & Ordinance Explorer"
])


# --- Tab 1: Matter Portfolio ---
with tab1:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("### 📝 Log a Confidential Matter")
        st.write("Record client intake facts. Facts are automatically embedded into your local vector database.")

        with st.form("new_matter_form", clear_on_submit=True):
            title = st.text_input("Matter Title", placeholder="e.g., Tenant Eviction Notice Without Just Cause")
            desc = st.text_input("Matter Reference / Tags", placeholder="e.g., Oakland Tenant, 30-day notice, lease compliance")
            facts = st.text_area(
                "Factual Record",
                placeholder="Detail the complete factual history. For example: On February 1, 2026, the client received an eviction notice stating owner-occupancy. However, the landlord owns multiple vacant rental units in the same building and did not specify statutory relocation payments...",
                height=220
            )
            submit_btn = st.form_submit_button("🔒 Save & Generate Matter Embedding")

            if submit_btn:
                if not title or not facts:
                    st.error("Matter Title and Factual Record are required.")
                else:
                    with st.spinner("Generating 1024-dim embedding via Ollama..."):
                        try:
                            resp = httpx.post(
                                f"{BACKEND_URL}/api/cases",
                                json={"title": title, "description": desc, "facts": facts},
                                timeout=45.0
                            )
                            if resp.status_code == 201:
                                st.success("Matter saved and embedded with full on-premise confidentiality!")
                                st.rerun()
                            else:
                                st.error(f"Error ({resp.status_code}): {resp.text}")
                        except Exception as e:
                            st.error(f"Failed to reach backend: {e}")

    with col2:
        st.markdown("### 🗃️ Active Matters")
        st.write("Browse existing matters stored securely on-premise.")

        try:
            resp = httpx.get(f"{BACKEND_URL}/api/cases", timeout=10.0)
            if resp.status_code == 200:
                cases = resp.json()
                if not cases:
                    st.info("No matters logged yet. Use the form on the left to record your first case.")
                else:
                    for c in cases:
                        with st.expander(f"💼 #{c['id']} — {c['title']}", expanded=False):
                            st.markdown(f"**Reference:** `{c['description'] or 'N/A'}`")
                            st.markdown(f"**Recorded:** `{c['created_at']}`")
                            st.text_area("Facts Summary", c['facts'], height=110, disabled=True, key=f"fact_{c['id']}")
            else:
                st.error("Could not fetch active matters.")
        except Exception as e:
            st.error(f"Database error: {e}")


# --- Tab 2: Precedent Consultation & Brief ---
with tab2:
    st.markdown("### ⚖️ Automated Legal Analysis & Citation Matching")
    st.write("Match matter facts against municipal ordinances and statutes, then generate an exhaustive AI analysis brief.")

    # Load cases for selection dropdown
    matter_options = {}
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/cases", timeout=10.0)
        if resp.status_code == 200:
            for c in resp.json():
                matter_options[f"#{c['id']} — {c['title']}"] = c['id']
    except Exception:
        pass

    if not matter_options:
        st.info("Please log a matter in the 'Matter Portfolio' tab first.")
    else:
        c_sel, c_st, c_cty = st.columns([2, 1, 1])
        with c_sel:
            selected_label = st.selectbox("Select Matter to Consult", list(matter_options.keys()))
            case_id = matter_options[selected_label]
        with c_st:
            state_filter = st.text_input("State Filter (optional)", max_chars=2, placeholder="e.g., CA")
        with c_cty:
            city_filter = st.text_input("City/County Filter (optional)", placeholder="e.g., Oakland")

        retrieval_limit = st.slider("Authorities to Retrieve", min_value=1, max_value=15, value=5)

        if st.button("⚖️ Generate Sovereign Legal Brief", use_container_width=True):
            with st.spinner("Executing pgvector cosine search and running local LLM reasoning..."):
                try:
                    params = {"case_id": case_id, "limit": retrieval_limit}
                    if state_filter:
                        params["state"] = state_filter
                    if city_filter:
                        params["city"] = city_filter

                    resp = httpx.get(f"{BACKEND_URL}/api/consult", params=params, timeout=180.0)
                    if resp.status_code == 200:
                        data = resp.json()

                        b_col, l_col = st.columns([3, 2], gap="large")

                        with b_col:
                            st.markdown("### 📋 AI Legal Analysis Brief")
                            st.markdown(data["analysis"])

                        with l_col:
                            st.markdown("### 📖 Matched Legal Authorities")
                            retrieved = data.get("retrieved_laws", [])
                            if not retrieved:
                                st.warning("No statutes or ordinances matched the query filters.")
                            else:
                                for law in retrieved:
                                    sim_pct = round(law["similarity"] * 100, 1)
                                    loc_parts = []
                                    if law.get("city_or_county"):
                                        loc_parts.append(law["city_or_county"])
                                    if law.get("state"):
                                        loc_parts.append(law["state"])
                                    loc_label = ", ".join(loc_parts) if loc_parts else "Federal / General"

                                    st.markdown(f"""
                                        <div class="law-card">
                                            <div class="law-card-header">{law['title']} — {law['section']}</div>
                                            <div class="law-card-meta">
                                                <span>Jurisdiction: {loc_label}</span>
                                                <span class="sim-badge" style="float: right;">{sim_pct}% Match</span>
                                            </div>
                                            <div class="law-card-body">{law['content']}</div>
                                        </div>
                                    """, unsafe_allow_html=True)
                    else:
                        st.error(f"Consultation error ({resp.status_code}): {resp.text}")
                except Exception as e:
                    st.error(f"Inference error: {e}")


# --- Tab 3: Statutory & Ordinance Explorer ---
with tab3:
    st.markdown("### 🔍 On-Premise Vector Search Explorer")
    st.write("Test semantic retrieval directly across all ingested municipal codes, ordinances, and statutes.")

    search_query = st.text_input("Enter natural language query", placeholder="e.g., maximum allowable residential rent increase without notice")
    search_limit = st.slider("Result Count", min_value=1, max_value=20, value=6, key="search_slider")

    if st.button("Search Legal Database", use_container_width=True):
        if not search_query.strip():
            st.warning("Please enter a search query.")
        else:
            with st.spinner("Generating query vector and querying pgvector..."):
                try:
                    # Create a temporary search matter to leverage consult backend
                    temp_matter = {"title": "Explorer Query", "description": "Explorer", "facts": search_query}
                    resp = httpx.post(f"{BACKEND_URL}/api/cases", json=temp_matter, timeout=30.0)
                    if resp.status_code == 201:
                        temp_id = resp.json()["id"]
                        consult_resp = httpx.get(
                            f"{BACKEND_URL}/api/consult",
                            params={"case_id": temp_id, "limit": search_limit},
                            timeout=60.0
                        )
                        if consult_resp.status_code == 200:
                            results = consult_resp.json().get("retrieved_laws", [])
                            if not results:
                                st.info("No matching legal authorities found.")
                            else:
                                for r in results:
                                    sim_pct = round(r["similarity"] * 100, 1)
                                    loc_str = f"{r.get('city_or_county') or 'Federal'} ({r.get('state') or 'US'})"
                                    st.markdown(f"""
                                        <div class="law-card">
                                            <div class="law-card-header">{r['title']} — {r['section']}</div>
                                            <div class="law-card-meta">
                                                <span>Location: {loc_str}</span>
                                                <span class="sim-badge" style="float: right;">{sim_pct}% Relevance</span>
                                            </div>
                                            <div class="law-card-body">{r['content']}</div>
                                        </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(f"Retrieval query failed: {consult_resp.text}")
                    else:
                        st.error(f"Search embedding failed: {resp.text}")
                except Exception as e:
                    st.error(f"Search failure: {e}")
