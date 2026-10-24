"""Install verified OpenCV Zoo weights; no image or credential is transmitted."""
from pathlib import Path
import argparse,hashlib,json,urllib.request

SHA='4eb496e0a7259d435b49b66faf1754aa45a5c382a34558ddda9a8c6fe5915d77'
CUT='/image_encoder/neck/neck.3/Add_1_output_0'
URL='https://huggingface.co/opencv/opencv_zoo/resolve/main/models/image_segmentation_efficientsam/image_segmentation_efficientsam_ti_2025april.onnx'

def install(directory):
    from onnx.utils import extract_model
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    source=directory/'efficient-sam-ti.onnx'
    if not source.exists():urllib.request.urlretrieve(URL,source)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=SHA:raise ValueError('MODEL_HASH_MISMATCH')
    encoder=directory/'efficient-sam-encoder.onnx';decoder=directory/'efficient-sam-decoder.onnx'
    extract_model(str(source),str(encoder),['batched_images'],[CUT])
    extract_model(str(source),str(decoder),[CUT,'batched_point_coords','batched_point_labels'],['output_masks','iou_predictions'])
    manifest={'source_url':URL,'source_sha256':SHA,'license':'Apache-2.0','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [encoder,decoder]}}
    (directory/'efficient-sam-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    print('Verified OpenCV EfficientSAM model installed. No photos uploaded.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',default=str(Path(__file__).resolve().parents[1]/'runtime/models'));args=parser.parse_args();install(args.directory)
