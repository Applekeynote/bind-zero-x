#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Private OpenCV5 API client demo; never operates physical apparatus.

Requires a running protected server, expert ROI masks and locally approved
protocol values. Does not turn synthetic responses into physical evidence.
"""
import argparse,base64,hashlib,json,os,urllib.request,urllib.error
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',default='http://127.0.0.1:8080')
    p.add_argument('--config',required=True,help='JSON containing session_id, observation_id, worlds, losses, view_signatures, view_costs, calibration, roi_manifest')
    for x in ('frame0','frame1','upper_mask','lower_mask'):
        p.add_argument('--'+x.replace('_','-'),required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    token=os.getenv('BZX_RESEARCH_TOKEN','')
    if len(token)<32:raise SystemExit('BZX_RESEARCH_TOKEN (>=32 chars) required')
    body=json.loads(Path(args.config).read_text(encoding='utf-8'))
    for key in ('frame0','frame1','upper_mask','lower_mask'):
        content=Path(getattr(args,key)).read_bytes()
        if len(content)>2_500_000 or not content.startswith(b'\x89PNG\r\n\x1a\n'):
            raise SystemExit('PNG input size/signature invalid for '+key)
        body[key+'_png_b64']=base64.b64encode(content).decode()
    raw=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
    req=urllib.request.Request(args.url.rstrip('/')+'/api/research/loop/start-captured',raw,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=30) as res:
            response=json.load(res)
    except urllib.error.HTTPError as ex:
        raise SystemExit(f'SERVER_REJECTED HTTP {ex.code}: '+ex.read()[:300].decode(errors='replace'))
    filtered={k:v for k,v in response.items() if k not in ('raw_image','authorization')}
    filtered['client_input_json_sha256']=hashlib.sha256(raw).hexdigest()
    filtered['not_real_gt_or_physical_authorization']=True
    Path(args.output).write_text(json.dumps(filtered,ensure_ascii=False,indent=2),encoding='utf-8')
    print('server initial archive receipt:',response.get('initial_capture_receipt_sha256'))
    print('initial source:',response.get('initial_capture_origin'))
    print('next:',response.get('disposition'),response.get('next_view'))
    print('physical action authorized:',response.get('physical_action_authorized'))
if __name__=='__main__':main()
