"""Run a bounded, private EC2 OpenCV 5 evidence job in the user's AWS account.

Use in an authenticated AWS CloudShell. No IAM role/key pair or ingress rule is
created. Instances stop after the job (or at the boot-time 20 minute deadline).
Stopped encrypted EBS and private S3 evidence are retained for review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import time


def save(path, state):
    path.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')


def launch(region, source, minutes, budget):
    import boto3
    if region != 'ap-northeast-1' or not 5 <= minutes <= 20 or budget < 5:
        raise ValueError('TOKYO_ONLY_MAX_20_MINUTES_MINIMUM_5_USD_ALLOWANCE')
    session = boto3.Session(region_name=region)
    ec2 = session.client('ec2'); s3 = session.client('s3')
    identity = session.client('sts').get_caller_identity()
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])['Vpcs']
    if len(vpcs) != 1:
        raise RuntimeError('EXISTING_DEFAULT_VPC_REQUIRED_NO_NETWORK_WILL_BE_CREATED')
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpcs[0]['VpcId']]},
                                          {'Name': 'default-for-az', 'Values': ['true']}])['Subnets']
    subnets = sorted((s for s in subnets if s['AvailableIpAddressCount'] > 2), key=lambda s: s['AvailabilityZone'])
    if not subnets:
        raise RuntimeError('NO_EXISTING_DEFAULT_SUBNET')
    ami = session.client('ssm').get_parameter(Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64')['Parameter']['Value']
    suffix = secrets.token_hex(4)
    state_path = Path('bzx-job-' + suffix + '.json')
    state = dict(region=region, account=identity['Account'], status='PREPARING',
                 max_runtime_minutes=minutes, instance_type='t3.small', ingress_rules=[],
                 budget_ceiling_usd=budget, iam_role_created=False, key_pair_created=False,
                 retained_storage_note='Stopped 10GiB encrypted EBS and private S3 remain billable; review before deletion.')
    save(state_path, state)
    bucket = 'bzx-evidence-' + identity['Account'] + '-' + suffix
    s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={'LocationConstraint': region})
    state['bucket'] = bucket; save(state_path, state)
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration=dict(
        BlockPublicAcls=True, IgnorePublicAcls=True, BlockPublicPolicy=True, RestrictPublicBuckets=True))
    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={'Rules': [
        {'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
    source = Path(source)
    s3.upload_file(str(source), bucket, 'source/runtime.zip')
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    get_url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': 'source/runtime.zip'}, ExpiresIn=3600)
    put_url = s3.generate_presigned_url('put_object', Params={'Bucket': bucket, 'Key': 'evidence/opencv5.tar.gz'}, ExpiresIn=3600)
    group = ec2.create_security_group(GroupName='bzx-private-evidence-' + suffix,
        Description='BZX temporary evidence worker: no inbound access', VpcId=vpcs[0]['VpcId'])['GroupId']
    state['security_group'] = group; save(state_path, state)
    user_data = '''#!/bin/bash
set -euo pipefail
exec > >(tee -a /var/log/bzx-job.log /dev/console) 2>&1
shutdown -h +__MINUTES__
trap 'shutdown -h now' EXIT
echo BZX_JOB_BOOTSTRAP_STARTED
dnf install -y python3.12 python3.12-pip
install -d -m 755 /opt/bzx
curl --fail --silent --show-error '__GET_URL__' -o /opt/bzx/source.zip
echo '__SHA__  /opt/bzx/source.zip' | sha256sum -c -
python3 -m zipfile -e /opt/bzx/source.zip /opt/bzx
python3.12 -m venv /opt/bzx/venv
/opt/bzx/venv/bin/python -m pip install --no-cache-dir -r /opt/bzx/requirements-opencv5.txt
id bzx >/dev/null 2>&1 || useradd --system --home-dir /opt/bzx --shell /sbin/nologin bzx
chown -R bzx:bzx /opt/bzx
cd /opt/bzx
export AWS_REGION=ap-northeast-1 AWS_EXECUTION_ENV=BZX_EC2_EVIDENCE_JOB
runuser -u bzx --preserve-environment -- /opt/bzx/venv/bin/python scripts/verify_opencv5.py --output runtime/evidence/opencv5-aws
tar -czf /opt/bzx/evidence.tar.gz -C /opt/bzx/runtime/evidence/opencv5-aws execution.json opencv-build.txt captures
curl --fail --silent --show-error -X PUT --upload-file /opt/bzx/evidence.tar.gz '__PUT_URL__'
echo BZX_OPENCV5_AWS_EVIDENCE_UPLOADED
'''.replace('__MINUTES__', str(minutes)).replace('__GET_URL__', get_url).replace('__PUT_URL__', put_url).replace('__SHA__', source_sha)
    launched = ec2.run_instances(ImageId=ami, InstanceType='t3.small', MinCount=1, MaxCount=1,
        InstanceInitiatedShutdownBehavior='stop', UserData=user_data,
        MetadataOptions={'HttpTokens': 'required', 'HttpEndpoint': 'enabled'},
        NetworkInterfaces=[dict(DeviceIndex=0, SubnetId=subnets[0]['SubnetId'], Groups=[group],
                                AssociatePublicIpAddress=True)],
        BlockDeviceMappings=[dict(DeviceName='/dev/xvda', Ebs=dict(VolumeSize=10, VolumeType='gp3', Encrypted=True, DeleteOnTermination=True))],
        CreditSpecification={'CpuCredits': 'standard'},
        TagSpecifications=[dict(ResourceType='instance', Tags=[{'Key': 'Name', 'Value': 'BIND-ZERO-X-evidence-' + suffix},
                              {'Key': 'Purpose', 'Value': 'OpenCV5-research-evidence'}])])
    instance = launched['Instances'][0]['InstanceId']
    state.update(instance_id=instance, source_sha256=source_sha, status='RUNNING')
    save(state_path, state)
    print('BZX_INSTANCE_LAUNCHED', instance, 'REGION', region, 'AUTO_STOP_MINUTES', minutes, flush=True)
    start = time.monotonic()
    while time.monotonic() - start < minutes * 60:
        try:
            s3.download_file(bucket, 'evidence/opencv5.tar.gz', 'bzx-aws-evidence.tar.gz')
            state['status'] = 'EVIDENCE_DOWNLOADED'
            save(state_path, state)
            print('BZX_EVIDENCE_DOWNLOADED bzx-aws-evidence.tar.gz', flush=True)
            break
        except Exception as exc:
            code = getattr(exc, 'response', {}).get('Error', {}).get('Code')
            if code not in ('404', 'NoSuchKey'):
                raise
        time.sleep(15)
    # An independent controller also stops the worker if cloud-init fails before shutdown.
    ec2.stop_instances(InstanceIds=[instance])
    state['stop_requested'] = True
    if state['status'] != 'EVIDENCE_DOWNLOADED':
        state['status'] = 'FAILED_NO_EVIDENCE'
    save(state_path, state)
    print('BZX_JOB_STATUS', state['status'], 'STATE_FILE', state_path, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', default='ap-northeast-1')
    parser.add_argument('--source', required=True)
    parser.add_argument('--minutes', type=int, default=20)
    parser.add_argument('--budget-usd', type=float, required=True)
    args = parser.parse_args()
    launch(args.region, args.source, args.minutes, args.budget_usd)
