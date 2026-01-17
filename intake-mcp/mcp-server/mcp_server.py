import os
import yaml
import json
import logging
from typing import Dict, Any, List, Optional
import re
from collections import defaultdict

# ✅ Hackathon required MCP framework
from fastmcp import FastMCP

# for /health response
from starlette.responses import PlainTextResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntakeTriageMCP")

mcp = FastMCP("Intelligent Intake and Triage MCP Server")


# --------------------------------------------------
# Custom route to validate server is running
# --------------------------------------------------
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return PlainTextResponse("OK")


@mcp.custom_route("/", methods=["GET"])
async def root(request):
    return PlainTextResponse("✅ MCP is running")


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()


def error_response(message: str, code: int = 400, details: Any = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    }


# --------------------------------------------------
# Configuration Management (Multi-Industry)
# Loads 3 files:
#   taxonomy.json
#   severity.yaml
#   routing.json
# --------------------------------------------------
def load_config() -> Dict[str, Any]:
    """
    Loads config dynamically using either:
    - CONFIG_PATH=/configs/healthcare    (folder path containing 3 files)
    OR
    - ACTIVE_INDUSTRY=healthcare        (loads ./config/healthcare/)
    """

    config_path_env = os.getenv("CONFIG_PATH", "").strip()

    if config_path_env:
        base_path = config_path_env
        logger.info(f"Loading config folder from CONFIG_PATH: {base_path}")
    else:
        industry = os.getenv("ACTIVE_INDUSTRY", "healthcare").strip().lower()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(base_dir, "config", industry)
        logger.info(f"Loading config for industry='{industry}' from: {base_path}")

    taxonomy_path = os.path.join(base_path, "taxonomy.json")
    severity_path = os.path.join(base_path, "severity.yaml")
    routing_path = os.path.join(base_path, "routing.json")

    config: Dict[str, Any] = {
        "taxonomy": [],
        "severity_rules": {},
        "routing": {
            "default_destination": "General_Queue",
            "severity_override": {
                "min_score": 9,
                "destination": "High_Priority_Queue",
                "priority": "HIGH"
            },
            "routes": []
        }
    }

    # -------- TAXONOMY.JSON --------
    if os.path.exists(taxonomy_path):
        try:
            with open(taxonomy_path, "r") as f:
                taxonomy_data = json.load(f) or {}
            config["taxonomy"] = taxonomy_data.get("taxonomy", [])
        except Exception as e:
            logger.error(f"Failed to load taxonomy.json: {e}")
    else:
        logger.error(f"taxonomy.json not found at: {taxonomy_path}")

    # -------- SEVERITY.YAML --------
    if os.path.exists(severity_path):
        try:
            with open(severity_path, "r") as f:
                severity_data = yaml.safe_load(f) or {}
            config["severity_rules"] = severity_data.get("severity_rules", {})
        except Exception as e:
            logger.error(f"Failed to load severity.yaml: {e}")
    else:
        logger.error(f"severity.yaml not found at: {severity_path}")

    # -------- ROUTING.JSON --------
    if os.path.exists(routing_path):
        try:
            with open(routing_path, "r") as f:
                routing_data = json.load(f) or {}

            config["routing"]["default_destination"] = routing_data.get(
                "default_destination", "General_Queue"
            )
            config["routing"]["severity_override"] = routing_data.get(
                "severity_override", config["routing"]["severity_override"]
            )
            config["routing"]["routes"] = routing_data.get("routes", [])
        except Exception as e:
            logger.error(f"Failed to load routing.json: {e}")
    else:
        logger.error(f"routing.json not found at: {routing_path}")

    return config


# --------------------------------------------------
# MCP Resources (Config Driven)
# --------------------------------------------------
@mcp.resource("config://taxonomy")
def get_taxonomy() -> List[Dict[str, Any]]:
    return load_config().get("taxonomy", [])


@mcp.resource("config://severity_rules")
def get_severity_rules() -> Dict[str, Any]:
    return load_config().get("severity_rules", {})


@mcp.resource("config://routing")
def get_routing_resource() -> Dict[str, Any]:
    return load_config().get("routing", {})


@mcp.resource("server://active_industry")
def get_active_industry() -> Dict[str, Any]:
    return {
        "ACTIVE_INDUSTRY": os.getenv("ACTIVE_INDUSTRY", "healthcare"),
        "CONFIG_PATH": os.getenv("CONFIG_PATH", ""),
        "status": "ok"
    }


