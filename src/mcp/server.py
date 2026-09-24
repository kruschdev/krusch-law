#!/usr/bin/env python3
"""
KruschLaw Model Context Protocol (MCP) Server.
Exposes air-gapped municipal ordinance search, matter logging, and staged brief generation
to IDE agents (Claude Code, Antigravity, Cursor) via stdio JSON-RPC with strict ethical guardrails.
"""

import sys
import json
import uuid
import logging
from typing import Dict, Any, Optional

from ..backend.db import SessionLocal, LawVector, Case, GroundingReport, StatuteCodeTraceability
from ..backend.rag import (
    get_embedding,
    retrieve_laws,
    generate_legal_analysis,
    verify_assertion_grounding,
    UPL_DISCLAIMER
)

# Configure logging to stderr so stdio JSON-RPC on stdout remains clean
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [MCP] %(levelname)s: %(message)s"
)
logger = logging.getLogger("kruschlaw.mcp")


TOOLS_CATALOG = [
    {
        "name": "search_ordinances",
        "description": "Perform hybrid full-text and vector semantic search across municipal codes, county ordinances, and state statutes in the air-gapped KruschLaw store.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language inquiry or statutory search terms (e.g., 'rent increase notice', 'just cause owner move-in')"
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state postal abbreviation (e.g., 'CA')"
                },
                "city": {
                    "type": "string",
                    "description": "City or county name (e.g., 'Oakland', 'San Francisco')"
                },
                "topic": {
                    "type": "string",
                    "description": "Subject matter classification (e.g., 'Housing & Rent', 'Public Nuisance')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of sections to return (default: 5, max: 20)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_section",
        "description": "Retrieve the unabridged text and metadata for a specific statutory section or municipal ordinance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Section number (e.g., 'Section 8.22.030' or '8.22.030')"
                },
                "jurisdiction": {
                    "type": "string",
                    "description": "Optional jurisdiction filter (e.g., 'Oakland Municipal Code')"
                }
            },
            "required": ["section"]
        }
    },
    {
        "name": "log_matter",
        "description": "Log a confidential legal inquiry or client matter into the air-gapped database with local dense embeddings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Descriptive short title for the matter"
                },
                "facts": {
                    "type": "string",
                    "description": "Comprehensive narrative of facts, parties, and circumstances"
                },
                "matter_number": {
                    "type": "string",
                    "description": "Internal law firm tracking or docket number"
                },
                "client_name": {
                    "type": "string",
                    "description": "Confidential client reference or party name"
                },
                "description": {
                    "type": "string",
                    "description": "Brief tags or classification notes"
                }
            },
            "required": ["title", "facts"]
        }
    },
    {
        "name": "list_matters",
        "description": "List existing active client matters with tracking codes and dates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max matters to return (default: 10)",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "get_grounding_report",
        "description": "Retrieve the most recent assertion-level grounding audit report for a matter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "integer",
                    "description": "Matter ID"
                }
            },
            "required": ["case_id"]
        }
    },
    {
        "name": "draft_brief",
        "description": "Stage an air-gapped, citation-grounded 4-part legal brief for human attorney review. Refuses to draft if governing authorities are absent. Does NOT auto-file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "integer",
                    "description": "ID of an existing logged matter to analyze"
                },
                "facts": {
                    "type": "string",
                    "description": "Matter factual record (required if case_id is omitted)"
                },
                "title": {
                    "type": "string",
                    "description": "Matter title (optional)"
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state filter (e.g., 'CA')"
                },
                "city": {
                    "type": "string",
                    "description": "City or county filter (e.g., 'Oakland')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum authority sections to retrieve (default: 5)",
                    "default": 5
                }
            }
        }
    },
    {
        "name": "get_code_traceability",
        "description": "Inspect curated statute-to-code traceability invariants mapping California Civil Code sections to verified code symbols, repository files, and attorney review attestations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctrine": {
                    "type": "string",
                    "description": "Optional doctrine filter (e.g. 'Security Deposits', 'Just Cause', 'Habitability')"
                },
                "status": {
                    "type": "string",
                    "description": "Optional verification status filter (e.g. 'manually_verified')"
                }
            }
        }
    }
]


def handle_search_ordinances(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "").strip()
    if not query:
        return {"error": "Missing required query string."}

    state = args.get("state")
    city = args.get("city")
    topic = args.get("topic")
    limit = min(20, max(1, int(args.get("limit", 5))))

    db = SessionLocal()
    try:
        results = retrieve_laws(
            text_query=query,
            state_filter=state,
            city_filter=city,
            topic_filter=topic,
            limit=limit,
            db_session=db
        )
        formatted = []
        for r in results:
            formatted.append({
                "id": r["id"],
                "jurisdiction": r["jurisdiction"],
                "section": r["section"],
                "title": r["title"],
                "location": f"{r.get('city') or r.get('city_or_county') or 'General'} ({r.get('state') or 'US'})",
                "authority_class": r.get("authority_class", "municipal_ordinance"),
                "hierarchy_level": r.get("hierarchy_level", "section"),
                "repealed": r.get("repealed", False),
                "relevance_score": round(r["similarity"], 4),
                "content": r["content"]
            })
        return {
            "query": query,
            "total_matches": len(formatted),
            "authorities": formatted
        }
    finally:
        db.close()


