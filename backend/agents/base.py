import json
import re
import time
from google import genai
from google.genai import types as gtypes
from google.genai import errors as gerrors
from ..config import GEMINI_API_KEY,GEMINI_MODEL_FAST,GEMINI_MODEL_PRO
from ..storage import append_event

_client=None

def get_client():
    global _client
    if _client is None:
        _client=genai.Client(api_key=GEMINI_API_KEY)
    return _client

RETRYABLE_CODES={429,500,502,503,504}

def _try_once(model,contents,config):
    return get_client().models.generate_content(model=model,contents=contents,config=config)

def _generate_with_retry(run_id,agent,model,contents,config,max_attempts=2,fallback_model=None):
    models=[m for m in [model,fallback_model] if m]
    if len(models)==2 and models[0]==models[1]:
        models=[models[0]]
    last=None
    for idx,current in enumerate(models):
        is_primary=(idx==0)
        delay=2
        for attempt in range(1,max_attempts+1):
            try:
                return _try_once(current,contents,config)
            except (gerrors.ServerError,gerrors.ClientError) as e:
                code=getattr(e,"code",0)
                last=e
                if code not in RETRYABLE_CODES:
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
    u=getattr(resp,"usage_metadata",None)
    in_tok=getattr(u,"prompt_token_count",0) if u else 0
    out_tok=getattr(u,"candidates_token_count",0) if u else 0
    append_event(run_id,"llm_usage",{"agent":agent,"model":model,"input_tokens":in_tok,"output_tokens":out_tok})
    return in_tok,out_tok

def _fallback_for(model):
    if model and model==GEMINI_MODEL_PRO:
        return GEMINI_MODEL_FAST
    return None

def simple_call(run_id,agent,system,user,model=None,max_output=400,want_json=False,thinking=False):
    model=model or GEMINI_MODEL_FAST
    fb=_fallback_for(model)
    append_event(run_id,"llm_call",{"agent":agent,"model":model,"prompt_chars":len(user),"want_json":want_json,"fallback":fb})
    cfg_kwargs={"max_output_tokens":max_output,"temperature":0.0,"system_instruction":system}
    if not thinking:
        cfg_kwargs["thinking_config"]=gtypes.ThinkingConfig(thinking_budget=0)
    if want_json:
        cfg_kwargs["response_mime_type"]="application/json"
    cfg=gtypes.GenerateContentConfig(**cfg_kwargs)
    resp=_generate_with_retry(run_id,agent,model,user,cfg,fallback_model=fb)
    _log_usage(run_id,agent,model,resp)
    text=(resp.text or "").strip()
    append_event(run_id,"llm_response",{"agent":agent,"chars":len(text),"preview":text[:120]})
    if want_json:
        return _extract_json(text) or {}
    return text

def tool_loop(run_id,agent,system,user,tool_decls,tool_handlers,model=None,max_iters=6,max_output=500,thinking_budget=0,temperature=0.0):
    model=model or GEMINI_MODEL_FAST
    tools=[gtypes.Tool(function_declarations=tool_decls)]
    append_event(run_id,"agent_start",{"agent":agent,"model":model,"tools":[d["name"] for d in tool_decls],"thinking_budget":thinking_budget,"temperature":temperature})

    contents=[gtypes.Content(role="user",parts=[gtypes.Part(text=user)])]
    final_text=""
    for step in range(max_iters):
        cfg=gtypes.GenerateContentConfig(
            max_output_tokens=max_output,
            temperature=temperature,
            system_instruction=system,
            tools=tools,
            thinking_config=gtypes.ThinkingConfig(thinking_budget=thinking_budget),
        )
        resp=_generate_with_retry(run_id,agent,model,contents,cfg,fallback_model=_fallback_for(model))
        _log_usage(run_id,agent,model,resp)

        cand=resp.candidates[0] if resp.candidates else None
        parts=cand.content.parts if cand and cand.content else []
        fn_calls=[p.function_call for p in parts if getattr(p,"function_call",None)]

        if not fn_calls:
            final_text=(resp.text or "").strip()
            append_event(run_id,"llm_response",{"agent":agent,"chars":len(final_text),"preview":final_text[:160]})
            break

        contents.append(gtypes.Content(role="model",parts=parts))
        tool_result_parts=[]
        for fc in fn_calls:
            name=fc.name
            args=dict(fc.args) if fc.args else {}
            append_event(run_id,"agent_tool_call",{"agent":agent,"tool":name,"args":{k:str(v)[:120] for k,v in args.items()}})
            handler=tool_handlers.get(name)
            if not handler:
                out={"error":f"unknown tool: {name}"}
            else:
                try:
                    out=handler(**args)
                except Exception as e:
                    out={"error":str(e)}
            tool_result_parts.append(gtypes.Part.from_function_response(name=name,response={"result":out} if not isinstance(out,dict) else out))
        contents.append(gtypes.Content(role="user",parts=tool_result_parts))
    else:
        append_event(run_id,"agent_max_iters",{"agent":agent,"max_iters":max_iters})

    append_event(run_id,"agent_end",{"agent":agent,"final_chars":len(final_text)})
    return final_text


# helper notes:
# get_client()             -> single shared Gemini client (created on first use)
# _generate_with_retry()   -> wraps generate_content with exponential backoff on
#                              429/500/502/503/504 (transient "high demand" errors).
#                              Tries the PRIMARY model up to max_attempts times
#                              (default 2: 2s -> 4s). If still failing AND a fallback
#                              model was provided, falls back to it and tries again.
#                              For Pro calls we set fallback=Flash automatically via
#                              _fallback_for(), so a Pro outage doesn't stall the run
#                              - it transparently degrades to Flash. Every retry and
#                              every fallback is logged (llm_retry / llm_model_fallback)
#                              so the audit log shows exactly what happened.
# _fallback_for(model)     -> returns GEMINI_MODEL_FAST when Pro was requested,
#                              else None. One-line rule, easy to extend later.
# _extract_json()    -> tries hard to pull a JSON object out of a model reply, even if
#                       it is wrapped in ```json fences or has extra text around it.
# _log_usage()       -> writes one "llm_usage" event with input/output token counts.
#                       This is how we keep an eye on token spend per agent.
# simple_call()      -> one-shot text or JSON call. Thinking is OFF by default and
#                       max_output_tokens is capped, so cost stays low. Pass want_json=True
#                       and you get a dict back (parsed for you).
# tool_loop()        -> the real agentic loop. We declare tool schemas, send the user
#                       prompt, the model can reply with one or more function_calls; we
#                       execute the matching Python handler, feed the result back, and
#                       repeat up to max_iters. Every step logs events (agent_start,
#                       agent_tool_call, llm_usage, agent_end) so the UI/audit-log can
#                       show exactly what happened, in order.
