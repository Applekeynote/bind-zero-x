"""Bundle allowlisted code for the bounded AWS evidence runner."""
from pathlib import Path
import zipfile
from package_release import source_files

root=Path(__file__).resolve().parents[1]
dist=root/'dist'
dist.mkdir(exist_ok=True)
runtime=dist/'bzx-aws-runtime.zip'
with zipfile.ZipFile(runtime,'w',zipfile.ZIP_DEFLATED) as package:
    for path in source_files(root):
        name=path.relative_to(root).as_posix()
        if (name.startswith('bind-zero-x/code/') and not path.name.startswith('test_')) or name in ('requirements-opencv5.txt','scripts/verify_opencv5.py'):
            package.write(path,name)
with zipfile.ZipFile(dist/'bzx-aws-job.zip','w',zipfile.ZIP_DEFLATED) as package:
    package.write(runtime,'runtime.zip')
    package.write(root/'scripts/aws_evidence_job.py','aws_evidence_job.py')
print(dist/'bzx-aws-job.zip')