def handle_get_section(args: Dict[str, Any]) -> Dict[str, Any]:
    section = args.get("section", "").strip()
    if not section:
        return {"error": "Missing required section parameter."}

    clean_sec = section if section.lower().startswith("section") else f"Section {section}"
    jurisdiction = args.get("jurisdiction")

    db = SessionLocal()
    try:
        q = db.query(LawVector).filter(
            (LawVector.section == clean_sec) |
            (LawVector.section == section) |
            (LawVector.source_header.ilike(f"%{section}%"))
        )
        if jurisdiction:
            q = q.filter(LawVector.jurisdiction.ilike(f"%{jurisdiction}%"))

        records = q.order_by(LawVector.chunk_index.asc()).all()
        if not records:
            return {"found": False, "message": f"Section '{section}' not found in local store."}

        primary = records[0]
        full_text = "\n\n".join(r.content for r in records)

        return {
            "found": True,
            "id": primary.id,
            "jurisdiction": primary.jurisdiction,
            "section": primary.section,
            "title": primary.title,
            "state": primary.state,
            "city": primary.city or primary.city_or_county,
            "county": primary.county,
            "topic": primary.topic,
            "authority_class": primary.authority_class,
            "hierarchy_level": primary.hierarchy_level,
            "repealed": primary.repealed,
            "preempted_by": primary.preempted_by,
            "effective_date": str(primary.effective_date) if primary.effective_date else None,
            "definitions_ref": primary.definitions_ref,
            "exceptions_ref": primary.exceptions_ref,
            "total_chunks": len(records),
            "content": full_text
        }
    finally:
        db.close()


