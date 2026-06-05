import json
import re
import time
import anthropic
from anthropic import Anthropic
from ..config import ANTHROPIC_API_KEY,CLAUDE_MODEL_FAST,CLAUDE_MODEL_PRO
from ..storage import append_event

_client=None

def get_client():
    global _client
    if _client is None:
        _client=Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

RETRYABLE_STATUSES={429,500,502,503,504,529}

def _is_retryable(exc):
    if isinstance(exc,(anthropic.RateLimitError,anthropic.InternalServerError,anthropic.APIConnectionError,anthropic.APITimeoutError)):
        return True
    status=getattr(exc,"status_code",None)
    return status in RETRYABLE_STATUSES

def _fallback_for(model):
    if model and model==CLAUDE_MODEL_PRO:
        return CLAUDE_MODEL_FAST
    return None

def _call_anthropic(model,system,messages,max_output,temperature,tools=None,thinking_budget=0):
    kwargs={
        "model":model,
        "max_tokens":max_output,
        "system":system,
        "messages":messages,
    }
    if tools:
        kwargs["tools"]=tools
    if thinking_budget and thinking_budget>0:
        kwargs["thinking"]={"type":"enabled","budget_tokens":thinking_budget}
        kwargs["temperature"]=1.0
    else:
        kwargs["temperature"]=temperature
    return get_client().messages.create(**kwargs)

def _generate_with_retry(run_id,agent,model,system,messages,max_output,temperature,tools=None,thinking_budget=0,max_attempts=2,fallback_model=None):
    models=[m for m in [model,fallback_model] if m]
    if len(models)==2 and models[0]==models[1]:
        models=[models[0]]
    last=None
    for idx,current in enumerate(models):
        is_primary=(idx==0)
        delay=2
        for attempt in range(1,max_attempts+1):
            try:
                return current,_call_anthropic(current,system,messages,max_output,temperature,tools,thinking_budget)
            except Exception as e:
                last=e
                code=getattr(e,"status_code",None) or 0
                if not _is_retryable(e):
                    raise
                if attempt<max_attempts:
                    append_event(run_id,"llm_retry",{"agent":agent,"model":current,"attempt":attempt,"code":code,"sleep":delay})
                    time.sleep(delay)
                    delay=min(delay*2,8)
                else:
                    if is_primary and len(models)>1:
                        append_event(run_id,"llm_model_fallback",{"agent":agent,"from":current,"to":models[1],"reason":f"code {code} after {max_attempts} attempts"})
                    else:
                        append_event(run_id,"llm_retry_exhausted",{"agent":agent,"model":current,"code":code})
    if last:
        raise last

def _extract_json(text):
    if not text:
        return None
    text=text.strip()
    fence=re.search(r"```(?:json)?\s*(.*?)```",text,re.DOTALL)
    if fence:
        text=fence.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start=text.find("{")
    end=text.rfind("}")
    if start>=0 and end>start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            return None
    return None

def _log_usage(run_id,agent,model,resp):
    u=getattr(resp,"usage",None)
    in_tok=getattr(u,"input_tokens",0) if u else 0
    out_tok=getattr(u,"output_tokens",0) if u else 0
    append_event(run_id,"llm_usage",{"agent":agent,"model":model,"input_tokens":in_tok,"output_tokens":out_tok})
    return in_tok,out_tok

def _join_text(resp):
    parts=[]
    for block in (resp.content or []):
        t=getattr(block,"text",None)
        if t: parts.append(t)
    return "".join(parts).strip()

def simple_call(run_id,agent,system,user,model=None,max_output=400,want_json=False,thinking=False):
    model=model or CLAUDE_MODEL_FAST
    fb=_fallback_for(model)
    sys_prompt=system
    if want_json:
        sys_prompt=system+"\n\nIMPORTANT: Reply with ONLY a valid JSON object. No prose, no markdown fences."
    messages=[{"role":"user","content":user}]
    append_event(run_id,"llm_call",{"agent":agent,"model":model,"prompt_chars":len(user),"want_json":want_json,"fallback":fb})
    used_model,resp=_generate_with_retry(
        run_id,agent,model,sys_prompt,messages,
        max_output=max_output,
        temperature=0.0,
        thinking_budget=2048 if thinking else 0,
        fallback_model=fb,
    )
    _log_usage(run_id,agent,used_model,resp)
    text=_join_text(resp)
    append_event(run_id,"llm_response",{"agent":agent,"chars":len(text),"preview":text[:120]})
    if want_json:
        return _extract_json(text) or {}
    return text

def _claude_tools(tool_decls):
    out=[]
    for d in tool_decls:
        out.append({
            "name":d["name"],
            "description":d.get("description",""),
            "input_schema":d.get("parameters") or {"type":"object","properties":{}},
        })
    return out

