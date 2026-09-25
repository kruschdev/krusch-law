import os
import streamlit as st
import httpx

# Page setup
st.set_page_config(
    page_title="KruschLaw | Air-Gapped Legal Intelligence (Research Prototype)",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8085")
DEFAULT_API_KEY = os.getenv("API_KEY", "")


def get_auth_headers() -> dict:
    """Return authorization headers with configured API key if available."""
    key = st.session_state.get("api_key", DEFAULT_API_KEY)
    headers = {}
    if key:
        headers["X-API-Key"] = key.strip()
    return headers


# Cyber-Legal Design Aesthetics
st.markdown("""
    <style>
    /* True Air-Gapped Offline Font Stack (Zero Outbound Network Calls) */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #0d1527, #030712 100%);
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
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
    .badge-prototype {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
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
        font-size: 1.05rem;
        color: #e2e8f0;
        margin-bottom: 0.35rem;
    }
    .law-card-meta {
        font-size: 0.82rem;
        color: #94a3b8;
        margin-bottom: 0.75rem;
    }
    .law-card-body {
        font-size: 0.88rem;
        color: #cbd5e1;
        line-height: 1.55;
    }
    .sim-badge {
        display: inline-block;
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        padding: 0.15rem 0.5rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-supported {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.76rem;
    }
    .badge-invented {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.76rem;
    }
    .badge-wrong-prop {
        background: rgba(249, 115, 22, 0.15);
        color: #fb923c;
        border: 1px solid rgba(249, 115, 22, 0.4);
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.76rem;
    }
    .badge-stale {
        background: rgba(168, 85, 247, 0.15);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.4);
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.76rem;
    }
    .badge-abstain {
        background: rgba(234, 179, 8, 0.15);
        color: #facc15;
        border: 1px solid rgba(234, 179, 8, 0.4);
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.76rem;
    }
    .authority-tag {
        display: inline-block;
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
        padding: 0.1rem 0.45rem;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 6px;
    }
    </style>
""", unsafe_allow_html=True)

# Top Bar Branding
st.markdown("""
    <div class="brand-container">
        <div style="display: flex; align-items: baseline;">
            <span class="brand-title">⚖️ KruschLaw</span>
            <span class="brand-subtitle">Air-Gapped Sovereign Legal Engine</span>
        </div>
        <div style="display: flex; gap: 8px;">
            <div class="badge-pill badge-prototype">
                🔬 Sovereign Edition (v0.3.0)
            </div>
            <div class="badge-pill">
                🔒 100% On-Premise Air-Gap
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# Ethical & Legal UPL Disclaimer
st.markdown("""
    <div class="disclaimer-card">
        <strong>⚠️ Research Prototype & Mandatory Verification Notice</strong><br>
        KruschLaw is an open-source experimental research prototype exploring local, air-gapped retrieval-augmented generation for legal research.
        It does <strong>NOT</strong> constitute legal advice, representation, or an attorney-client relationship.
        Seed statutes are paraphrased demo fixtures. An attorney admitted in the governing jurisdiction must independently Shepardize and verify all cited sections and quotes prior to taking formal legal action.
    </div>
""", unsafe_allow_html=True)


# --- Helper to Check Backend Status ---
def check_backend_health():
    try:
        resp = httpx.get(f"{BACKEND_URL}/health", timeout=3.0)
        return resp.status_code == 200, resp.json() if resp.status_code == 200 else None
    except Exception:
        return False, None


is_healthy, health_info = check_backend_health()


# --- Cached Matter List Helper ---
def fetch_cases_list():
    """Fetch active matters from backend with short caching."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/cases", headers=get_auth_headers(), timeout=10.0)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


# --- Sidebar: Control Plane ---
with st.sidebar:
    st.markdown("### 🏛️ Control Plane")

    if is_healthy:
        sec = health_info.get("security", {})
        auth_active = sec.get("auth_enabled", False)
        st.success(f"🟢 Backend Online (`{health_info.get('models', {}).get('reasoning')}`)")

        if auth_active:
            st.info("🔒 Matter Authorization Active")
            user_key = st.text_input(
                "API Access Key",
                value=st.session_state.get("api_key", DEFAULT_API_KEY),
                type="password",
                help="Provided via API_KEY env var or entered here"
            )
            st.session_state["api_key"] = user_key
        else:
            st.caption("ℹ️ Dev Mode: Open Access (No API_KEY set)")
    else:
        st.error(f"🔴 Backend Offline at `{BACKEND_URL}`")
        st.caption("Verify the backend service is running via `docker compose up backend`.")

    st.markdown("---")
    st.markdown("#### 📥 Ingestion Center")
    st.caption("Seed or expand the on-premise statutory knowledge base.")

    # California Seed Ingestion
    if st.button("🚀 Seed Paraphrased Demo Fixtures", use_container_width=True):
        with st.spinner("Embedding and ingesting demo California ordinance fixtures..."):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/api/ingest/mock",
                    headers=get_auth_headers(),
                    timeout=60.0
                )
                if resp.status_code == 200:
                    inserted = resp.json().get("inserted_records", 0)
                    st.success(f"Ingested {inserted} demo ordinance fixtures!")
                else:
                    st.error(f"Ingestion failed: {resp.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    st.markdown("---")
    st.markdown("#### 📄 KruschNexus Document Ingestion")
    st.caption("Universal sovereign ingest: PDF (with OCR), DOCX, EML, MD, TXT.")

    upload_file = st.file_uploader(
        "Upload Legal Document",
        type=["pdf", "docx", "eml", "msg", "txt", "md", "csv"],
        help="Upload contracts, discovery, or case filings directly into the local vector store."
    )
    doc_type_choice = st.selectbox(
        "Document Classification",
        ["matter_facts", "work_product", "authority"],
        format_func=lambda x: {
            "matter_facts": "📁 Matter Facts / Evidence",
            "work_product": "⚖️ Attorney Work Product",
            "authority": "📜 Controlling Authority"
        }.get(x, x)
    )
    active_matters = fetch_cases_list()
    matter_choices = {"None (General Knowledge)": None}
    for m in active_matters:
        matter_choices[f"#{m['id']} — {m['title'][:25]}..."] = m['id']
    chosen_matter_label = st.selectbox("Assign to Matter", list(matter_choices.keys()))
    chosen_matter_id = matter_choices[chosen_matter_label]

    if st.button("🚀 Ingest via KruschNexus", use_container_width=True):
        if not upload_file:
            st.warning("Please select a file to upload.")
        else:
            with st.spinner(f"Parsing '{upload_file.name}' with KruschNexus and embedding chunks..."):
                try:
                    file_bytes = upload_file.getvalue()
                    files_payload = {
                        "file": (upload_file.name, file_bytes, upload_file.type or "application/octet-stream")
                    }
                    data_payload = {
                        "doc_type": doc_type_choice
                    }
                    if chosen_matter_id is not None:
                        data_payload["matter_id"] = str(chosen_matter_id)

                    resp = httpx.post(
                        f"{BACKEND_URL}/api/ingest/upload",
                        files=files_payload,
                        data=data_payload,
                        headers=get_auth_headers(),
                        timeout=180.0
                    )
                    if resp.status_code == 200:
                        res = resp.json()
                        st.success(
                            f"✅ Ingested **{res['filename']}**!\n\n"
                            f"• **Pages:** {res['pages_in']}\n"
                            f"• **Chunks:** {res['chunks_out']}\n"
                            f"• **Vectors Inserted:** {res['records_inserted']}\n"
                            f"• **OCR Pages:** {res.get('ocr_pages') or 'None'}\n"
                            f"• **Latency:** {res['duration_ms']:.1f}ms"
                        )
                    else:
                        st.error(f"Ingestion failed ({resp.status_code}): {resp.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    st.markdown("---")
    st.markdown("#### 📦 LOCUS Parquet Ingestion")
    st.caption("LOCUS-v1 is licensed under **CC-BY-NC-4.0** (non-commercial research only).")
    parquet_path = st.text_input("Parquet Path in `/app/data`", placeholder="/app/data/ingest/ordinances.parquet")
    limit_num = st.number_input("Max Records to Embed", min_value=10, max_value=5000, value=100)
    async_mode = st.checkbox("Run in Background (Async)", value=False)

    if st.button("⚡ Ingest Parquet Dataset", use_container_width=True):
        if not parquet_path:
            st.warning("Please specify a valid Parquet file path.")
        else:
            if async_mode:
                try:
                    resp = httpx.post(
                        f"{BACKEND_URL}/api/ingest/parquet/async",
                        json={"file_path": parquet_path, "limit": limit_num},
                        headers=get_auth_headers(),
                        timeout=30.0
                    )
                    if resp.status_code in (200, 202):
                        job_id = resp.json().get("job_id")
                        st.info(f"Queued background ingestion job: `{job_id}`")
                    else:
                        st.error(f"Async dispatch error: {resp.text}")
                except Exception as e:
                    st.error(f"Dispatch error: {e}")
            else:
                with st.spinner(f"Ingesting up to {limit_num} records into vector store..."):
                    try:
                        resp = httpx.post(
                            f"{BACKEND_URL}/api/ingest/parquet",
                            json={"file_path": parquet_path, "limit": limit_num},
                            headers=get_auth_headers(),
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
        "<strong>KruschLaw v0.3.0 (Sovereign Edition)</strong><br>"
        "Open-source local legal intelligence.<br>"
        "Released under the MIT License."
        "</div>",
        unsafe_allow_html=True
    )


# --- Main Dashboard Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📁 Matter Portfolio",
    "⚖️ Precedent Consultation & Brief",
    "🛡️ Defense Checklist & Demand Letter",
    "🔍 Statutory & Evidence Explorer",
    "📜 Statutory Traceability & Audit Registry"
])


