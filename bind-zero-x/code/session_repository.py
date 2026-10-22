# coding: utf-8
"""SQLite reference for atomic approvals + durable idempotency.
This is NOT AWS/DynamoDB: a production port must provide equivalent transactional
semantics with ownership checks, stored responses, and conditional version updates.
"""
from dataclasses import asdict
import sqlite3, json, hashlib
from sqlite_scope import connect
from cape_rule_core import Session,approval_event,confirm_human_execution,ActionError

class DurableSessions:
    def __init__(self,filepath):
        self.filepath=str(filepath)
        with self._conn() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)')
            c.execute('''CREATE TABLE IF NOT EXISTS idempotency
                (session_id TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,
                 response TEXT NOT NULL,PRIMARY KEY(session_id,key))''')

    def _conn(self):
        c=connect(self.filepath,timeout=10,isolation_level=None)
        c.row_factory=sqlite3.Row
        return c

    @staticmethod
    def _encode(s:Session)->str:
        d=asdict(s);d['allowed_actions']=sorted(s.allowed_actions)
        d['accepted_observation_ids']=sorted(s.accepted_observation_ids)
        return json.dumps(d,sort_keys=True,ensure_ascii=False)

    @staticmethod
    def _decode(txt:str)->Session:
        d=json.loads(txt)
        d['allowed_actions']=frozenset(d['allowed_actions'])
        d['accepted_observation_ids']=frozenset(d['accepted_observation_ids'])
        return Session(**d)

    def create(self,s:Session):
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('INSERT INTO sessions VALUES(?,?,?)',(s.session_id,s.owner_sub,self._encode(s)))
            c.commit()

    def read(self,sid:str,auth_sub:str):
        with self._conn() as c:
            r=c.execute('SELECT owner,body FROM sessions WHERE id=?',(sid,)).fetchone()
            if r is None or r['owner']!=auth_sub:raise ActionError('NOT_AUTHORIZED_OR_NOT_FOUND')
            return self._decode(r['body'])

    def approve(self,sid:str,action:str,key:str,version:int,observation_id:str,auth_sub:str):
        req={'session_id':sid,'action':action,'key':key,'expected_version':version,
             'observation_id':observation_id,'auth_sub':auth_sub}
        finger=hashlib.sha256(json.dumps(req,sort_keys=True).encode()).hexdigest()
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT owner,body FROM sessions WHERE id=?',(sid,)).fetchone()
            if row is None or row['owner']!=auth_sub:raise ActionError('NOT_AUTHORIZED_OR_NOT_FOUND')
            old=c.execute('SELECT fingerprint,response FROM idempotency WHERE session_id=? AND key=?',
                          (sid,key)).fetchone()
            if old is not None:
                if old['fingerprint']!=finger:raise ActionError('IDEMPOTENCY_KEY_REUSE_CONFLICT')
                return self._decode(old['response'])  # original response, not current state
            before=self._decode(row['body'])
            after=approval_event(before,action,key,version,observation_id,auth_sub)
            body=self._encode(after)
            changed=c.execute('UPDATE sessions SET body=? WHERE id=? AND body=?',
                              (body,sid,row['body'])).rowcount
            if changed!=1:raise ActionError('VERSION_CONFLICT')
            c.execute('INSERT INTO idempotency VALUES(?,?,?,?)',(sid,key,finger,body))
            c.commit()
            return after

    def confirm(self,sid:str,action:str,version:int,auth_sub:str):
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT owner,body FROM sessions WHERE id=?',(sid,)).fetchone()
            if row is None or row['owner']!=auth_sub:raise ActionError('NOT_AUTHORIZED_OR_NOT_FOUND')
            before=self._decode(row['body'])
            after=confirm_human_execution(before,action,auth_sub,version)
            changed=c.execute('UPDATE sessions SET body=? WHERE id=? AND body=?',
                              (self._encode(after),sid,row['body'])).rowcount
            if changed!=1:raise ActionError('VERSION_CONFLICT')
            c.commit()
            return after