def tool_loop(run_id,agent,system,user,tool_decls,tool_handlers,model=None,max_iters=6,max_output=500,thinking_budget=0,temperature=0.0):
    model=model or CLAUDE_MODEL_FAST
    tools=_claude_tools(tool_decls)
    append_event(run_id,"agent_start",{"agent":agent,"model":model,"tools":[d["name"] for d in tool_decls],"thinking_budget":thinking_budget,"temperature":temperature})

    messages=[{"role":"user","content":user}]
    final_text=""
    used_model=model
    for step in range(max_iters):
        used_model,resp=_generate_with_retry(
            run_id,agent,model,system,messages,
            max_output=max_output,
            temperature=temperature,
            tools=tools,
            thinking_budget=thinking_budget,
            fallback_model=_fallback_for(model),
        )
        _log_usage(run_id,agent,used_model,resp)

        tool_uses=[b for b in (resp.content or []) if getattr(b,"type",None)=="tool_use"]
        if not tool_uses or resp.stop_reason!="tool_use":
            final_text=_join_text(resp)
            append_event(run_id,"llm_response",{"agent":agent,"chars":len(final_text),"preview":final_text[:160]})
            break

        assistant_blocks=[]
        for b in (resp.content or []):
            bt=getattr(b,"type",None)
            if bt=="text":
                assistant_blocks.append({"type":"text","text":b.text})
            elif bt=="tool_use":
                assistant_blocks.append({"type":"tool_use","id":b.id,"name":b.name,"input":dict(b.input or {})})
            elif bt=="thinking":
                assistant_blocks.append({"type":"thinking","thinking":getattr(b,"thinking",""),"signature":getattr(b,"signature","")})
            elif bt=="redacted_thinking":
                assistant_blocks.append({"type":"redacted_thinking","data":getattr(b,"data","")})
        messages.append({"role":"assistant","content":assistant_blocks})

        tool_result_blocks=[]
        for tu in tool_uses:
            name=tu.name
            args=dict(tu.input or {})
            append_event(run_id,"agent_tool_call",{"agent":agent,"tool":name,"args":{k:str(v)[:120] for k,v in args.items()}})
            handler=tool_handlers.get(name)
            if not handler:
                out={"error":f"unknown tool: {name}"}
            else:
                try:
                    out=handler(**args)
                except Exception as e:
                    out={"error":str(e)}
            tool_result_blocks.append({
                "type":"tool_result",
                "tool_use_id":tu.id,
                "content":json.dumps(out),
            })
        messages.append({"role":"user","content":tool_result_blocks})
    else:
        append_event(run_id,"agent_max_iters",{"agent":agent,"max_iters":max_iters})

    append_event(run_id,"agent_end",{"agent":agent,"final_chars":len(final_text)})
    return final_text


# helper notes:
# get_client()             -> single shared Anthropic client (created on first use)
# _is_retryable()          -> True for RateLimit / InternalServerError / Connection /
#                              Timeout, plus HTTP status 429/5xx/529 (overloaded).
# _fallback_for(model)     -> returns Haiku when Sonnet was requested, else None.
#                              Lets the orchestrator transparently degrade if Sonnet
#                              is overloaded.
# _call_anthropic()        -> the actual messages.create call. When thinking is on,
#                              temperature MUST be 1.0 per Claude's extended-thinking
#                              requirement; we set it automatically and ignore the
#                              caller's temperature in that case.
# _generate_with_retry()   -> exponential backoff (2s -> 4s) on the primary model,
#                              then if a fallback is provided, try it too. Every
#                              retry / fallback / exhaustion event goes into the
#                              audit log so the UI shows what happened.
# _extract_json()          -> tolerant JSON extractor (handles ```json fences and
#                              extra prose around an object).
# _log_usage()             -> writes one llm_usage event with input/output token
#                              counts so the UI can show running spend.
# simple_call()            -> one-shot text or JSON call. want_json=True appends a
#                              strict "respond with ONLY JSON" instruction to the
#                              system prompt and parses the reply into a dict.
#                              thinking=True asks Claude to think for up to 2048
#                              tokens before answering (used by Inspector + Rubric).
# _claude_tools()          -> adapts our internal tool schema (which uses the Gemini
#                              "parameters" key) to Claude's input_schema key.
# tool_loop()              -> the real agentic loop. Each turn Claude either replies
#                              with text (we stop and return it) OR with one+ tool_use
#                              blocks. We execute the matching Python handlers, append
#                              tool_result blocks for the next user turn, and continue
#                              until Claude is done or max_iters is hit. Every turn
#                              logs llm_call / llm_usage / agent_tool_call so the live
#                              trace shows exactly which tool was chosen and why.
