"""Single use-case service: reserve -> persist -> initialize -> release.

Local reference implementation, not distributed transaction across DB / S3.
Orphans from crashed writers are detected by audit_archive and cleaned only after review.
"""
from research_loop_store import StoreError
from active_evidence_loop import start_research_loop
from capture_archive import persist_capture

def start_captured(store, archive, *,session_id,observation_id,raw_images,metadata,
                   worlds,losses,view_signatures,view_costs):
    # Reject invalid models before reserving identifiers or persisting any bytes.
    start_research_loop(session_id,observation_id,worlds,losses,
        view_signatures,view_costs,'0'*64)
    store.reserve_capture_start(session_id)
    try:
        receipt=persist_capture(archive,session_id,observation_id,raw_images,metadata)
        loop=start_research_loop(session_id,observation_id,worlds,losses,
            view_signatures,view_costs,receipt,initial_capture_origin='SERVER_CAPTURED_PNG')
        result=store.start(loop)
        store.finalize_capture_start(session_id)
        return result,receipt
    except BaseException:
        store.release_capture_start(session_id)
        raise
