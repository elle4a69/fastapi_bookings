from typing import Dict, Any, Optional, List
from .responses_client import generate_response
import json

async def compile_rule(tenant_id: str, plain_language_rule: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Compiles a plain language rule into a validated, immutable JSON rule object.
    Uses Structured Outputs from OpenAI to guarantee the format.
    """
    
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "rule_object",
            "schema": {
                "type": "object",
                "properties": {
                    "rule_type": {
                        "type": "string",
                        "enum": ["selection", "confirmation", "cancellation", "inquiry", "fallback"]
                    },
                    "trigger_keywords": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "action": {
                        "type": "string"
                    },
                    "priority": {
                        "type": "integer"
                    }
                },
                "required": ["rule_type", "trigger_keywords", "action", "priority"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
    
    messages = [
        {"role": "system", "content": "You are a compiler that translates plain language into deterministic JSON rule objects."},
        {"role": "user", "content": f"Compile this rule: {plain_language_rule}"}
    ]
    
    result = await generate_response(
        tenant_id=tenant_id,
        messages=messages,
        policy_name="terra", # Escalation model for better reasoning
        response_format=response_format,
        api_key=api_key
    )
    
    content = result["choices"][0]["message"]["content"]
    compiled_rule = json.loads(content)
    
    return compiled_rule

def evaluate_deterministic_rules(compiled_rules: List[Dict[str, Any]], message_body: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates a list of compiled rules against the message deterministically.
    Returns the action of the highest priority matching rule.
    """
    clean_body = message_body.strip().lower()
    
    # Sort rules by priority descending
    sorted_rules = sorted(compiled_rules, key=lambda x: x.get("priority", 0), reverse=True)
    
    for rule in sorted_rules:
        keywords = rule.get("trigger_keywords", [])
        if not keywords:
            continue
            
        if any(kw in clean_body for kw in keywords):
            return rule
            
    return None
