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
                🔬 Research Prototype (v0.2.0-dev)
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
        "<strong>KruschLaw v0.2.0-dev (Research Prototype)</strong><br>"
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


# --- Tab 3: Statutory & Ordinance Explorer ---
with tab3:
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

            ev_q_col, ev_type_col = st.columns([3, 1])
            with ev_q_col:
                ev_query = st.text_input("Discovery Search Query (optional)", placeholder="e.g., rent increase notice text or security deposit clause")
            with ev_type_col:
                ev_doc_type = st.selectbox("Doc Classification", ["All", "matter_facts", "evidence", "lease", "notice", "work_product"])

            ev_limit = st.slider("Max Evidence Chunks", min_value=1, max_value=20, value=8)

            if st.button("Search Matter Discovery", use_container_width=True):
                with st.spinner("Searching isolated client matter evidence table..."):
                    try:
                        ev_params = {"limit": ev_limit}
                        if ev_query.strip():
                            ev_params["q"] = ev_query.strip()
                        if ev_doc_type != "All":
                            ev_params["doc_type"] = ev_doc_type

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
                                    st.markdown(f"""
                                        <div class="law-card">
                                            <div class="law-card-header">📄 {er['filename']}{page_info}{sec_info}</div>
                                            <div class="law-card-meta">
                                                <span>Classification: <code>{er['doc_type']}</code></span>
                                                <span class="sim-badge" style="float: right;">{sim_pct}% Relevance</span>
                                            </div>
                                            <div class="law-card-body">{er['content']}</div>
                                        </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(f"Evidence search failed ({resp.status_code}): {resp.text}")
                    except Exception as e:
                        st.error(f"Evidence search failure: {e}")
