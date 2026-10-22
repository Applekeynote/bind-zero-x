# -*- coding: utf-8 -*-
"""Local SQLite CAS + integrity MAC for research sessions (NOT AWS durability).

The MAC uses BZX_RESEARCH_INTEGRITY_KEY from an external secret store in deployment,
or a separate local 0600 key file for offline developer tests. Anyone able to
replace both SQLite and that local key can forge the store: not a security claim.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import sqlite3, json, os, hmac, hashlib, secrets
from sqlite_scope import connect
from active_evidence_loop import ResearchLoop,EvidenceStep,continue_research_loop,trace_dict,LoopError,validate_loop
from witness_planner import DecisionWitness

class StoreError(ValueError): pass

def encode(s:ResearchLoop)->str:
    validate_loop(s)
    return json.dumps(asdict(s),sort_keys=True,ensure_ascii=False,allow_nan=False,
                      separators=(',',':'))

def decode(blob:str)->ResearchLoop:
    try:
        d=json.loads(blob)
        wit=d['witness']
        for k in ('possible_worlds','common_optimal_actions','conflict_core','counterexample_pair'):
            if wit.get(k) is not None:wit[k]=tuple(wit[k])
        wit['candidate_view_risks']=tuple(tuple(x) for x in wit['candidate_view_risks'])
        d['witness']=DecisionWitness(**wit)
        d['steps']=tuple(EvidenceStep(**{**x,'worlds_before':tuple(x['worlds_before']),
                                    'worlds_after':tuple(x['worlds_after'])}) for x in d['steps'])
        for k in ('worlds','candidate_views'):d[k]=tuple(d[k])
        result=ResearchLoop(**d)
        validate_loop(result)
        return result
    except (KeyError,TypeError,ValueError,IndexError,AttributeError) as e:
        raise StoreError('CORRUPTED_OR_UNBOUND_SESSION') from e

class SQLiteResearchLoops:
    def __init__(self,path):
        self.path=str(path)
        self._key=self._init_key()
        with connect(self.path) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS research_loops
                       (session_id TEXT PRIMARY KEY,version INTEGER NOT NULL,
                        body TEXT NOT NULL,record_mac TEXT NOT NULL)''')
            columns={x[1] for x in db.execute('PRAGMA table_info(research_loops)')}
            if 'record_mac' not in columns:
                db.execute("ALTER TABLE research_loops ADD COLUMN record_mac TEXT NOT NULL DEFAULT ''")

    def _init_key(self):
        explicit=os.environ.get('BZX_RESEARCH_INTEGRITY_KEY')
        if explicit:
            if len(explicit)<32:raise StoreError('WEAK_INTEGRITY_KEY')
            return hashlib.sha256(explicit.encode()).digest()
        # Development-only, independent file with restrictive permissions.
        path=self.path+'.hmac_key'
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as file:file.write(secrets.token_bytes(32))
        except FileExistsError:pass
        key=Path(path).read_bytes()
        if len(key)!=32:raise StoreError('INVALID_LOCAL_INTEGRITY_KEY')
        return key

    def _mac(self,session_id,version,body):
        payload=json.dumps([session_id,version,body],separators=(',',':')).encode()
        return hmac.new(self._key,payload,hashlib.sha256).hexdigest()

    def _read_row(self,db,session_id):
        row=db.execute('SELECT version,body,record_mac FROM research_loops WHERE session_id=?',
                       (session_id,)).fetchone()
        if row is None:raise StoreError('SESSION_NOT_FOUND')
        version,body,mac=row
        if not hmac.compare_digest(self._mac(session_id,version,body),mac):
            raise StoreError('STORED_SESSION_INTEGRITY_FAILED')
        return version,decode(body)

    def start(self,s:ResearchLoop):
        body=encode(s)
        with connect(self.path,timeout=10) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO research_loops VALUES(?,?,?,?)',
                           (s.session_id,0,body,self._mac(s.session_id,0,body)))
                db.commit()
            except sqlite3.IntegrityError as e:
                db.rollback();raise StoreError('SESSION_EXISTS') from e
        return dict(version=0,**trace_dict(s))

    def read(self,session_id):
        with connect(self.path) as db:
            version,state=self._read_row(db,session_id)
        self._assert_capture_available(state)
        return version,state

    @staticmethod
    def _assert_capture_available(state):
        if state.initial_capture_origin!='SERVER_CAPTURED_PNG':
            return
        from capture_archive import verify_capture
        directory=os.environ.get('BZX_CAPTURE_ARCHIVE_DIR','')
        if not directory or not verify_capture(directory,state.initial_image_sha256):
            raise StoreError('EVIDENCE_UNAVAILABLE')

    def reserve_capture_start(self,session_id):
        # Unique reservation before object writes prevents duplicate-request orphan objects.
        with connect(self.path,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS capture_start_reservations
                (session_id TEXT PRIMARY KEY,status TEXT NOT NULL)''')
            if db.execute('SELECT 1 FROM research_loops WHERE session_id=?',(session_id,)).fetchone():
                raise StoreError('SESSION_EXISTS')
            try:db.execute('INSERT INTO capture_start_reservations VALUES(?,?)',(session_id,'PENDING'))
            except sqlite3.IntegrityError as e:raise StoreError('CAPTURE_START_ALREADY_RESERVED') from e
            db.commit()

    def finalize_capture_start(self,session_id):
        with connect(self.path,timeout=10) as db:
            db.execute('UPDATE capture_start_reservations SET status=? WHERE session_id=?',('COMMITTED',session_id))

    def release_capture_start(self,session_id):
        with connect(self.path,timeout=10) as db:
            db.execute('DELETE FROM capture_start_reservations WHERE session_id=? AND status=?',(session_id,'PENDING'))


    def _advance(self,session_id,expected_version,view,signature,capture_sha256,
                 *,source,cv_result=None,trusted_cv_validator=None,cv_threshold_mm=5.0):
        with connect(self.path,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            version,current=self._read_row(db,session_id)
            self._assert_capture_available(current)
            if version!=expected_version:raise StoreError('VERSION_CONFLICT')
            next_state=continue_research_loop(current,view,signature,capture_sha256,source=source,
                cv_result=cv_result,trusted_cv_validator=trusted_cv_validator,cv_threshold_mm=cv_threshold_mm)
            body=encode(next_state)
            updated=db.execute('''UPDATE research_loops SET version=?,body=?,record_mac=?
                                  WHERE session_id=? AND version=?''',
                               (version+1,body,self._mac(session_id,version+1,body),
                                session_id,version)).rowcount
            if updated!=1:raise StoreError('VERSION_CONFLICT')
            db.commit()
        return dict(version=version+1,**trace_dict(next_state))

    def advance(self,session_id,expected_version,view,signature,capture_sha256,
                *,source='HUMAN_REPORTED'):
        if source!='HUMAN_REPORTED':raise StoreError('SERVER_SIDE_CV_REQUIRED')
        return self._advance(session_id,expected_version,view,signature,capture_sha256,
                             source=source)

    def advance_cv_internal(self,session_id,expected_version,view,capture_sha256,cv_result,
                            *,trusted_cv_validator,qualified_signature=None,cv_threshold_mm=5.0):
        """Server-internal only. Never expose client-provided CV attestations."""
        m=cv_result.get('measurement') if isinstance(cv_result,dict) else None
        if not isinstance(m,dict):raise StoreError('CV_MEASUREMENT_UNAVAILABLE')
        if (qualified_signature is None or qualified_signature=='?') and m.get('uncertainty_status')=='EMPIRICALLY_CALIBRATED':
            raise StoreError('GT_GATE_SIGNATURE_REQUIRED')
        if qualified_signature is None or qualified_signature=='?':
            return self._advance(session_id,expected_version,view,'?',capture_sha256,
                source='CV_UNCALIBRATED',cv_result=cv_result,
                trusted_cv_validator=trusted_cv_validator)
        if qualified_signature not in ('layer_moves','layer_still'):
            raise StoreError('INVALID_GT_GATE_SIGNATURE')
        if m.get('uncertainty_status')!='EMPIRICALLY_CALIBRATED':
            raise StoreError('NO_APPROVED_GT_ENVELOPE')
        return self._advance(session_id,expected_version,view,qualified_signature,capture_sha256,
            source='CV_LAYER_ONLY',cv_result=cv_result,cv_threshold_mm=cv_threshold_mm,
            trusted_cv_validator=trusted_cv_validator)
