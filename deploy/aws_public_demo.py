"""AWS CloudShell deployment. Default action is read-only; no local secrets ship.

Public judge environment: Tokyo HTTP API (TLS 1.2+), private ALB, isolated EC2,
WAF, encrypted EBS, and a 30-day expiry. Source comes from a pinned PUBLIC commit.
Run `prepare --commit SHA`, review template, then explicitly `deploy --commit SHA
--account 510266171733`. Metadata and login handout stay in ~/.bzx-public/.
"""
import argparse,base64,datetime,hashlib,json,os,re,secrets,time,urllib.request,zipfile,io
from pathlib import Path
import boto3

REGION='ap-northeast-1'
EXPECTED_ACCOUNT='510266171733'
HOME=Path.home()/'.bzx-public'

def private_file(path,content):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(content)

def template(name,bucket,key,parameter,expires,subnets,vpc,ami):
    ref=lambda n:{'Ref':n}
    att=lambda n,k:{'Fn::GetAtt':[n,k]}
    sub=lambda s:{'Fn::Sub':s}
    tags=[{'Key':'Project','Value':'BZX-PublicDemo'},{'Key':'Deployment','Value':name}]
    r={}
    def resource(n,t,p):r[n]={'Type':t,'Properties':p};return r[n]
    for keysg in ['GatewaySG','BalancerSG','AppSG']:
        resource(keysg,'AWS::EC2::SecurityGroup',dict(GroupDescription=name+' '+keysg,VpcId=vpc,Tags=tags))
    resource('GatewayToBalancer','AWS::EC2::SecurityGroupIngress',dict(GroupId=ref('BalancerSG'),SourceSecurityGroupId=ref('GatewaySG'),IpProtocol='tcp',FromPort=80,ToPort=80))
    resource('BalancerToApp','AWS::EC2::SecurityGroupIngress',dict(GroupId=ref('AppSG'),SourceSecurityGroupId=ref('BalancerSG'),IpProtocol='tcp',FromPort=8080,ToPort=8080))
    resource('Api','AWS::ApiGatewayV2::Api',dict(Name=name,ProtocolType='HTTP',Tags={'Project':'BZX-PublicDemo'}))
    resource('Link','AWS::ApiGatewayV2::VpcLink',dict(Name=name,SubnetIds=subnets,SecurityGroupIds=[ref('GatewaySG')],Tags={'Project':'BZX-PublicDemo'}))
    resource('Balancer','AWS::ElasticLoadBalancingV2::LoadBalancer',dict(Name=name,Scheme='internal',Type='application',Subnets=subnets,SecurityGroups=[ref('BalancerSG')],Tags=tags,
        LoadBalancerAttributes=[{'Key':'routing.http.drop_invalid_header_fields.enabled','Value':'true'}]))
    visibility=lambda n:dict(SampledRequestsEnabled=False,CloudWatchMetricsEnabled=True,MetricName=n)
    resource('Firewall','AWS::WAFv2::WebACL',dict(Name=name,Scope='REGIONAL',DefaultAction={'Allow':{}},VisibilityConfig=visibility(name),Tags=tags,Rules=[
        dict(Name='ViewerRate',Priority=0,Action={'Block':{}},VisibilityConfig=visibility('ViewerRate'),Statement={'RateBasedStatement':{'Limit':100,'EvaluationWindowSec':300,'AggregateKeyType':'FORWARDED_IP','ForwardedIPConfig':{'HeaderName':'x-bzx-viewer-ip','FallbackBehavior':'NO_MATCH'}}}),
        dict(Name='KnownBadInputs',Priority=1,OverrideAction={'None':{}},VisibilityConfig=visibility('KnownBadInputs'),Statement={'ManagedRuleGroupStatement':{'VendorName':'AWS','Name':'AWSManagedRulesKnownBadInputsRuleSet'}})
    ]))
    resource('FirewallLink','AWS::WAFv2::WebACLAssociation',dict(ResourceArn=ref('Balancer'),WebACLArn=att('Firewall','Arn')))
    policy=[
        {'Effect':'Allow','Action':['ssm:UpdateInstanceInformation','ssmmessages:CreateControlChannel','ssmmessages:CreateDataChannel','ssmmessages:OpenControlChannel','ssmmessages:OpenDataChannel','ec2messages:AcknowledgeMessage','ec2messages:DeleteMessage','ec2messages:FailMessage','ec2messages:GetEndpoint','ec2messages:GetMessages','ec2messages:SendReply'],'Resource':'*'},
        {'Effect':'Allow','Action':['ssm:GetDocument','ssm:DescribeDocument'],'Resource':sub('arn:aws:ssm:${AWS::Region}::document/AWS-*')},
        {'Effect':'Allow','Action':['ssm:GetParameter','ssm:DeleteParameter'],'Resource':sub('arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter'+parameter)},
        {'Effect':'Allow','Action':'kms:Decrypt','Resource':sub('arn:aws:kms:${AWS::Region}:${AWS::AccountId}:key/*'),'Condition':{'StringEquals':{'kms:ViaService':sub('ssm.${AWS::Region}.amazonaws.com'),'kms:EncryptionContext:PARAMETER_ARN':sub('arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter'+parameter)}}},
        {'Effect':'Allow','Action':'s3:GetObject','Resource':'arn:aws:s3:::'+bucket+'/'+key},
        {'Effect':'Allow','Action':['elasticloadbalancing:DeleteLoadBalancer'],'Resource':ref('Balancer')},
        {'Effect':'Allow','Action':['wafv2:DisassociateWebACL'],'Resource':[ref('Balancer'),att('Firewall','Arn')]},
        {'Effect':'Allow','Action':['wafv2:GetWebACL','wafv2:DeleteWebACL'],'Resource':att('Firewall','Arn')},
        {'Effect':'Allow','Action':'apigateway:DELETE','Resource':sub('arn:aws:apigateway:${AWS::Region}::/apis/${Api}')}
    ]
    resource('Role','AWS::IAM::Role',dict(RoleName=name,AssumeRolePolicyDocument={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'ec2.amazonaws.com'},'Action':'sts:AssumeRole'}]},Policies=[{'PolicyName':'ScopedRuntimeAndExpiry','PolicyDocument':{'Version':'2012-10-17','Statement':policy}}],Tags=tags))
    resource('Profile','AWS::IAM::InstanceProfile',dict(InstanceProfileName=name,Roles=[ref('Role')]))
    expiration_script='''import boto3,json,subprocess,time
from pathlib import Path
c=json.loads(Path('/etc/bzx-expire.json').read_text());s=boto3.Session(region_name='ap-northeast-1')
for service,method,args in [('apigatewayv2','delete_api',{'ApiId':c['api']}),('wafv2','disassociate_web_acl',{'ResourceArn':c['alb']}),('elbv2','delete_load_balancer',{'LoadBalancerArn':c['alb']})]:
 try:getattr(s.client(service),method)(**args)
 except Exception as e:print(service,type(e).__name__)
for attempt in range(12):
 try:
  w=s.client('wafv2');a=w.get_web_acl(Name=c['name'],Scope='REGIONAL',Id=c['waf']);w.delete_web_acl(Name=c['name'],Scope='REGIONAL',Id=c['waf'],LockToken=a['LockToken']);break
 except Exception:time.sleep(15)
try:s.client('ssm').delete_parameter(Name=c['parameter'])
except Exception:pass
subprocess.run(['/sbin/shutdown','-h','now'],check=False)
'''
    boot=f'''#!/bin/bash
set -euo pipefail
umask 077
dnf install -y python3.12 python3.12-pip unzip
useradd --system --home-dir /var/lib/bzx --shell /sbin/nologin bzx
mkdir -p /opt/bzx /var/lib/bzx/security
aws s3 cp s3://{bucket}/{key} /opt/bzx/source.zip --region {REGION} --only-show-errors
python3.12 - <<'PY'
import zipfile,json,pathlib,stat
root=pathlib.Path('/opt/bzx/code');root.mkdir()
with zipfile.ZipFile('/opt/bzx/source.zip') as z:
 prefix=z.namelist()[0].split('/')[0]+'/'
 names=json.loads(z.read(prefix+'scripts/release-files.json'))
 for name in names:
  p=pathlib.PurePosixPath(name)
  if p.is_absolute() or '..' in p.parts:raise ValueError('UNSAFE_SOURCE')
  info=z.getinfo(prefix+name)
  if stat.S_ISLNK(info.external_attr>>16):raise ValueError('UNSAFE_LINK')
  target=root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(info))
PY
python3.12 -m venv /opt/bzx/venv
/opt/bzx/venv/bin/pip install --only-binary=:all: -r /opt/bzx/code/requirements-opencv5.txt
chmod 755 /opt/bzx
chmod -R a+rX /opt/bzx/code /opt/bzx/venv
aws ssm get-parameter --name {parameter} --with-decryption --region {REGION} --query Parameter.Value --output text > /var/lib/bzx/origin-token
chmod 600 /var/lib/bzx/origin-token
cat > /etc/bzx.env <<'ENV'
BZX_PUBLIC_DEMO=1
BZX_PUBLIC_URL=${{Api.ApiEndpoint}}
BZX_ORIGIN_TOKEN_FILE=/var/lib/bzx/origin-token
BZX_DATA_DIR=/var/lib/bzx
ENV
cat > /etc/bzx-expire.json <<'JSON'
{{"api":"${{Api}}","alb":"${{Balancer}}","waf":"${{Firewall.Id}}","name":"{name}","parameter":"{parameter}"}}
JSON
echo {base64.b64encode(expiration_script.encode()).decode()} | base64 -d > /opt/bzx/expire.py
cat > /etc/systemd/system/bzx-expire.service <<'UNIT'
[Unit]
Description=Retire this temporary public judge deployment
[Service]
Type=oneshot
ExecStart=/opt/bzx/venv/bin/python /opt/bzx/expire.py
UNIT
cat > /etc/systemd/system/bzx-expire.timer <<'UNIT'
[Unit]
Description=Public demo expiry
[Timer]
OnCalendar={expires.strftime('%Y-%m-%d %H:%M:%S')} UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
chown -R bzx:bzx /var/lib/bzx
runuser -u bzx -- /opt/bzx/venv/bin/python - <<'PY'
import sys,pathlib,datetime
sys.path[:0]=['/opt/bzx/code/app','/opt/bzx/code/bind-zero-x/code']
from auth_security import AuthStore
a=AuthStore('/var/lib/bzx/security',judge_only=True);password=a.create_password_judge(days=30)
p=pathlib.Path('/var/lib/bzx/judge-login.txt');p.write_text('BIND ZERO-X / AWS Judge\\nLogin URL: ${{Api.ApiEndpoint}}/judge\\nUsername: judge\\nPassword: '+password+'\\nExpires UTC: {expires.isoformat()}\\nPassword only. No authenticator code is required.\\n');p.chmod(0o600)
PY
cat > /etc/systemd/system/bzx.service <<'UNIT'
[Unit]
Description=BIND ZERO-X isolated public judge console
After=network-online.target
[Service]
User=bzx
Group=bzx
EnvironmentFile=/etc/bzx.env
WorkingDirectory=/opt/bzx/code
ExecStart=/opt/bzx/venv/bin/python app/console_server.py --port 8080
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/bzx
MemoryMax=1400M
CPUQuota=150%
LimitNOFILE=1024
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now bzx bzx-expire.timer
'''
    resource('Instance','AWS::EC2::Instance',dict(ImageId=ami,InstanceType='t3.small',IamInstanceProfile=ref('Profile'),NetworkInterfaces=[{'DeviceIndex':'0','SubnetId':subnets[0],'GroupSet':[ref('AppSG')],'AssociatePublicIpAddress':True}],
        InstanceInitiatedShutdownBehavior='terminate',CreditSpecification={'CPUCredits':'standard'},MetadataOptions={'HttpTokens':'required','HttpPutResponseHopLimit':1,'HttpEndpoint':'enabled'},
        BlockDeviceMappings=[{'DeviceName':'/dev/xvda','Ebs':{'VolumeType':'gp3','VolumeSize':12,'Encrypted':True,'DeleteOnTermination':True}}],Tags=tags,
        UserData={'Fn::Base64':sub(boot)}))
    resource('Targets','AWS::ElasticLoadBalancingV2::TargetGroup',dict(Name=name,Port=8080,Protocol='HTTP',VpcId=vpc,TargetType='instance',Targets=[{'Id':ref('Instance'),'Port':8080}],HealthCheckPath='/healthz',HealthCheckIntervalSeconds=15,HealthyThresholdCount=2,Tags=tags))
    resource('Listener','AWS::ElasticLoadBalancingV2::Listener',dict(LoadBalancerArn=ref('Balancer'),Port=80,Protocol='HTTP',DefaultActions=[{'Type':'forward','TargetGroupArn':ref('Targets')}]))
    resource('Integration','AWS::ApiGatewayV2::Integration',dict(ApiId=ref('Api'),IntegrationType='HTTP_PROXY',IntegrationMethod='ANY',IntegrationUri=ref('Listener'),ConnectionType='VPC_LINK',ConnectionId=ref('Link'),PayloadFormatVersion='1.0',TimeoutInMillis=29000,
        RequestParameters={'overwrite:path':'$request.path','overwrite:header.x-bzx-origin':sub("'${OriginToken}'"),'overwrite:header.x-bzx-edge-proto':"'https'",'overwrite:header.x-bzx-viewer-ip':'$context.identity.sourceIp'}))
    resource('Route','AWS::ApiGatewayV2::Route',dict(ApiId=ref('Api'),RouteKey='$default',Target={'Fn::Join':['',['integrations/',ref('Integration')]]}))
    resource('Stage','AWS::ApiGatewayV2::Stage',dict(ApiId=ref('Api'),StageName='$default',AutoDeploy=True,DefaultRouteSettings={'ThrottlingBurstLimit':40,'ThrottlingRateLimit':2.0}))
    r['Stage']['DependsOn']='Route'
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Isolated temporary BZX public judge demo. No operator data.','Parameters':{'OriginToken':{'Type':'String','NoEcho':True,'MinLength':48}},'Resources':r,
        'Outputs':{'URL':{'Value':att('Api','ApiEndpoint')},'Instance':{'Value':ref('Instance')},'ExpiresUTC':{'Value':expires.isoformat()}}}

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('PINNED_PUBLIC_COMMIT_REQUIRED')
    s=boto3.Session(region_name=REGION);account=s.client('sts').get_caller_identity()['Account']
    if account!=EXPECTED_ACCOUNT:raise ValueError('WRONG_ACCOUNT')
    e=s.client('ec2');vpc=next(v['VpcId'] for v in e.describe_vpcs()['Vpcs'] if v.get('IsDefault'))
    subnets=sorted(e.describe_subnets(Filters=[{'Name':'vpc-id','Values':[vpc]}])['Subnets'],key=lambda v:v['AvailabilityZoneId'])[:2]
    if len({v['AvailabilityZoneId'] for v in subnets})!=2:raise ValueError('TWO_AVAILABILITY_ZONES_REQUIRED')
    ami=s.client('ssm').get_parameter(Name='/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64')['Parameter']['Value']
    name='bzx-public-'+secrets.token_hex(4);bucket=name+'-'+account;parameter='/'+name+'/origin-token'
    expires=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=30)
    body=template(name,bucket,'source/'+commit+'.zip',parameter,expires,[v['SubnetId'] for v in subnets],vpc,ami)
    metadata={'account':account,'region':REGION,'name':name,'bucket':bucket,'key':'source/'+commit+'.zip','parameter':parameter,'commit':commit,'expires':expires.isoformat(),'status':'PREPARED'}
    private_file(HOME/'template.json',json.dumps(body));private_file(HOME/'state.json',json.dumps(metadata))
    print(json.dumps({**metadata,'estimated_30_day_base_usd':'45–60 before tax; request/transfer costs vary','public_network_entry':'HTTPS HTTP API only','private_origin':'internal ALB; EC2 inbound only from ALB','expiry':'Deletes this public API/ALB/WAF and terminates its EC2/EBS. Judge-only history expires.'},ensure_ascii=False))