# --- Tab 1: Matter Portfolio ---
with tab1:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("### 📝 Log a Confidential Matter")
        st.write("Record client intake facts. Facts are automatically embedded into your local vector database.")

        with st.form("new_matter_form", clear_on_submit=True):
            title = st.text_input("Matter Title", placeholder="e.g., Tenant Eviction Notice Without Just Cause")
            c_num, c_client = st.columns(2)
            with c_num:
                matter_no = st.text_input("Matter # (optional)", placeholder="e.g., 2026-CA-014")
            with c_client:
                client_id = st.text_input("Client ID / Code (optional)", placeholder="e.g., Confidential Party A")
            desc = st.text_input("Matter Reference / Tags", placeholder="e.g., Oakland Tenant, 30-day notice, lease compliance")
            facts = st.text_area(
                "Factual Record",
                placeholder="Detail the complete factual history. For example: On February 1, 2026, the client received an eviction notice stating owner-occupancy. However, the landlord owns multiple vacant rental units in the same building and did not specify statutory relocation payments...",
                height=200
            )
            submit_btn = st.form_submit_button("🔒 Save & Generate Matter Embedding")

            if submit_btn:
                if not title or not facts:
                    st.error("Matter Title and Factual Record are required.")
                else:
                    with st.spinner("Generating dense embedding via Ollama..."):
                        try:
                            payload = {
                                "title": title,
                                "matter_number": matter_no or None,
                                "client_name": client_id or None,
                                "description": desc,
                                "facts": facts
                            }
                            resp = httpx.post(
                                f"{BACKEND_URL}/api/cases",
                                json=payload,
                                headers=get_auth_headers(),
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

        cases = fetch_cases_list()
        if not cases:
            st.info("No matters logged yet. Use the form on the left to record your first case.")
        else:
            for c in cases:
                m_label = f"💼 #{c['id']} — {c['title']}"
                if c.get("matter_number"):
                    m_label = f"💼 [{c['matter_number']}] #{c['id']} — {c['title']}"
                with st.expander(m_label, expanded=False):
                    if c.get("client_name"):
                        st.markdown(f"**Client/Party:** `{c['client_name']}`")
                    st.markdown(f"**Reference:** `{c['description'] or 'N/A'}`")
                    st.markdown(f"**Recorded:** `{c['created_at']}`")
                    st.text_area("Facts Summary", c['facts'], height=100, disabled=True, key=f"fact_{c['id']}")

                    st.markdown("##### 📎 Ingest Document for this Matter (KruschNexus)")
                    doc_upload = st.file_uploader(
                        f"Attach Document to #{c['id']}",
                        type=["pdf", "docx", "eml", "msg", "txt", "md"],
                        key=f"doc_up_{c['id']}"
                    )
                    doc_kind = st.selectbox(
                        "Document Type",
                        ["matter_facts", "work_product", "authority"],
                        key=f"kind_{c['id']}"
                    )
                    if st.button(f"📥 Parse & Ingest into Matter #{c['id']}", key=f"ingest_btn_{c['id']}"):
                        if doc_upload:
                            with st.spinner("Processing through KruschNexus engine..."):
                                try:
                                    resp = httpx.post(
                                        f"{BACKEND_URL}/api/ingest/upload",
                                        files={"file": (doc_upload.name, doc_upload.getvalue(), doc_upload.type or "application/octet-stream")},
                                        data={"matter_id": str(c['id']), "doc_type": doc_kind},
                                        headers=get_auth_headers(),
                                        timeout=180.0
                                    )
                                    if resp.status_code == 200:
                                        res = resp.json()
                                        st.success(f"✅ Ingested {res['filename']} ({res['pages_in']} pages, {res['chunks_out']} chunks)")
                                    else:
                                        st.error(f"Error ({resp.status_code}): {resp.text}")
                                except Exception as e:
                                    st.error(f"Failed to ingest: {e}")
                        else:
                            st.warning("Please choose a file to attach.")

                    st.markdown("---")
                    c_del, c_purge = st.columns(2)
                    with c_del:
                        if st.button(f"🗑️ Soft Delete #{c['id']}", key=f"del_{c['id']}"):
                            try:
                                del_resp = httpx.delete(
                                    f"{BACKEND_URL}/api/cases/{c['id']}",
                                    headers=get_auth_headers(),
                                    timeout=10.0
                                )
                                if del_resp.status_code == 200:
                                    st.success(f"Matter #{c['id']} soft-deleted.")
                                    st.rerun()
                                else:
                                    st.error(f"Delete failed: {del_resp.text}")
                            except Exception as e:
                                st.error(f"Error deleting matter: {e}")
                    with c_purge:
                        if st.button(f"🔥 Hard Purge #{c['id']}", key=f"purge_{c['id']}", help="Permanently destroys matter record, facts, evidence chunks, and all embeddings."):
                            try:
                                purge_resp = httpx.delete(
                                    f"{BACKEND_URL}/api/cases/{c['id']}/purge",
                                    headers=get_auth_headers(),
                                    timeout=10.0
                                )
                                if purge_resp.status_code == 200:
                                    st.success(f"Matter #{c['id']} permanently purged from sovereign database.")
                                    st.rerun()
                                else:
                                    st.error(f"Purge failed: {purge_resp.text}")
                            except Exception as e:
                                st.error(f"Error purging matter: {e}")


# --- Tab 2: Precedent Consultation & Brief ---
with tab2:
    st.markdown("### ⚖️ Automated Legal Analysis & Citation Matching")
    st.write("Match matter facts against municipal ordinances and statutes, then generate an exhaustive AI analysis brief.")

    # Load cases for selection dropdown
    cases_for_consult = fetch_cases_list()
    matter_options = {f"#{c['id']} — {c['title']}": c['id'] for c in cases_for_consult}

    if not matter_options:
        st.info("Please log a matter in the 'Matter Portfolio' tab first.")
    else:
        c_sel, c_st, c_cty, c_top = st.columns([2, 1, 1, 1])
        with c_sel:
            selected_label = st.selectbox("Select Matter to Consult", list(matter_options.keys()))
            case_id = matter_options[selected_label]
        with c_st:
            state_filter = st.text_input("State Filter (optional)", max_chars=2, placeholder="e.g., CA")
        with c_cty:
            city_filter = st.text_input("City Filter (optional)", placeholder="e.g., Oakland")
        with c_top:
            topic_filter = st.text_input("Topic Filter (optional)", placeholder="e.g., Housing")

        retrieval_limit = st.slider("Authorities to Retrieve", min_value=1, max_value=15, value=5)

        if st.button("⚖️ Generate Sovereign Legal Brief", use_container_width=True):
            with st.spinner("Executing hybrid tsvector + pgvector search and running local LLM reasoning..."):
                try:
                    params = {"case_id": case_id, "limit": retrieval_limit}
                    if state_filter:
                        params["state"] = state_filter
                    if city_filter:
                        params["city"] = city_filter
                    if topic_filter:
                        params["topic"] = topic_filter

                    resp = httpx.get(
                        f"{BACKEND_URL}/api/consult",
                        params=params,
                        headers=get_auth_headers(),
                        timeout=180.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()

                        b_col, l_col = st.columns([3, 2], gap="large")

                        with b_col:
                            st.markdown("### 📋 AI Legal Analysis Brief")
                            if "CONTROLLING STATUTE UNCERTAIN" in data.get("analysis", ""):
                                st.warning("⚠️ **CONTROLLING STATUTE UNCERTAIN**: Proposed statutory preemption or amendment links are pending human attorney review in Tab 5. Unconfirmed links do not dictate binding precedent.")
                            st.markdown(data["analysis"])

                            # Brief Export (Markdown + Word .docx)
                            g_stats = data.get("grounding_stats") or {}
                            claims_audit = data.get("claims_audit") or []
                            spotted = data.get("spotted_issues") or []

                            if spotted:
                                st.markdown("#### 🎯 Spotted Legal Issues & Causes of Action")
                                for sp in spotted:
                                    st.info(f"**{sp['issue']}** ({sp['jurisdiction']})\n\nGoverning Authorities: `{sp['governing_authorities']}`")

                            exp_c1, exp_c2 = st.columns(2)
                            with exp_c1:
                                st.download_button(
                                    label="📥 Export Markdown (.md)",
                                    data=data["analysis"],
                                    file_name=f"kruschlaw_brief_matter_{case_id}.md",
                                    mime="text/markdown",
                                    use_container_width=True
                                )
                            with exp_c2:
                                try:
                                    docx_resp = httpx.post(
                                        f"{BACKEND_URL}/api/consult/export/docx",
                                        json={
                                            "brief_content": data["analysis"],
                                            "matter_title": data.get("case", {}).get("title", f"Matter #{case_id}"),
                                            "matter_number": f"MATTER-{case_id:04d}",
                                            "claims_audit": claims_audit,
                                            "retrieved_laws": data.get("retrieved_laws", [])
                                        },
                                        headers=get_auth_headers(),
                                        timeout=30.0
                                    )
                                    if docx_resp.status_code == 200:
                                        docx_data = docx_resp.content
                                    else:
                                        from src.backend.export import generate_brief_docx
                                        docx_data = generate_brief_docx(
                                            brief_content=data["analysis"],
                                            matter_title=data.get("case", {}).get("title", f"Matter #{case_id}"),
                                            matter_number=f"MATTER-{case_id:04d}",
                                            claims_audit=claims_audit,
                                            retrieved_laws=data.get("retrieved_laws", []),
                                            disclaimer=data.get("disclaimer", "")
                                        )
                                    st.download_button(
                                        label="📄 Export Word (.docx)",
                                        data=docx_data,
                                        file_name=f"kruschlaw_brief_matter_{case_id}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        use_container_width=True
                                    )
                                except Exception as e:
                                    st.caption(f"DOCX Export: {e}")

                            # Assertion-Level Grounding Scorecard & Table
                            st.markdown("---")
                            st.markdown("### 🛡️ Assertion-Level Grounding Audit")

                            if g_stats:
                                m1, m2, m3, m4 = st.columns(4)
                                with m1:
                                    st.metric("Pass Rate", f"{g_stats.get('pass_rate', 100.0)}%")
                                with m2:
                                    st.metric("Total Claims", g_stats.get("total_claims", 0))
                                with m3:
                                    st.metric("Supported", g_stats.get("supported_claims", 0))
                                with m4:
                                    flagged = g_stats.get("unsupported_claims", 0)
                                    st.metric("Flagged Issues", flagged)

                            if claims_audit:
                                st.markdown("#### 🔬 Side-by-Side Claim Verification")
                                for c_idx, c_item in enumerate(claims_audit, 1):
                                    status = c_item.get("status", "supported")
                                    badge_html = {
                                        "supported": '<span class="badge-supported">🟢 Supported</span>',
                                        "invented_citation": '<span class="badge-invented">🔴 Invented Citation</span>',
                                        "wrong_proposition": '<span class="badge-wrong-prop">🟠 Wrong Proposition</span>',
                                        "stale_law": '<span class="badge-stale">🟣 Stale / Repealed Law</span>'
                                    }.get(status, f'<span class="badge-supported">{status}</span>')

                                    with st.expander(f"Claim #{c_idx} [{c_item.get('citation') or 'Context'}]: {c_item['claim'][:60]}..."):
                                        st.markdown(f"**Assertion:** {c_item['claim']}")
                                        st.markdown(f"**Status:** {badge_html}", unsafe_allow_html=True)
                                        if c_item.get("reason"):
                                            st.markdown(f"**Grounding Analysis:** {c_item['reason']}")
                                        if c_item.get("source_excerpt"):
                                            st.markdown(f"**Source Legal Excerpt:**\n> {c_item['source_excerpt']}")

                        with l_col:
                            st.markdown("### 📖 Matched Legal Authorities")
                            retrieved = data.get("retrieved_laws", [])
                            if not retrieved:
                                st.warning("No statutes or ordinances matched the query filters.")
                            else:
                                for law in retrieved:
                                    sim_pct = round(law["similarity"] * 100, 1)
                                    loc_parts = []
                                    if law.get("city"):
                                        loc_parts.append(law["city"])
                                    elif law.get("city_or_county"):
                                        loc_parts.append(law["city_or_county"])
                                    if law.get("state"):
                                        loc_parts.append(law["state"])
                                    loc_label = ", ".join(loc_parts) if loc_parts else "Federal / General"

                                    topic_str = f" • {law['topic']}" if law.get("topic") else ""
                                    auth_class = law.get("authority_class") or "municipal_ordinance"
                                    h_level = law.get("hierarchy_level") or "section"

                                    auth_tags = (
                                        f'<span class="authority-tag">{auth_class.replace("_", " ").title()}</span>'
                                        f'<span class="authority-tag">{h_level.title()}</span>'
                                    )
                                    if law.get("repealed"):
                                        auth_tags += '<span class="badge-stale">REPEALED</span>'

                                    st.markdown(f"""
                                        <div class="law-card">
                                            <div class="law-card-header">{law['title']} — {law['section']}</div>
                                            <div style="margin-bottom: 0.4rem;">{auth_tags}</div>
                                            <div class="law-card-meta">
                                                <span>Jurisdiction: {loc_label}{topic_str}</span>
                                                <span class="sim-badge" style="float: right;">{sim_pct}% Relevance</span>
                                            </div>
                                            <div class="law-card-body">{law['content']}</div>
                                        </div>
                                    """, unsafe_allow_html=True)
                    else:
                        st.error(f"Consultation error ({resp.status_code}): {resp.text}")
                except Exception as e:
                    st.error(f"Inference error: {e}")



# --- Tab 3: Defense Checklist & Demand Letter ---
with tab3:
    st.markdown("### 🛡️ Evidentiary Defense Checklist & Formal Statutory Demand Letter")
    st.write(
        "Audit matter facts against binding statutory deadlines (e.g. 21-day deposit return under § 1950.5, "
        "3-court-day cure under CCP § 1161, 180-day retaliation presumption under § 1942.5) "
        "and assemble rigid statutory letters asserting mandatory legal citations."
    )

    cases_for_def = fetch_cases_list()
    matter_def_options = {f"#{c['id']} — {c['title']}": c for c in cases_for_def}

    if not matter_def_options:
        st.info("Please log a confidential matter in the 'Matter Portfolio' tab first.")
    else:
        c_sel_mat, c_as_of = st.columns([2, 1])
        with c_sel_mat:
            sel_def_label = st.selectbox("Select Matter for Defense Analysis", list(matter_def_options.keys()), key="def_matter_sel")
            selected_case = matter_def_options[sel_def_label]
            def_case_id = selected_case["id"]
        with c_as_of:
            def_as_of_date = st.text_input("As-of Valuation Date (optional)", placeholder="e.g., 2026-03-01", key="def_as_of")

        def_subtab1, def_subtab2, def_subtab3 = st.tabs([
            "📋 Statutory Defense Checklist",
            "✉️ Statutory Demand Letter Assembly",
            "✍️ Attorney Verification & Feedback"
        ])

        with def_subtab1:
            st.markdown("#### ⏱️ Binding Statutory Deadlines & Fact Audit")
            if st.button("🔍 Generate / Refresh Defense Checklist", key="btn_gen_chk", use_container_width=True):
                st.session_state[f"chk_ran_{def_case_id}"] = True

            if st.session_state.get(f"chk_ran_{def_case_id}"):
                with st.spinner("Auditing factual record and computing statutory limitation windows..."):
                    try:
                        chk_params = {}
                        if def_as_of_date.strip():
                            chk_params["as_of_date"] = def_as_of_date.strip()
                        chk_resp = httpx.get(
                            f"{BACKEND_URL}/api/cases/{def_case_id}/defense-checklist",
                            params=chk_params,
                            headers=get_auth_headers(),
                            timeout=20.0
                        )
                        if chk_resp.status_code == 200:
                            chk_data = chk_resp.json()
                            st.session_state[f"chk_data_{def_case_id}"] = chk_data
                        else:
                            st.error(f"Failed to generate checklist ({chk_resp.status_code}): {chk_resp.text}")
                    except Exception as e:
                        st.error(f"Checklist error: {e}")

            chk_data = st.session_state.get(f"chk_data_{def_case_id}")
            if chk_data:
                st.markdown(f"**Identified {chk_data.get('total_defenses_spotted', 0)} Governed Defenses for Matter #{def_case_id}:**")

                for item in chk_data.get("defenses", []):
                    status = item.get("status", "")
                    if status == "POTENTIAL_VIOLATION":
                        stat_badge = '<span class="badge-invented">⚠️ POTENTIAL VIOLATION</span>'
                    elif status == "COMPLIANT":
                        stat_badge = '<span class="badge-supported">✅ COMPLIANT</span>'
                    elif status == "NEEDS_DOCUMENTATION":
                        stat_badge = '<span class="badge-wrong-prop">📋 NEEDS DOCUMENTATION</span>'
                    else:
                        stat_badge = f'<span class="authority-tag">{status}</span>'

                    st.markdown(f"""
                        <div class="law-card" style="border-left-color: #f59e0b;">
                            <div class="law-card-header">🛡️ {item['issue']}</div>
                            <div style="margin-bottom: 0.45rem;">
                                <span class="authority-tag">📜 {item['controlling_citation']}</span>
                                <span class="authority-tag" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24;">⏱️ {item['statutory_deadline']}</span>
                                {stat_badge}
                            </div>
                            <div class="law-card-body">
                                <strong>Remedy / Defense Value:</strong> {item.get('statutory_remedy', 'N/A')}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    with st.expander(f"Inspect Statutory Elements & Evidence Requirements ({item['issue']})", expanded=False):
                        for el in item.get("elements", []):
                            v_icon = "✅" if el.get("verified") else "❌"
                            v_text = "Verified in Factual Record" if el.get("verified") else "Unverified / Missing in Record"
                            st.markdown(f"- **{v_icon} {el.get('check_item')}** ({v_text})")
                            if el.get("evidence_found"):
                                st.caption(f"  Evidence: {el['evidence_found']}")
                            st.caption(f"  *Advisory: {el.get('advisory')}*")
                        if item.get("required_evidence"):
                            st.markdown("**Recommended Documentary Evidence:**")
                            for req_ev in item["required_evidence"]:
                                st.markdown(f"  • `{req_ev}`")

        with def_subtab2:
            st.markdown("#### 📜 Formal Statutory Demand Letter & Legal Notice Assembly")
            st.write("Generate rigid demand notices bound to statutory phrasing. Missing factual slots will be explicitly called out as statutory coverage gaps.")

            c_lt, c_asof = st.columns([2, 1])
            with c_lt:
                letter_type = st.selectbox(
                    "Letter Type",
                    [
                        ("security_deposit_demand", "💰 Security Deposit Bad-Faith Return Demand (Cal. Civ. Code § 1950.5)"),
                        ("habitability_repair_notice", "🏚️ Notice of Substandard Conditions & Repair Demand (§ 1941.1 / § 1942)"),
                        ("defective_notice_response", "⚠️ Formal Objection to Defective Notice to Pay or Quit (CCP § 1161 / OMC § 8.22.360)")
                    ],
                    format_func=lambda x: x[1]
                )[0]
            with c_asof:
                letter_as_of = st.text_input("Notice Date / As-of Date", value=def_as_of_date or "", placeholder="YYYY-MM-DD", key="letter_asof_input")

            c_rec_name, c_snd_name = st.columns(2)
            with c_rec_name:
                recipient_name = st.text_input("Recipient / Landlord Name", placeholder="e.g., Skyline Property Management, LLC", key="rec_name")
            with c_snd_name:
                default_sender = selected_case.get("client_name") or "Tenant Client"
                sender_name = st.text_input("Sender / Tenant Full Name", value=default_sender, key="snd_name")

            recipient_addr = st.text_input("Recipient Mailing Address", placeholder="e.g., 100 Grand Ave, Suite 400, Oakland, CA 94612", key="rec_addr")

            if st.button("⚡ Assemble Formal Statutory Letter", key="btn_assemble_letter", use_container_width=True):
                if not recipient_name.strip() or not recipient_addr.strip():
                    st.error("Recipient Name and Mailing Address are required for formal legal correspondence.")
                else:
                    with st.spinner("Assembling statutory notice from verified matter facts and legal authorities..."):
                        try:
                            payload = {
                                "letter_type": letter_type,
                                "recipient_name": recipient_name.strip(),
                                "recipient_address": recipient_addr.strip(),
                                "sender_name": sender_name.strip() or None,
                                "as_of_date": letter_as_of.strip() or None
                            }
                            ltr_resp = httpx.post(
                                f"{BACKEND_URL}/api/cases/{def_case_id}/assemble-letter",
                                json=payload,
                                headers=get_auth_headers(),
                                timeout=25.0
                            )
                            if ltr_resp.status_code == 200:
                                st.session_state[f"ltr_res_{def_case_id}"] = ltr_resp.json()
                                st.success("Statutory letter successfully assembled!")
                            else:
                                st.error(f"Letter assembly failed ({ltr_resp.status_code}): {ltr_resp.text}")
                        except Exception as e:
                            st.error(f"Letter assembly error: {e}")

            ltr_data = st.session_state.get(f"ltr_res_{def_case_id}")
            if ltr_data:
                st.markdown("---")
                st.markdown(f"### 📄 {ltr_data.get('title', 'Statutory Demand Letter')}")
                st.markdown(f"**Subject:** `{ltr_data.get('subject', '')}`")

                cit_badges = " ".join([f'<span class="authority-tag">⚖️ {cit}</span>' for cit in ltr_data.get("mandatory_citations", [])])
                st.markdown(f"**Controlling Citations:** {cit_badges}", unsafe_allow_html=True)

                gaps = ltr_data.get("coverage_gaps", [])
                if gaps:
                    st.warning("⚠️ **STATUTORY COVERAGE GAPS DETECTED**: The factual record lacked necessary data for the following items:")
                    for g in gaps:
                        st.markdown(f"• `{g}`")

                st.text_area("Letter Text", value=ltr_data.get("letter_body", ""), height=400, key="ltr_body_display")

                c_dl_txt, c_dl_md = st.columns(2)
                with c_dl_txt:
                    st.download_button(
                        label="📥 Download Plain Text (.txt)",
                        data=ltr_data.get("letter_body", ""),
                        file_name=f"Matter_{def_case_id}_{ltr_data.get('letter_type')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                with c_dl_md:
                    st.download_button(
                        label="📥 Download Markdown (.md)",
                        data=f"# {ltr_data.get('title')}\n\n**Subject:** {ltr_data.get('subject')}\n\n{ltr_data.get('letter_body')}",
                        file_name=f"Matter_{def_case_id}_{ltr_data.get('letter_type')}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

        with def_subtab3:
            st.markdown("#### ✍️ Human Attorney Claim Annotation & Local Verification")
            st.write("Annotate individual propositions, record accept/reject decisions, and log feedback for local refinement without cloud telemetry.")

            with st.form(f"attorney_fb_form_{def_case_id}", clear_on_submit=True):
                fb_claim = st.text_input("Legal Claim / Proposition Under Review", placeholder="e.g., Landlord forfeited right to retain deposit due to 21-day failure.")
                fb_cit = st.text_input("Statutory Citation", placeholder="e.g., Cal. Civ. Code § 1950.5(g)")
                fb_decision = st.selectbox("Attorney Decision", ["approved", "rejected", "flagged_for_research"])
                fb_correction = st.text_input("Correction / Replacement Citation (if rejected)", placeholder="e.g., § 1950.5(l) requires proving bad faith.")
                fb_notes = st.text_area("Supervising Attorney Notes", placeholder="e.g., Verified against Alameda County Superior Court local practice.")
                fb_submit = st.form_submit_button("💾 Save Verification Feedback")

                if fb_submit:
                    if not fb_claim.strip():
                        st.error("Claim text is required.")
                    else:
                        try:
                            fb_payload = {
                                "feedbacks": [
                                    {
                                        "claim_text": fb_claim.strip(),
                                        "citation": fb_cit.strip() or None,
                                        "decision": fb_decision,
                                        "correction": fb_correction.strip() or None,
                                        "attorney_notes": fb_notes.strip() or None
                                    }
                                ]
                            }
                            fb_resp = httpx.post(
                                f"{BACKEND_URL}/api/cases/{def_case_id}/claims/feedback",
                                json=fb_payload,
                                headers=get_auth_headers(),
                                timeout=15.0
                            )
                            if fb_resp.status_code == 200:
                                st.success("Attorney feedback saved to local verification signal store.")
                                st.rerun()
                            else:
                                st.error(f"Error saving feedback ({fb_resp.status_code}): {fb_resp.text}")
                        except Exception as e:
                            st.error(f"Feedback save error: {e}")

            st.markdown("---")
            st.markdown("##### 📜 Recorded Attorney Verification History")
            try:
                hist_resp = httpx.get(
                    f"{BACKEND_URL}/api/cases/{def_case_id}/claims/feedback",
                    headers=get_auth_headers(),
                    timeout=15.0
                )
                if hist_resp.status_code == 200:
                    fb_list = hist_resp.json()
                    if not fb_list:
                        st.info("No attorney verification feedback recorded for this matter yet.")
                    else:
                        for fb in fb_list:
                            dec = fb.get("decision", "")
                            if dec == "approved":
                                d_badge = '<span class="badge-supported">✅ APPROVED</span>'
                            elif dec == "rejected":
                                d_badge = '<span class="badge-invented">❌ REJECTED</span>'
                            else:
                                d_badge = '<span class="badge-wrong-prop">🔍 FLAGGED FOR RESEARCH</span>'

                            cit_info = f" • Citation: <code>{fb['citation']}</code>" if fb.get("citation") else ""
                            corr_info = f"<div style='font-size: 0.85rem; color: #fbbf24; margin-top: 0.25rem;'><strong>Correction:</strong> {fb['correction']}</div>" if fb.get("correction") else ""
                            notes_info = f"<div style='font-size: 0.82rem; color: #94a3b8; margin-top: 0.25rem;'><strong>Notes:</strong> {fb['attorney_notes']}</div>" if fb.get("attorney_notes") else ""

                            st.markdown(f"""
                                <div class="law-card" style="border-left-color: #38bdf8; padding: 0.9rem 1.1rem;">
                                    <div style="margin-bottom: 0.35rem;">
                                        {d_badge} <span style="font-weight: 600; font-size: 0.95rem; color: #f1f5f9; margin-left: 8px;">{fb.get('claim_text')}</span>{cit_info}
                                    </div>
                                    {corr_info}
                                    {notes_info}
                                    <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.35rem;">Logged: {fb.get('created_at', '')[:19]}</div>
                                </div>
                            """, unsafe_allow_html=True)
                else:
                    st.error(f"Failed to fetch feedback history: {hist_resp.status_code}")
            except Exception as e:
                st.error(f"Feedback history error: {e}")


# --- Tab 4: Statutory & Ordinance Explorer ---
with tab4:
    st.markdown("### 🔍 Sovereign Legal & Discovery Search Explorer")
    st.write("Perform isolated hybrid searches across the governing statutory graph or inspect client matter discovery exhibits.")

    search_domain = st.radio(
        "Search Domain",
        ["📜 Governing Statutory Graph", "📁 Client Matter Discovery & Evidence"],
        horizontal=True
    )

    if search_domain == "📜 Governing Statutory Graph":
        e_q, e_st, e_cty = st.columns([2, 1, 1])
        with e_q:
            search_query = st.text_input("Enter natural language query or statutory terms", placeholder="e.g., notice of rent increase dispute")
        with e_st:
            exp_state = st.text_input("Filter State", max_chars=2, placeholder="e.g., CA", key="exp_st")
        with e_cty:
            exp_city = st.text_input("Filter City", placeholder="e.g., Oakland", key="exp_cty")

        col_opt1, col_opt2 = st.columns([1, 1])
        with col_opt1:
            search_limit = st.slider("Result Count", min_value=1, max_value=25, value=6, key="search_slider")
        with col_opt2:
            use_query_expansion = st.checkbox("Enable Automated Issue-Spotting Expansion", value=True)

        if st.button("Search Statutory Graph", use_container_width=True):
            if not search_query.strip():
                st.warning("Please enter a search query.")
            else:
                with st.spinner("Executing hybrid search against local statutory corpus..."):
                    try:
                        params = {
                            "q": search_query.strip(),
                            "limit": search_limit,
                            "expand_query": use_query_expansion
                        }
                        if exp_state:
                            params["state"] = exp_state
                        if exp_city:
                            params["city"] = exp_city

                        resp = httpx.get(
                            f"{BACKEND_URL}/api/laws",
                            params=params,
                            headers=get_auth_headers(),
                            timeout=30.0
                        )
                        if resp.status_code == 200:
                            results = resp.json()
                            if not results:
                                st.info("No matching legal authorities found.")
                            else:
                                st.markdown(f"**Found {len(results)} matching authority provisions:**")
                                for r in results:
                                    sim_pct = round(r["similarity"] * 100, 1)
                                    loc_str = f"{r.get('city') or r.get('city_or_county') or 'Federal'} ({r.get('state') or 'US'})"
                                    top_str = f" [{r['topic']}]" if r.get("topic") else ""
                                    auth_class = r.get("authority_class") or "municipal_ordinance"
                                    h_level = r.get("hierarchy_level") or "section"

                                    auth_tags = (
                                        f'<span class="authority-tag">{auth_class.replace("_", " ").title()}</span>'
                                        f'<span class="authority-tag">{h_level.title()}</span>'
                                    )
                                    if r.get("repealed"):
                                        auth_tags += '<span class="badge-stale">REPEALED</span>'

                                    st.markdown(f"""
                                        <div class="law-card">
                                            <div class="law-card-header">{r['title']} — {r['section']}{top_str}</div>
                                            <div style="margin-bottom: 0.4rem;">{auth_tags}</div>
                                            <div class="law-card-meta">
                                                <span>Location: {loc_str}</span>
                                                <span class="sim-badge" style="float: right;">{sim_pct}% Match</span>
                                            </div>
                                            <div class="law-card-body">{r['content']}</div>
                                        </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(f"Statutory search failed ({resp.status_code}): {resp.text}")
                    except Exception as e:
                        st.error(f"Search failure: {e}")

    else:
        # Client Matter Discovery & Evidence Search
        matters = fetch_cases_list()
        if not matters:
            st.info("No active matters found. Please log a matter in the 'Matter Portfolio' tab and upload documents.")
        else:
            m_options = {f"#{m['id']} — {m['title']}": m['id'] for m in matters}
            sel_m_label = st.selectbox("Select Client Matter to Search", list(m_options.keys()))
            sel_m_id = m_options[sel_m_label]

            # Fetch existing legal tags and doctrines for this matter
            avail_tags = []
            avail_doctrines = []
            try:
                tm_resp = httpx.get(f"{BACKEND_URL}/api/cases/{sel_m_id}/evidence/tags", headers=get_auth_headers(), timeout=5.0)
                if tm_resp.status_code == 200:
                    t_data = tm_resp.json()
                    avail_tags = t_data.get("tags", [])
                    avail_doctrines = t_data.get("doctrines", [])
            except Exception:
                pass

            ev_q_col, ev_type_col = st.columns([3, 1])
            with ev_q_col:
                ev_query = st.text_input("Discovery Search Query (optional)", placeholder="e.g., rent increase notice text or security deposit clause")
            with ev_type_col:
                ev_doc_type = st.selectbox("Doc Classification", ["All", "matter_facts", "evidence", "lease", "notice", "work_product"])

            ev_filt1, ev_filt2, ev_filt3 = st.columns([1, 1, 1])
            with ev_filt1:
                ev_doctrine_choice = st.selectbox("Doctrine Filter", ["All"] + avail_doctrines)
            with ev_filt2:
                ev_tag_choice = st.selectbox("Semantic Tag Filter", ["All"] + avail_tags)
            with ev_filt3:
                ev_limit = st.slider("Max Evidence Chunks", min_value=1, max_value=20, value=8)

            if st.button("Search Matter Discovery", use_container_width=True):
                with st.spinner("Searching isolated client matter evidence table with semantic understanding..."):
                    try:
                        ev_params = {"limit": ev_limit}
                        if ev_query.strip():
                            ev_params["q"] = ev_query.strip()
                        if ev_doc_type != "All":
                            ev_params["doc_type"] = ev_doc_type
                        if ev_doctrine_choice != "All":
                            ev_params["doctrine"] = ev_doctrine_choice
                        if ev_tag_choice != "All":
                            ev_params["tag"] = ev_tag_choice

                        resp = httpx.get(
                            f"{BACKEND_URL}/api/cases/{sel_m_id}/evidence",
                            params=ev_params,
                            headers=get_auth_headers(),
                            timeout=30.0
                        )
                        if resp.status_code == 200:
                            ev_results = resp.json()
                            if not ev_results:
                                st.info("No discovery evidence chunks matched.")
                            else:
                                st.markdown(f"**Found {len(ev_results)} discovery chunks for Matter #{sel_m_id}:**")
                                for er in ev_results:
                                    sim_pct = round(er["similarity"] * 100, 1)
                                    page_info = f" (p. {er['page_number']})" if er.get("page_number") else ""
                                    sec_info = f" • {er['section_locator']}" if er.get("section_locator") else ""
                                    tags_list = er.get("tags") or []
                                    tags_badge_html = " ".join([f'<span class="authority-tag" style="background: rgba(14, 165, 233, 0.15); color: #38bdf8;">🏷️ #{t}</span>' for t in tags_list])
                                    doctrine_badge = f'<span class="authority-tag" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc;">⚖️ {er["doctrine"]}</span>' if er.get("doctrine") else ""
                                    summary_html = f"<div style='font-size: 0.86rem; color: #93c5fd; margin-bottom: 0.55rem; padding: 0.35rem 0.65rem; background: rgba(15, 23, 42, 0.5); border-radius: 6px; border-left: 3px solid #38bdf8;'>💡 <strong>Legal Micro-Digest:</strong> {er['summary']}</div>" if er.get("summary") else ""

                                    st.markdown(f"""
                                        <div class="law-card">
                                            <div class="law-card-header">📄 {er['filename']}{page_info}{sec_info}</div>
                                            <div style="margin-bottom: 0.45rem;">
                                                {doctrine_badge}
                                                {tags_badge_html}
                                            </div>
                                            <div class="law-card-meta">
                                                <span>Classification: <code>{er['doc_type']}</code></span>
                                                <span class="sim-badge" style="float: right;">{sim_pct}% Relevance</span>
                                            </div>
                                            {summary_html}
                                            <div class="law-card-body">{er['content']}</div>
                                        </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(f"Evidence search failed ({resp.status_code}): {resp.text}")
                    except Exception as e:
                        st.error(f"Evidence search failure: {e}")


# --- Tab 5: Statutory Traceability & Audit Registry ---
with tab5:
    t5_sub1, t5_sub2 = st.tabs([
        "🔗 Preemption & Amendment Review Queue",
        "📜 Statute-to-Code Traceability"
    ])

    with t5_sub1:
        st.markdown("### 🔗 Statutory Preemption & Legislative Amendment Review Queue")
        st.write(
            "Human-in-the-loop review queue for statutory preemption (e.g., Costa-Hawkins, AB 12, AB 1482) "
            "and legislative amendment relations. **Only confirmed edges dictate binding controlling precedence**; "
            "proposed edges trigger advisories across briefs and consultations."
        )

        # Propose new relation expander
        with st.expander("➕ Propose New Preemption or Amendment Relation Edge", expanded=False):
            with st.form("propose_statute_relation_form", clear_on_submit=True):
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    src_stat = st.text_input("Source Statute (Higher Authority / Amending Act)", placeholder="e.g., Cal. Civ. Code § 1954.50 or Stats. 2023, ch. 290 (AB 12)")
                    rel_type = st.selectbox("Relation Type", ["PREEMPTS", "AMENDS", "SUPERSEDES", "CARVES_OUT", "EXEMPTS_FROM", "IMPLEMENTS"])
                with p_c2:
                    tgt_stat = st.text_input("Target Statute (Subordinate / Historical Section)", placeholder="e.g., Oakland OMC 8.22.030 or Cal. Civ. Code § 1950.5(c)")
                    scope_top = st.text_input("Scope Doctrine / Topic", placeholder="e.g., Rent Control, Security Deposits, Just Cause")

                trig_sp = st.text_area("Triggering Statutory Span", placeholder="Exact statutory language establishing preemption or amendment...")
                legal_rat = st.text_area("Legal Rationale & Analysis", placeholder="Explanation of preemption scope or legislative intent...")

                if st.form_submit_button("Propose Relation Edge", use_container_width=True):
                    if src_stat and tgt_stat:
                        try:
                            prop_resp = httpx.post(
                                f"{BACKEND_URL}/api/resolver/relations",
                                json={
                                    "source_statute": src_stat.strip(),
                                    "target_statute": tgt_stat.strip(),
                                    "relation_type": rel_type,
                                    "scope_topic": scope_top.strip() if scope_top else None,
                                    "trigger_span": trig_sp.strip() if trig_sp else None,
                                    "rationale": legal_rat.strip() if legal_rat else None,
                                    "status": "proposed"
                                },
                                headers=get_auth_headers(),
                                timeout=10.0
                            )
                            if prop_resp.status_code == 201:
                                st.success(f"Proposed {rel_type} relation successfully logged.")
                                st.rerun()
                            else:
                                st.error(f"Failed to propose relation: {prop_resp.text}")
                        except Exception as pe:
                            st.error(f"Error proposing relation: {pe}")
                    else:
                        st.warning("Source and Target statutes are required.")

        # Filter relations
        f_c1, f_c2 = st.columns([1, 1])
        with f_c1:
            rel_status_filt = st.selectbox("Filter Preemption Status", ["All", "proposed", "confirmed", "rejected"])
        with f_c2:
            rel_top_filt = st.text_input("Filter by Doctrine/Topic (optional)", placeholder="e.g., Security Deposits")

        rel_params = {}
        if rel_status_filt != "All":
            rel_params["status"] = rel_status_filt
        if rel_top_filt.strip():
            rel_params["topic"] = rel_top_filt.strip()

        try:
            r_resp = httpx.get(
                f"{BACKEND_URL}/api/resolver/relations",
                params=rel_params,
                headers=get_auth_headers(),
                timeout=15.0
            )
            if r_resp.status_code == 200:
                relations = r_resp.json()
                if not relations:
                    st.info("No statutory preemption or amendment relations found matching filters.")
                else:
                    st.markdown(f"**Found {len(relations)} relation edge(s):**")
                    for rel in relations:
                        r_id = rel["id"]
                        status = rel["status"]
                        if status == "confirmed":
                            s_badge = '<span class="badge-supported">✅ CONFIRMED</span>'
                        elif status == "rejected":
                            s_badge = '<span class="badge-wrong-prop">❌ REJECTED</span>'
                        else:
                            s_badge = '<span class="badge-prototype">⏳ PROPOSED (Awaiting Attorney Review)</span>'

                        st.markdown(f"""
                            <div class="law-card" style="border-left-color: {'#22c55e' if status == 'confirmed' else '#f59e0b' if status == 'proposed' else '#64748b'};">
                                <div class="law-card-header">
                                    <code>{rel['source_statute']}</code> ➔ <strong>{rel['relation_type']}</strong> ➔ <code>{rel['target_statute']}</code>
                                </div>
                                <div style="margin-bottom: 0.45rem;">
                                    <span class="authority-tag">{rel.get('scope_topic') or 'General'}</span>
                                    {s_badge}
                                </div>
                                <div style="font-size: 0.86rem; color: #cbd5e1; margin-bottom: 0.35rem;">
                                    <strong>Triggering Statutory Span:</strong> <em>"{rel.get('trigger_span') or 'N/A'}"</em>
                                </div>
                                <div style="font-size: 0.82rem; color: #94a3b8;">
                                    <strong>Legal Rationale:</strong> {rel.get('rationale') or 'N/A'}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                        btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 3])
                        with btn_c1:
                            if status != "confirmed" and st.button("✅ Confirm", key=f"conf_rel_{r_id}"):
                                try:
                                    patch_res = httpx.patch(
                                        f"{BACKEND_URL}/api/resolver/relations/{r_id}",
                                        json={"status": "confirmed", "reviewed_by": "attorney:krusch"},
                                        headers=get_auth_headers(),
                                        timeout=10.0
                                    )
                                    if patch_res.status_code == 200:
                                        st.success("Confirmed!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        with btn_c2:
                            if status != "rejected" and st.button("❌ Reject", key=f"rej_rel_{r_id}"):
                                try:
                                    patch_res = httpx.patch(
                                        f"{BACKEND_URL}/api/resolver/relations/{r_id}",
                                        json={"status": "rejected", "reviewed_by": "attorney:krusch"},
                                        headers=get_auth_headers(),
                                        timeout=10.0
                                    )
                                    if patch_res.status_code == 200:
                                        st.warning("Rejected!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        with btn_c3:
                            with st.popover("✏️ Edit Scope/Type"):
                                opts = ["PREEMPTS", "AMENDS", "SUPERSEDES", "CARVES_OUT", "EXEMPTS_FROM", "IMPLEMENTS"]
                                def_idx = opts.index(rel["relation_type"]) if rel["relation_type"] in opts else 0
                                new_type = st.selectbox("Relation Type", opts, index=def_idx, key=f"et_{r_id}")
                                new_top = st.text_input("Scope Doctrine", value=rel.get("scope_topic") or "", key=f"etop_{r_id}")
                                new_rat = st.text_area("Rationale", value=rel.get("rationale") or "", key=f"erat_{r_id}")
                                if st.button("Save Changes", key=f"save_rel_{r_id}"):
                                    try:
                                        patch_res = httpx.patch(
                                            f"{BACKEND_URL}/api/resolver/relations/{r_id}",
                                            json={"relation_type": new_type, "scope_topic": new_top, "rationale": new_rat},
                                            headers=get_auth_headers(),
                                            timeout=10.0
                                        )
                                        if patch_res.status_code == 200:
                                            st.success("Updated!")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")
            else:
                st.error(f"Failed to fetch relations: {r_resp.text}")
        except Exception as e:
            st.error(f"Relation fetch error: {e}")

    with t5_sub2:
        st.markdown("### 📜 Statutory Traceability & Audit Registry")
        st.write(
            "Deterministic, versioned statute-to-code binding invariants mapping California Civil Code and housing doctrine "
            "directly to verified code symbols and attorney attestations under CCP § 128.7."
        )

        t_col1, t_col2 = st.columns([1, 1])
        with t_col1:
            trace_doctrine = st.selectbox(
                "Filter by Doctrine",
                ["All", "Security Deposits", "Just Cause", "Habitability"]
            )
        with t_col2:
            trace_status = st.selectbox(
                "Filter by Verification Status",
                ["All", "manually_verified", "suggested_candidate", "deprecated"]
            )

        trace_params = {}
        if trace_doctrine != "All":
            trace_params["doctrine"] = trace_doctrine
        if trace_status != "All":
            trace_params["status"] = trace_status

        try:
            t_resp = httpx.get(
                f"{BACKEND_URL}/api/compliance/traceability",
                params=trace_params,
                headers=get_auth_headers(),
                timeout=15.0
            )
            if t_resp.status_code == 200:
                trace_items = t_resp.json()
                if not trace_items:
                    st.info("No traceability mappings found matching the selected filters.")
                else:
                    st.markdown(f"**Showing {len(trace_items)} verified statutory binding records:**")
                    for item in trace_items:
                        status_badge = (
                            '<span class="badge-supported">✅ MANUALLY VERIFIED</span>'
                            if item.get("status") == "manually_verified"
                            else f'<span class="badge-wrong-prop">{item.get("status", "").upper()}</span>'
                        )
                        rev_info = f" • Reviewed by: <code>{item.get('reviewed_by')}</code> ({item.get('reviewed_at', '')[:10]})" if item.get("reviewed_by") else ""
                        st.markdown(f"""
                            <div class="law-card" style="border-left-color: #6366f1;">
                                <div class="law-card-header">{item['statute_id']} ➔ <code>{item['symbol_id']}</code></div>
                                <div style="margin-bottom: 0.45rem;">
                                    <span class="authority-tag">{item['doctrine']}</span>
                                    {status_badge}
                                </div>
                                <div class="law-card-meta">
                                    <span>File: <code>{item['file_path']}</code> (Repo: {item['repository']}){rev_info}</span>
                                </div>
                                <div style="font-size: 0.88rem; color: #e2e8f0; margin-bottom: 0.4rem;">
                                    <strong>Digest:</strong> {item.get('statutory_digest') or 'No digest provided.'}
                                </div>
                                <div style="font-size: 0.82rem; color: #94a3b8;">
                                    <strong>Attestation Notes:</strong> {item.get('notes') or 'N/A'}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
            else:
                st.error(f"Failed to fetch traceability records ({t_resp.status_code}): {t_resp.text}")
        except Exception as e:
            st.error(f"Traceability service error: {e}")

