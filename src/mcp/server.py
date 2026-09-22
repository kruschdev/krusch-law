#!/usr/bin/env python3
"""
KruschLaw Model Context Protocol (MCP) Server.
Exposes air-gapped municipal ordinance search, matter logging, and staged brief generation
to IDE agents (Claude Code, Antigravity, Cursor) via stdio JSON-RPC.
"""

import sys
import json
import logging
from typing import Dict, Any, List, Optional

from ..backend.db import SessionLocal, LawVector, Case
from ..backend.rag import (
    get_embedding,
    retrieve_laws,
    generate_legal_analysis,
    verify_citation_grounding,
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
        "name": "draft_brief",
        "description": "Stage an air-gapped, citation-grounded 4-part legal brief for human attorney review. Does NOT auto-file; all outputs require human approval.",
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
                "topic": r.get("topic"),
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


def handle_draft_brief(args: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        case_id = args.get("case_id")
        case = None
        if case_id:
            case = db.query(Case).filter(Case.id == case_id, Case.is_deleted == False).first()
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

        analysis = generate_legal_analysis(case_facts=facts, case_title=title, laws=laws)
        is_grounded, ungrounded, notice = verify_citation_grounding(analysis, laws)

        return {
            "staged_status": "READY_FOR_ATTORNEY_REVIEW",
            "matter_title": title,
            "grounding_verified": is_grounded,
            "flagged_items": ungrounded,
            "retrieved_authority_count": len(laws),
            "authorities_cited": [
                {
                    "section": l.get("section"),
                    "title": l.get("title"),
                    "jurisdiction": l.get("jurisdiction"),
                    "similarity": round(l.get("similarity", 0.0), 3)
                } for l in laws
            ],
            "brief_content": analysis,
            "disclaimer": UPL_DISCLAIMER
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
                    "version": "0.2.0-dev"
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

        try:
            if tool_name == "search_ordinances":
                res = handle_search_ordinances(args)
            elif tool_name == "get_section":
                res = handle_get_section(args)
            elif tool_name == "log_matter":
                res = handle_log_matter(args)
            elif tool_name == "draft_brief":
                res = handle_draft_brief(args)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }

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
            logger.error(f"Error handling tool '{tool_name}': {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error executing tool '{tool_name}': {str(e)}"
                        }
                    ]
                }
            }
    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not supported: {method}"
            }
        }


def run_stdio_server():
    """Run JSON-RPC 2.0 loop reading from sys.stdin and writing to sys.stdout."""
    logger.info("Starting KruschLaw MCP stdio server (v0.2.0-dev)...")
    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue
        try:
            req = json.loads(line_clean)
            resp = process_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