def deploy(account,commit):
    state=json.loads((HOME/'state.json').read_text());s=boto3.Session(region_name=REGION)
    if account!=EXPECTED_ACCOUNT or s.client('sts').get_caller_identity()['Account']!=account or state['commit']!=commit or state['status']!='PREPARED':raise ValueError('PREPARED_ACCOUNT_COMMIT_REQUIRED')
    def save(status):state['status']=status;private_file(HOME/'state.json',json.dumps(state));print(status,flush=True)
    token=secrets.token_urlsafe(48);ssm=s.client('ssm');ssm.put_parameter(Name=state['parameter'],Value=token,Type='SecureString',Overwrite=False)
    raw=urllib.request.urlopen('https://codeload.github.com/Applekeynote/bind-zero-x/zip/'+commit,timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        prefix=z.namelist()[0].split('/')[0]+'/';allow=json.loads(z.read(prefix+'scripts/release-files.json'))
        if any(n.startswith(('runtime/','data/','.tmp/')) for n in allow):raise ValueError('UNSAFE_RELEASE')
    s3=s.client('s3');s3.create_bucket(Bucket=state['bucket'],CreateBucketConfiguration={'LocationConstraint':REGION})
    s3.put_public_access_block(Bucket=state['bucket'],PublicAccessBlockConfiguration={k:True for k in ['BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets']})
    s3.put_bucket_encryption(Bucket=state['bucket'],ServerSideEncryptionConfiguration={'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]})
    s3.put_bucket_lifecycle_configuration(Bucket=state['bucket'],LifecycleConfiguration={'Rules':[{'ID':'ExpirePublicSource','Status':'Enabled','Filter':{'Prefix':'source/'},'Expiration':{'Days':45}}]})
    s3.put_object(Bucket=state['bucket'],Key=state['key'],Body=raw,ServerSideEncryption='AES256');state['source_sha256']=hashlib.sha256(raw).hexdigest()
    c=s.client('cloudformation');body=(HOME/'template.json').read_text()
    c.validate_template(TemplateBody=body)
    stack=c.create_stack(StackName=state['name'],TemplateBody=body,Parameters=[{'ParameterKey':'OriginToken','ParameterValue':token}],Capabilities=['CAPABILITY_NAMED_IAM'],OnFailure='ROLLBACK',Tags=[{'Key':'Project','Value':'BZX-PublicDemo'}])
    state['stack']=stack['StackId'];save('CREATING')
    for _ in range(120):
        d=c.describe_stacks(StackName=state['stack'])['Stacks'][0];status=d['StackStatus']
        if status=='CREATE_COMPLETE':break
        if 'FAILED' in status or 'ROLLBACK' in status:save(status);raise RuntimeError('STACK_FAILED_CHECK_EVENTS')
        time.sleep(10)
    else:raise TimeoutError('STACK_CREATION_TIMEOUT')
    outputs={o['OutputKey']:o['OutputValue'] for o in d['Outputs']};state.update(url=outputs['URL'],instance=outputs['Instance']);save('WAITING_FOR_BOOT')
    for _ in range(120):
        try:
            with urllib.request.urlopen(state['url']+'/judge',timeout=10) as response:
                if response.status==200:break
        except Exception:pass
        time.sleep(10)
    else:raise TimeoutError('APPLICATION_BOOT_TIMEOUT')
    cmd=ssm.send_command(InstanceIds=[state['instance']],DocumentName='AWS-RunShellScript',Parameters={'commands':['base64 -w0 /var/lib/bzx/judge-login.txt']},TimeoutSeconds=60)['Command']['CommandId']
    for _ in range(30):
        time.sleep(2)
        try:result=ssm.get_command_invocation(CommandId=cmd,InstanceId=state['instance'])
        except ssm.exceptions.InvocationDoesNotExist:continue
        if result['Status']=='Success':break
        if result['Status'] in ['Failed','TimedOut','Cancelled']:raise RuntimeError('HANDOUT_RETRIEVAL_FAILED')
    else:raise TimeoutError('HANDOUT_RETRIEVAL_TIMEOUT')
    handout=base64.b64decode(result['StandardOutputContent']).decode('utf-8');private_file(HOME/'judge-login.txt',handout)
    save('READY');print(json.dumps({'url':state['url']+'/judge','handout':str(HOME/'judge-login.txt'),'expires':state['expires']}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','deploy','status']);p.add_argument('--commit');p.add_argument('--account');a=p.parse_args()
    if a.action=='prepare':prepare(a.commit)
    elif a.action=='deploy':deploy(a.account,a.commit)
    else:print((HOME/'state.json').read_text())
if __name__=='__main__':main()
