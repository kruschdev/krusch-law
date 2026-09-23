#!/usr/bin/env python3
"""
scripts/generate_frozen_embeddings.py
=====================================
Generates frozen bge-large 1024-d embeddings using local Ollama (http://localhost:11434)
and writes them to data/eval/embeddings/ for reproducible, unmocked CI testing.
"""

import os
import sys
import json
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.backend.ingest import SEED_CALIFORNIA_ORDINANCES

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = "bge-large"
EMBED_DIR = os.path.join(PROJECT_ROOT, "data", "eval", "embeddings")
os.makedirs(EMBED_DIR, exist_ok=True)


def get_embedding(text: str) -> list[float]:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": MODEL_NAME, "prompt": text},
        timeout=60.0
    )
    resp.raise_for_status()
    data = resp.json()
    return data["embedding"]


def generate_seed_embeddings():
    print("[1/3] Generating seed law embeddings...")
    seed_data = {}
    for ord_item in SEED_CALIFORNIA_ORDINANCES:
        sec = ord_item["section"]
        title = ord_item.get("title", "")
        body = ord_item.get("content", "")
        embed_text = f"{sec}: {title}. {body}"
        vec = get_embedding(embed_text)
        seed_data[sec] = {
            "title": title,
            "topic": ord_item.get("topic", ""),
            "jurisdiction": ord_item.get("jurisdiction", ""),
            "embedding": vec
        }
        print(f"  Embedded: {sec} ({len(vec)} dims)")

    out_path = os.path.join(EMBED_DIR, "seed_bge_large.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, indent=2)
    print(f"Saved {len(seed_data)} seed embeddings to {out_path}")


def generate_query_embeddings():
    print("\n[2/3] Generating query embeddings for golden eval cases...")
    eval_path = os.path.join(PROJECT_ROOT, "data", "eval", "golden_legal_eval.json")
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    queries_data = {}
    for tc in eval_cases:
        cid = tc["id"]
        fp = tc["fact_pattern"]
        vec = get_embedding(fp)
        queries_data[cid] = {
            "fact_pattern": fp,
            "gold_sections": tc.get("gold_sections", []),
            "forbidden_distractors": tc.get("forbidden_distractors", []),
            "jurisdiction": tc.get("jurisdiction", ""),
            "embedding": vec
        }
        print(f"  Embedded Query: {cid} ({len(vec)} dims)")

    out_path = os.path.join(EMBED_DIR, "queries_bge_large.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(queries_data, f, indent=2)
    print(f"Saved {len(queries_data)} query embeddings to {out_path}")


def generate_heldout_embeddings():
    print("\n[3/3] Generating held-out statutory embeddings...")
    heldout_path = os.path.join(PROJECT_ROOT, "data", "eval", "heldout_statutes.json")
    with open(heldout_path, "r", encoding="utf-8") as f:
        heldout_cases = json.load(f)

    statutes_embed = {}
    queries_embed = {}

    for hc in heldout_cases:
        hid = hc["id"]
        sec = hc["section"]
        title = hc["title"]
        content = hc["content"]
        fp = hc["fact_pattern"]

        statute_text = f"{sec}: {title}. {content}"
        statutes_embed[hid] = {
            "section": sec,
            "title": title,
            "jurisdiction": hc.get("jurisdiction", ""),
            "embedding": get_embedding(statute_text)
        }

        queries_embed[hid] = {
            "fact_pattern": fp,
            "gold_sections": hc.get("gold_sections", []),
            "embedding": get_embedding(fp)
        }
        print(f"  Embedded Held-Out: {hid} ({sec})")

    out_data = {
        "statutes": statutes_embed,
        "queries": queries_embed
    }
    out_path = os.path.join(EMBED_DIR, "heldout_bge_large.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
    print(f"Saved {len(statutes_embed)} held-out statute embeddings to {out_path}")


if __name__ == "__main__":
    generate_seed_embeddings()
    generate_query_embeddings()
    generate_heldout_embeddings()
    print("\nAll frozen BGE-Large embeddings generated successfully!")
