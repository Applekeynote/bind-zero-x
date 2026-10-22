"""Create a local Wi-Fi CA/certificate; private keys never enter source releases."""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'bind-zero-x/code')]
from tls_local import create_tls

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--ip',required=True)
    parser.add_argument('--output',default=str(ROOT/'runtime/tls'))
    args=parser.parse_args()
    create_tls(args.output,args.ip)
    print('Local HTTPS certificate created. No OS or phone trust settings were changed.')
    print('Public CA certificate:',Path(args.output)/'ca-cert.cer')
    print('Certificate details:',Path(args.output)/'certificate-info.json')