# --------------------------------------------------
# MCP Tools (Stateless + Config Driven)
# --------------------------------------------------
@mcp.tool()
def classify_intake(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return error_response("Invalid input: 'text' must be a non-empty string.", 422)

    config = load_config()
    taxonomy = config.get("taxonomy", [])
    normalized_text = normalize_text(text)

    scores = defaultdict(int)
    matched = defaultdict(list)

    for entry in taxonomy:
        category = entry.get("id")
        for kw in entry.get("keywords", []):
            kw_norm = normalize_text(kw)
            if kw_norm and kw_norm in normalized_text:
                scores[category] += 1
                matched[category].append(kw)

    if not scores:
        return {
            "ok": True,
            "category": None,
            "confidence": 0.0,
            "matched_keywords": [],
            "method": "keyword",
            "needs_llm": True
        }

    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = round(scores[best] / total, 2)

    return {
        "ok": True,
        "category": best,
        "confidence": confidence,
        "matched_keywords": matched[best],
        "method": "keyword",
        "needs_llm": confidence < 0.5
    }


@mcp.tool()
def score_severity(text: str, category: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return error_response("Invalid input: 'text' must be a non-empty string.", 422)

    config = load_config()
    rules = config.get("severity_rules", {})
    normalized = normalize_text(text)

    priority_order = ["critical", "high", "medium", "low"]
    ordered_levels = [lvl for lvl in priority_order if lvl in rules] + [
        lvl for lvl in rules.keys() if lvl not in priority_order
    ]

    for level in ordered_levels:
        rule = rules.get(level, {})
        for kw in rule.get("keywords", []):
            kw_norm = normalize_text(kw)
            if kw_norm and kw_norm in normalized:
                return {
                    "ok": True,
                    "score": int(rule.get("score", 0)),
                    "level": level,
                    "reason": f"Matched keyword: '{kw}'"
                }

    if category == "emergency":
        return {
            "ok": True,
            "score": 9,
            "level": "escalated",
            "reason": "Emergency category escalation"
        }

    return {
        "ok": True,
        "score": 2,
        "level": "low",
        "reason": "No severity indicators found"
    }


@mcp.tool()
def route_case(category: Optional[str], score: int) -> Dict[str, Any]:
    if score is None or not isinstance(score, int):
        return error_response("Invalid input: 'score' must be an integer.", 422)

    config = load_config()
    routing = config.get("routing", {})
    routes = routing.get("routes", [])

    default_destination = routing.get("default_destination", "General_Queue")
    severity_override = routing.get("severity_override", {})

    min_score = int(severity_override.get("min_score", 9))
    if score >= min_score:
        return {
            "ok": True,
            "destination": severity_override.get("destination", "High_Priority_Queue"),
            "priority": severity_override.get("priority", "HIGH"),
            "status": "Severity override"
        }

    for rule in routes:
        if rule.get("category") == category:
            threshold = int(rule.get("threshold", 0))
            destination = rule.get("destination", default_destination)

            if score >= threshold:
                return {
                    "ok": True,
                    "destination": destination,
                    "priority": "HIGH" if score >= 7 else "NORMAL",
                    "status": "Routed via routing.json"
                }
            else:
                return {
                    "ok": True,
                    "destination": destination,
                    "priority": "LOW",
                    "status": "Below threshold"
                }

    return {
        "ok": True,
        "destination": default_destination,
        "priority": "LOW",
        "status": "Unknown category fallback"
    }


@mcp.tool()
def triage_intake(text: str) -> Dict[str, Any]:
    """
    UPDATED:
    If keyword classifier is weak, return needs_llm=True
    so client + Gemini can classify intelligently.
    """

    if not isinstance(text, str) or not text.strip():
        return error_response("Invalid input: 'text' must be a non-empty string.", 422)

    classification = classify_intake(text)
    if not classification.get("ok", True):
        return classification

    # ✅ if classifier says needs_llm, stop and return it
    if classification.get("needs_llm") is True:
        return {
            "ok": True,
            "needs_llm": True,
            "message": "Keyword confidence low. LLM should classify category first.",
            "classification": classification
        }

    category = classification.get("category")

    severity = score_severity(text, category)
    if not severity.get("ok", True):
        return severity

    score = severity.get("score", 2)

    routing = route_case(category, score)
    if not routing.get("ok", True):
        return routing

    return {
        "ok": True,
        "needs_llm": False,
        "input": text,
        "active_industry": os.getenv("ACTIVE_INDUSTRY", "healthcare"),
        "config_path": os.getenv("CONFIG_PATH", ""),
        "triage_summary": {
            "category": category or "general_inquiry",
            "severity_level": severity.get("level"),
            "severity_score": score,
            "priority": routing.get("priority"),
            "destination": routing.get("destination"),
            "status": routing.get("status")
        },
        "details": {
            "classification": classification,
            "severity": severity,
            "routing": routing
        }
    }


# --------------------------------------------------
# Run MCP Server (HTTP JSON-RPC)
# --------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting Intelligent Intake and Triage MCP Server...")
    mcp.run(transport="http", host="0.0.0.0", port=8000)
