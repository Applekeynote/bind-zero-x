# -*- coding: utf-8 -*-
"""Research-only local immutable PNG capture archive.

Keeps exact uploaded PNG bytes with content-addressed filenames. Does NOT
claim AWS S3 Object Lock, trusted camera capture time, or image authenticity.
An integrity digest does not independently prove what a camera saw.
"""
from __future__ import annotations
import os,hashlib,json,stat
from pathlib import Path

class CaptureArchiveError(ValueError):pass

def _canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def _atomic_create(path,content):
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    if hasattr(os,'O_NOFOLLOW'):flags|=os.O_NOFOLLOW
    try: fd=os.open(str(path),flags,0o600)
    except FileExistsError:
        # Immutable: never overwrite; detect truncated/different-content files.
        if path.is_symlink() or not path.is_file() or path.read_bytes()!=content:
            raise CaptureArchiveError('ARCHIVE_CONTENT_MISMATCH')
        return
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(content);f.flush();os.fsync(f.fileno())
    except Exception:
        try:path.unlink()
        except OSError:pass
        raise

def persist_capture(archive_dir,session_id,observation_id,images,metadata):
    if not archive_dir or not isinstance(session_id,str) or not isinstance(observation_id,str):
        raise CaptureArchiveError('ARCHIVE_NOT_CONFIGURED')
    if set(images)!={'frame0','frame1','upper_mask','lower_mask'}:
        raise CaptureArchiveError('INCOMPLETE_CAPTURE_SET')
    root=Path(archive_dir)
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if not root.is_dir() or root.is_symlink():raise CaptureArchiveError('INVALID_ARCHIVE_DIRECTORY')
    image_info={}
    for name,content in sorted(images.items()):
        if not isinstance(content,bytes) or not content.startswith(b'\x89PNG\r\n\x1a\n') or len(content)>2_500_000:
            raise CaptureArchiveError('INVALID_PNG_PAYLOAD')
        digest=hashlib.sha256(content).hexdigest()
        _atomic_create(root/(digest+'.png'),content)
        image_info[name]={'sha256':digest,'bytes':len(content)}
    manifest={'schema':'BZX-INITIAL-CAPTURE-MANIFEST-V1','session_id':session_id,
              'observation_id':observation_id,'images':image_info,'metadata':metadata,
              'capture_provenance':'SERVER_RECEIVED_BYTES_NOT_TRUSTED_CAMERA_ATTESTATION'}
    raw=_canonical(manifest);hash_value=hashlib.sha256(raw).hexdigest()
    _atomic_create(root/(hash_value+'.json'),raw)
    if not verify_capture(archive_dir,hash_value):raise CaptureArchiveError('ARCHIVE_POSTWRITE_VERIFICATION_FAILED')
    return hash_value

def verify_capture(archive_dir,hash_value):
    if not isinstance(hash_value,str) or len(hash_value)!=64 or any(c not in '0123456789abcdef' for c in hash_value):
        return False
    try:
        root=Path(archive_dir)
        manifest_path=root/(hash_value+'.json')
        if manifest_path.is_symlink():return False
        raw=manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=hash_value:return False
        m=json.loads(raw)
        if m.get('schema')!='BZX-INITIAL-CAPTURE-MANIFEST-V1' or set(m.get('images',{}))!={'frame0','frame1','upper_mask','lower_mask'}:
            return False
        for item in m['images'].values():
            obj_path=root/(item['sha256']+'.png')
            if obj_path.is_symlink():return False
            data=obj_path.read_bytes()
            if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
                return False
        return True
    except (OSError,ValueError,KeyError,TypeError,OverflowError):return False


def audit_archive(archive_dir, live_receipts):
    """Read-only inventory; safe for operations dashboards and garbage-collection review.

    Does not delete content-addressed objects: a PNG can be shared across sessions.
    """
    root=Path(archive_dir)
    if not root.exists():return {'status':'MISSING_ARCHIVE','missing_receipts':sorted(live_receipts)}
    referenced=set();issues=[]
    for receipt in live_receipts:
        if not verify_capture(root,receipt):
            issues.append(receipt);continue
        m=json.loads((root/(receipt+'.json')).read_bytes())
        referenced.add(receipt+'.json')
        referenced.update(item['sha256']+'.png' for item in m['images'].values())
    inventory={x.name for x in root.iterdir() if x.is_file() and not x.is_symlink() and x.suffix in ('.png','.json')}
    return {'status':'CHECK_REQUIRED' if issues else 'INVENTORIED',
            'missing_or_corrupt_receipts':sorted(issues),
            'orphan_candidates_REVIEW_BEFORE_DELETE':sorted(inventory-referenced),
            'referenced_objects':len(referenced)}
