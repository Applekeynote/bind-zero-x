# -*- coding:utf-8 -*-
"""TWO SYNTHETIC scenarios: OpenCV4/5 -> layer SE2 -> witness next view.
The next view is from ILLUSTRATIVE handcrafted signatures, not measured material GT.
"""
import sys,json,hashlib,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from test_synthetic_opencv import image_pair
from research_pipeline import analyze
import cv2

def run_case(name,slip,local_rotation):
 a,b,m=image_pair(slip=slip,local_rotation=local_rotation)
 manifest=dict(operator_verified=True,frame0_sha256=hashlib.sha256(a.tobytes()).hexdigest(),
     layers={k:dict(mask_sha256=hashlib.sha256(v.tobytes()).hexdigest(),layer_label=k,source_id='SYNTH-'+k)
             for k,v in m.items()})
 output=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='SYNTH_PLANE',calibration_id='SYNTH_SCALE',verified=True),
                name,require_opencv5=False,roi_manifest=manifest,threshold_mm=5.)
 return {'name':name,'input_ground_truth':'SYNTHETIC_PIXEL_TRANSFORMS_ONLY',
         'gt_slip_px':slip,'gt_local_rotation_deg':local_rotation,
         'measured':output['measurement'],'local_rule':output['decision'],
         'hypothetical_witness':{k:v for k,v in output['research_witness'].items() if k!='hypothetical_model'},
         'source_tier':'SYNTHETIC_DEMO_NOT_PHYSICAL_EVIDENCE'}

def main():
 data={'scope':'SYNTHETIC_OPENCV_LOCAL', 'opencv_version':cv2.__version__,
       'cases':[run_case('COMMON_MOTION', (0,0),0),run_case('RELATIVE_LAYER_SLIP',(9,0),0),
                run_case('RELATIVE_ROTATION',(0,0),8)]}
 views=[i['hypothetical_witness']['next_observation'] for i in data['cases']]
 assert views[0]!=views[1]
 assert views[1]==views[2]
 print(json.dumps(data,ensure_ascii=False,indent=2))
 if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
