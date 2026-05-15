import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ..storage import append_event

def _normalize(text):
    t=(text or "").lower()
    t=re.sub(r"\s+"," ",t)
    t=re.sub(r"[^a-z0-9 ]"," ",t)
    return t.strip()

def _ngrams(text,n=5):
    words=text.split()
    if len(words)<n:
        return set()
    return set(tuple(words[i:i+n]) for i in range(len(words)-n+1))

def _jaccard(a,b):
    if not a or not b:
        return 0.0
    inter=len(a&b)
    union=len(a|b)
    return inter/union if union else 0.0

def compute_similarity(run_id,docs,cosine_threshold=0.7,jaccard_threshold=0.2):
    append_event(run_id,"tool_call_start",{"tool":"compute_similarity","num_docs":len(docs)})
    ids=[d["id"] for d in docs]
    texts=[_normalize(d.get("text","")) for d in docs]

    cosine_matrix=[[0.0]*len(ids) for _ in ids]
    try:
        if any(len(t)>0 for t in texts):
            vec=TfidfVectorizer(ngram_range=(1,2),min_df=1)
            X=vec.fit_transform(texts)
            cm=cosine_similarity(X)
            cosine_matrix=[[float(v) for v in row] for row in cm]
    except Exception:
        pass

    ngram_sets=[_ngrams(t,5) for t in texts]
    jaccard_matrix=[[0.0]*len(ids) for _ in ids]
    for i in range(len(ids)):
        for j in range(len(ids)):
            jaccard_matrix[i][j]=_jaccard(ngram_sets[i],ngram_sets[j]) if i!=j else 1.0

    flags=[]
    for i in range(len(ids)):
        for j in range(i+1,len(ids)):
            c=cosine_matrix[i][j]
            jc=jaccard_matrix[i][j]
            if c>=cosine_threshold or jc>=jaccard_threshold:
                flags.append({"a":ids[i],"b":ids[j],"cosine":round(c,3),"jaccard":round(jc,3)})

    result={
        "ok":True,
        "ids":ids,
        "cosine":cosine_matrix,
        "jaccard":jaccard_matrix,
        "flags":flags,
        "thresholds":{"cosine":cosine_threshold,"jaccard":jaccard_threshold},
    }
    append_event(run_id,"tool_call_end",{"tool":"compute_similarity","flags":flags})
    return result


# helper notes:
# _normalize()         -> lowercases the text and strips punctuation so two students
#                          who copy each other but change punctuation still look similar
# _ngrams(text,n=5)    -> turns text into a set of 5-word phrases. Copying long phrases
#                          is what 5-gram Jaccard catches; paraphrasing breaks 5-grams.
# _jaccard(a,b)        -> classic |intersection| / |union| over those phrase sets
# compute_similarity() -> the main tool the agent calls. It takes a list of docs
#                          {id, text}, builds two matrices:
#                            * TF-IDF cosine (catches "same ideas, similar wording")
#                            * 5-gram Jaccard (catches "literally same phrases")
#                          Pairs above either threshold get added to `flags`.
#                          Student #3 (paraphrase of #2) should appear in flags.
#                          The agent later passes the flags to an LLM for a final
#                          judgment - similarity alone never accuses a student.
