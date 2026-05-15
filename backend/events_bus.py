import queue
import threading
from collections import defaultdict

_subs=defaultdict(list)
_lock=threading.Lock()

def subscribe(run_id):
    q=queue.Queue(maxsize=2000)
    with _lock:
        _subs[run_id].append(q)
    return q

def unsubscribe(run_id,q):
    with _lock:
        if q in _subs[run_id]:
            _subs[run_id].remove(q)
        if not _subs[run_id]:
            _subs.pop(run_id,None)

def publish(run_id,event):
    with _lock:
        subs=list(_subs.get(run_id,[]))
    for q in subs:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass


# helper notes:
# _subs           -> a dict: run_id -> list of subscriber queues. Every websocket
#                    client adds itself here while connected.
# _lock           -> protects _subs from threads (publish is called from sync code,
#                    subscribe/unsubscribe from async websocket handlers).
# subscribe()     -> the websocket handler calls this, gets a thread-safe queue.
# unsubscribe()   -> always called in a finally-block so disconnected clients are
#                    removed and we do not leak queues.
# publish()       -> called by storage.append_event right after writing an event.
#                    Non-blocking: if a subscriber's queue is full we just drop the
#                    event for that subscriber (this only happens if a client is
#                    very slow). The websocket also re-reads from sqlite on connect
#                    so a missed live event is still visible after reconnect.
