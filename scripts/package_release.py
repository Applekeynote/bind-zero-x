"""Build a checked-in source allowlist, never a workspace snapshot."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def source_files(root=ROOT):
    names = json.loads((root / 'scripts/release-files.json').read_text(encoding='utf-8'))
    if not isinstance(names,list) or len(names)!=len(set(names)):
        raise ValueError('INVALID_RELEASE_ALLOWLIST')
    result=[]
    for name in names:
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('UNSAFE_RELEASE_PATH')
        path=root/relative
        for component in [path,*path.parents]:
            if component==root: break
            if component.is_symlink() or (hasattr(component,'is_junction') and component.is_junction()):
                raise ValueError('LINK_IN_RELEASE')
        if (path.suffix.lower() in {'.env','.pem','.key','.cer','.db','.sqlite','.sqlite3','.protected'}
            or path.name.startswith('.env') or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve())):
            raise ValueError('UNSAFE_RELEASE_FILE')
        raw=path.read_bytes()
        if any(marker in raw for marker in (b'-----BEGIN '+b'PRIVATE KEY-----',b'-----BEGIN '+b'ENCRYPTED PRIVATE KEY-----',b'-----BEGIN '+b'RSA PRIVATE KEY-----')):
            raise ValueError('SECRET_IN_RELEASE')
        result.append(path)
    return sorted(result)

def build(root=ROOT):
    files=source_files(root)
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files)
    destination=root/'dist'
    destination.mkdir(exist_ok=True)
    archive=destination/'BIND_ZERO_X_v4.9_pixel_console.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as package:
        for path in files:
            package.write(path,path.relative_to(root).as_posix())
        package.writestr('RELEASE_SHA256.txt',manifest)
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
    return archive

if __name__=='__main__':
    archive=build()
    print(archive)
    print('SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