def handle_log_matter(args: Dict[str, Any]) -> Dict[str, Any]:
    title = args.get("title", "").strip()
    facts = args.get("facts", "").strip()
    if not title or not facts:
        return {"error": "Both 'title' and 'facts' are required to log a matter."}

    matter_no = args.get("matter_number")
    client_name = args.get("client_name")
    description = args.get("description")

    db = SessionLocal()
    try:
        vector = get_embedding(facts)
        case = Case(
            title=title,
            matter_number=matter_no,
            client_name=client_name,
            description=description,
            facts=facts,
            embedding=vector
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        return {
            "status": "created",
            "case_id": case.id,
            "matter_number": case.matter_number,
            "client_name": case.client_name,
            "title": case.title,
            "created_at": case.created_at.isoformat() if case.created_at else ""
        }
    finally:
        db.close()


def handle_list_matters(args: Dict[str, Any]) -> Dict[str, Any]:
    limit = min(50, max(1, int(args.get("limit", 10))))
    db = SessionLocal()
    try:
        cases = db.query(Case).filter(Case.is_deleted.is_(False)).order_by(Case.created_at.desc()).limit(limit).all()
        return {
            "total_matters": len(cases),
            "matters": [
                {
                    "id": c.id,
                    "matter_number": c.matter_number,
                    "client_name": c.client_name,
                    "title": c.title,
                    "created_at": c.created_at.isoformat() if c.created_at else ""
                } for c in cases
            ]
        }
    finally:
        db.close()


def handle_get_grounding_report(args: Dict[str, Any]) -> Dict[str, Any]:
    case_id = args.get("case_id")
    if not case_id:
        return {"error": "case_id is required."}

    db = SessionLocal()
    try:
        report = db.query(GroundingReport).filter(GroundingReport.case_id == case_id).order_by(GroundingReport.created_at.desc()).first()
        if not report:
            return {"found": False, "message": f"No grounding audit report found for matter #{case_id}."}

        return {
            "found": True,
            "case_id": case_id,
            "report_id": report.id,
            "created_at": report.created_at.isoformat() if report.created_at else "",
            "pass_rate": report.pass_rate,
            "total_claims": report.total_claims,
            "supported_claims": report.supported_claims,
            "unsupported_claims": report.unsupported_claims,
            "invented_citations": report.invented_citations,
            "stale_law_citations": report.stale_law_citations,
            "claims": json.loads(report.claims_json) if report.claims_json else []
        }
    finally:
        db.close()


def handle_draft_brief(args: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        case_id = args.get("case_id")
        case = None
        if case_id:
            case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).first()
            if not case:
                return {"error": f"Matter #{case_id} not found."}

        facts = case.facts if case else args.get("facts", "").strip()
        title = case.title if case else (args.get("title") or "Confidential Matter Analysis")

        if not facts:
            return {"error": "Factual narrative is required. Provide 'facts' or a valid 'case_id'."}

        query_vector = case.embedding if (case and case.embedding) else get_embedding(facts)
        limit = min(15, max(1, int(args.get("limit", 5))))
        state = args.get("state")
        city = args.get("city")

        laws = retrieve_laws(
            query_vector=query_vector,
            text_query=facts,
            limit=limit,
            state_filter=state,
            city_filter=city,
            db_session=db
        )

        if not laws:
            return {
                "error": "CANNOT_DRAFT_WITHOUT_AUTHORITIES",
                "review_required": True,
                "provisional_work_product": True,
                "message": "Drafting refused: No relevant governing statutory or municipal authorities retrieved in the air-gapped corpus."
            }

        res = generate_legal_analysis(
            case_facts=facts,
            case_title=title,
            laws=laws,
            case_id=case.id if case else None,
            db_session=db
        )
        if isinstance(res, tuple):
            analysis = res[0]
            stats = res[1] if len(res) > 1 else {}
            claim_records = res[2] if len(res) > 2 else []
        else:
            analysis = str(res)
            is_grounded, claim_records, notice, stats = verify_assertion_grounding(analysis, laws)
            if case and case.id:
                try:
                    report = GroundingReport(
                        id=str(uuid.uuid4()),
                        case_id=case.id,
                        pass_rate=stats.get("pass_rate", 0.0),
                        total_claims=stats.get("total_claims", 0),
                        supported_claims=stats.get("supported_claims", 0),
                        unsupported_claims=stats.get("unsupported_claims", 0),
                        invented_citations=stats.get("invented_citations", 0),
                        stale_law_citations=stats.get("stale_law_citations", 0),
                        claims_json=json.dumps(claim_records)
                    )
                    db.add(report)
                    db.commit()
                except Exception as e:
                    logger.warning(f"Could not persist fallback grounding report: {e}")

        return {
            "staged_status": "READY_FOR_ATTORNEY_REVIEW",
            "review_required": True,
            "provisional_work_product": True,
            "matter_title": title,
            "pass_rate": stats.get("pass_rate", 100.0),
            "retrieved_authority_count": len(laws),
            "grounding_summary": stats,
            "claims_audit": claim_records,
            "authorities_cited": [
                {
                    "section": law_item.get("section"),
                    "title": law_item.get("title"),
                    "jurisdiction": law_item.get("jurisdiction"),
                    "authority_class": law_item.get("authority_class"),
                    "similarity": round(law_item.get("similarity", 0.0), 3)
                } for law_item in laws
            ],
            "brief_content": analysis,
            "disclaimer": UPL_DISCLAIMER
        }
    finally:
        db.close()


def handle_get_code_traceability(args: Dict[str, Any]) -> Dict[str, Any]:
    doctrine = args.get("doctrine")
    status = args.get("status")
    db = SessionLocal()
    try:
        q = db.query(StatuteCodeTraceability)
        if doctrine:
            q = q.filter(StatuteCodeTraceability.doctrine == doctrine)
        if status:
            q = q.filter(StatuteCodeTraceability.status == status)
        rows = q.order_by(StatuteCodeTraceability.id.asc()).all()
        return {
            "total": len(rows),
            "mappings": [
                {
                    "id": r.id,
                    "statute_id": r.statute_id,
                    "symbol_id": r.symbol_id,
                    "repository": r.repository,
                    "file_path": r.file_path,
                    "doctrine": r.doctrine,
                    "status": r.status,
                    "reviewed_by": r.reviewed_by,
                    "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                    "statutory_digest": r.statutory_digest,
                    "notes": r.notes
                }
                for r in rows
            ]
        }
    finally:
        db.close()


def process_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "kruschlaw-mcp",
                    "version": "0.3.0"
                }
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_CATALOG
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        handlers = {
            "search_ordinances": handle_search_ordinances,
            "get_section": handle_get_section,
            "log_matter": handle_log_matter,
            "list_matters": handle_list_matters,
            "get_grounding_report": handle_get_grounding_report,
            "draft_brief": handle_draft_brief,
            "get_code_traceability": handle_get_code_traceability
        }

        if tool_name not in handlers:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found."
                }
            }

        try:
            res = handlers[tool_name](args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, indent=2)
                        }
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not implemented."
            }
        }


def main():
    logger.info("KruschLaw MCP Server initializing on stdio...")
    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue
        try:
            req = json.loads(line_clean)
            resp = process_request(req)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: Invalid JSON"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
