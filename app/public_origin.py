"""Verified AWS gateway boundary for the isolated public judge deployment."""
import hmac
import ipaddress
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from starlette.responses import JSONResponse


class PublicOrigin:
    def __init__(self,app,url,token,budget_file=None):
        parsed=urlsplit(url)
        if (parsed.scheme!='https' or not re.fullmatch(r'(d[a-z0-9]+\.cloudfront\.net|[a-z0-9]+\.execute-api\.ap-northeast-1\.amazonaws\.com)',parsed.netloc)
            or parsed.path not in ('','/') or parsed.query or parsed.fragment or len(token)<48):
            raise ValueError('INVALID_PUBLIC_ORIGIN_CONFIGURATION')
        self.app,self.host,self.token=app,parsed.netloc,token
        self.gateway='.execute-api.' in self.host
        self.budget=OutboundBudget(budget_file) if budget_file else None

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        if scope['path']=='/healthz' and scope['method']=='GET':
            return await JSONResponse({'status':'ready'},headers={'Cache-Control':'no-store'})(scope,receive,send)
        pairs=scope.get('headers',[]);headers={k.lower():v for k,v in pairs}
        def unique(key):return sum(k.lower()==key for k,_ in pairs)==1
        supplied=headers.get(b'x-bzx-origin',b'')
        if (not unique(b'x-bzx-origin') or not hmac.compare_digest(supplied,self.token.encode())
            or headers.get(b'x-bzx-edge-proto' if self.gateway else b'cloudfront-forwarded-proto')!=b'https'):
            return await JSONResponse({'detail':'NOT_FOUND'},status_code=404,headers={'Cache-Control':'no-store'})(scope,receive,send)
        try:
            address=headers[b'x-bzx-viewer-ip' if self.gateway else b'cloudfront-viewer-address'].decode('ascii')
            if self.gateway:peer=address
            elif address.startswith('['):peer=address[1:address.index(']')]
            else:peer=address.rsplit(':',1)[0]
            peer=str(ipaddress.ip_address(peer))
        except (KeyError,ValueError,UnicodeError):
            return await JSONResponse({'detail':'INVALID_EDGE_CONTEXT'},status_code=400)(scope,receive,send)
        blocked={b'host',b'forwarded',b'x-forwarded-for',b'x-forwarded-proto',b'x-forwarded-host',b'x-bzx-origin'}
        scope={**scope,'scheme':'https','server':(self.host,443),'client':(peer,0),
            'headers':[(k,v) for k,v in pairs if k.lower() not in blocked]+[(b'host',self.host.encode())]}
        rejected=False
        async def bounded_send(message):
            nonlocal rejected
            if message['type']=='http.response.start' and self.budget:
                response_headers=dict(message.get('headers',[]))
                amount=int(response_headers.get(b'content-length',b'524288'))+1024
                if not self.budget.reserve(amount):
                    rejected=True
                    await JSONResponse({'detail':'DAILY_DEMO_QUOTA_REACHED'},status_code=429,headers={'Cache-Control':'no-store'})(scope,receive,send)
                    return
            if not rejected:await send(message)
        return await self.app(scope,receive,bounded_send)


class OutboundBudget:
    """Durable per-day and lifetime byte reservations, including restarts."""
    def __init__(self,path,daily=500*1024**2,total=5*1024**3):
        self.path,self.daily,self.total=path,daily,total
        with closing(sqlite3.connect(path)) as db,db:db.execute('CREATE TABLE IF NOT EXISTS outgoing(day INTEGER PRIMARY KEY,bytes INTEGER NOT NULL)')
    def reserve(self,amount):
        day=int(time.time()//86400)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            used=db.execute('SELECT COALESCE(SUM(bytes),0) FROM outgoing').fetchone()[0]
            daily=db.execute('SELECT bytes FROM outgoing WHERE day=?',(day,)).fetchone()
            if amount<0 or used+amount>self.total or (daily[0] if daily else 0)+amount>self.daily:return False
            db.execute('INSERT INTO outgoing VALUES(?,?) ON CONFLICT(day) DO UPDATE SET bytes=bytes+excluded.bytes',(day,amount))
        return True


def load_public_origin(app,url,token_file):
    path=Path(token_file)
    if path.is_symlink() or (path.stat().st_mode&0o077):raise ValueError('INSECURE_ORIGIN_TOKEN_FILE')
    return PublicOrigin(app,url,path.read_text('utf-8').strip(),path.parent/'edge-budget.db')
