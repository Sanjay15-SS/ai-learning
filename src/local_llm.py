"""Local backend: Qwen2.5-3B-Instruct (4-bit, MLX) on this Mac. No key, no network.

Returns objects shaped like an Anthropic Messages response (content blocks of type
text / tool_use, stop_reason, usage, model) so agent, workflow, app and judge run
unchanged. Greedy decoding, so a re-run gives the same output.
"""
import json
import re
from functools import lru_cache
from types import SimpleNamespace as NS

LOCAL_MODEL = "mlx-community/Qwen2.5-3B-Instruct-4bit"
TOOL_CALL = re.compile(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|$)", re.S)


@lru_cache(maxsize=1)
def _load():
    from mlx_lm import load
    return load(LOCAL_MODEL)


def _text(blocks) -> str:
    if isinstance(blocks, str):
        return blocks
    return "".join(b["text"] if isinstance(b, dict) else getattr(b, "text", "")
                   for b in blocks if (b.get("type") if isinstance(b, dict) else b.type) == "text")


def _to_chat(system, messages) -> list:
    out = [{"role": "system", "content": _text(system)}]
    for m in messages:
        c = m["content"]
        if m["role"] == "user":
            if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get("type") == "tool_result":
                out += [{"role": "tool", "content": r["content"]} for r in c]
            else:
                out.append({"role": "user", "content": _text(c)})
        else:
            calls = [b for b in c if getattr(b, "type", None) == "tool_use"]
            out.append({"role": "assistant", "content": _text(c),
                        "tool_calls": [{"type": "function", "function":
                                        {"name": b.name, "arguments": b.input}} for b in calls]})
    return out


def _parse_call(raw: str):
    s = raw.strip()
    while s.startswith("{{"):                 # the 3B model sometimes doubles the brace
        s = s[1:]
    try:
        obj, _ = json.JSONDecoder().raw_decode(s)
        return obj.get("name"), obj.get("arguments") or {}
    except (json.JSONDecodeError, AttributeError):
        return None, None


_n = 0


def create(*, system, messages, max_tokens=4000, tools=None, **_ignored):
    global _n
    from mlx_lm import generate
    model, tok = _load()
    fn_tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["input_schema"]}}
                for t in tools] if tools else None
    prompt = tok.apply_chat_template(_to_chat(system, messages), tools=fn_tools,
                                     add_generation_prompt=True, tokenize=False)
    in_tok = len(tok.encode(prompt))
    out = generate(model, tok, prompt=prompt, max_tokens=max_tokens)
    out_tok = len(tok.encode(out))
    blocks, calls = [], TOOL_CALL.findall(out) if tools else []
    text = TOOL_CALL.sub("", out).strip() if tools else out.strip()
    if text:
        blocks.append(NS(type="text", text=text))
    for raw in calls:
        name, args = _parse_call(raw)
        if name:
            _n += 1
            blocks.append(NS(type="tool_use", name=name, input=args, id=f"call_{_n}"))
    has_call = any(b.type == "tool_use" for b in blocks)
    stop = "max_tokens" if out_tok >= max_tokens else ("tool_use" if has_call else "end_turn")
    return NS(content=blocks, stop_reason=stop, model=LOCAL_MODEL,
              usage=NS(input_tokens=in_tok, output_tokens=out_tok,
                       cache_creation_input_tokens=0, cache_read_input_tokens=0))
