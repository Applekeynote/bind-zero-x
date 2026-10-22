"""Read-only operator audit for local research mode. Never delete data."""
import argparse,json,sqlite3
from sqlite_scope import connect
from pathlib import Path
from capture_archive import audit_archive
from research_loop_store import SQLiteResearchLoops,StoreError

def inspect(db_path,archive_dir):
    store=SQLiteResearchLoops(db_path)
    with connect(db_path) as db:
        sessions=[x[0] for x in db.execute('SELECT session_id FROM research_loops ORDER BY session_id')]
        reservations=list(db.execute('SELECT session_id,status FROM capture_start_reservations ORDER BY session_id')) if db.execute("SELECT 1 FROM sqlite_master WHERE name='capture_start_reservations'").fetchone() else []
    refs=[];failures=[]
    for sid in sessions:
        try:
            _,s=store.read(sid)
            if s.initial_capture_origin=='SERVER_CAPTURED_PNG':refs.append(s.initial_image_sha256)
        except StoreError as e:failures.append({'session_id':sid,'reason':str(e)})
    inventory=audit_archive(archive_dir,refs)
    return {'status':'ATTENTION' if failures or inventory['status']!='INVENTORIED' else 'OK',
            'session_count':len(sessions),'session_validation_failures':failures,
            'capture_reservations':[{'session_id':s,'status':t} for s,t in reservations],
            'archive':inventory,'note':'READ_ONLY_LOCAL_RESEARCH_AUDIT_NOT_AWS_PROVENANCE'}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--db',required=True);a.add_argument('--archive',required=True);a.add_argument('--output',required=True)
    args=a.parse_args();Path(args.output).write_text(json.dumps(inspect(args.db,args.archive),ensure_ascii=False,indent=2),encoding='utf-8')
