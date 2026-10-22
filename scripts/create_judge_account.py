"""Offline operator command: create a restricted password-only judge.

Stop the server first: AuthStore startup intentionally revokes existing sessions.
Never print the invitation, password or TOTP secret into command logs.
"""
from pathlib import Path
import argparse
import os
import sys
import re
from datetime import datetime,timezone
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
sys.path.insert(0,str(ROOT/'bind-zero-x/code'))
from auth_security import AuthStore


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username',default='judge')
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument('--base-url',default='http://127.0.0.1:8765')
    action=parser.add_mutually_exclusive_group()
    action.add_argument('--revoke',action='store_true',help='Revoke this judge and all of their device sessions')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{2,31}',args.username) or args.username=='operator':raise SystemExit('Invalid judge username.')
    url=urlsplit(args.base_url)
    if url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise SystemExit('A plain local HTTPS base URL is required.')
    import ipaddress
    try:ip=ipaddress.ip_address(url.hostname)
    except ValueError:raise SystemExit('Use the actual loopback or private Wi-Fi IP.')
    if ip.version!=4 or ip.is_unspecified or ip.is_multicast or ip.is_link_local or not ip.is_private or (url.scheme!='https' and not (url.scheme=='http' and ip.is_loopback)):
        raise SystemExit('Use loopback HTTP or private-network HTTPS.')
    directory=Path(os.environ.get('BZX_DATA_DIR',ROOT/'runtime'))/'security'
    target=directory/(args.username+'-login.txt')
    if target.exists() and not args.revoke:raise SystemExit('Login file already exists; inspect it locally.')
    auth=AuthStore(directory)
    if args.revoke:
        auth.revoke_judge(args.username);print('Judge revoked:',args.username);return
    password=auth.create_password_judge(args.username,args.days)
    created=datetime.fromtimestamp(auth.clock(),timezone.utc).isoformat()
    expires=datetime.fromtimestamp(auth.judge_status(args.username)['expires'],timezone.utc).isoformat()
    text=f'''BIND ZERO-X / 審査員用アカウント
Username: {args.username}
Login URL: {args.base_url.rstrip('/')}{'/judge' if args.username=='judge' else '/'}
Password: {password}
このPC用URL: http://localhost:8765{'/judge' if args.username=='judge' else '/'}

1. ログインURLを、管理者と別のブラウザプロファイルで開いてください。
2. judge専用ページでは上記のパスワードだけでログインできます。
   他のユーザー名の場合はUsername欄も入力してください。
3. QR登録や認証アプリのコードは不要です。

権限: デモ写真、色分け、パッキング案内、自分の合成観測セッション。
非公開の管理者画像・履歴・証拠・実物キャプチャにはアクセスできません。
アカウント有効期限（UTC）: {expires}
ログインセッション: 最大1時間、15分間操作がない場合も失効します。
Wi-Fiは同じ私設ネットワークでHTTPS証明書を信頼済みの端末から接続してください。
localhostのURLはこのPC専用です。Wi-Fiでは上記のHTTPSアドレスを使用します。
発行UTC: {created}

このテキストは審査員本人へ直接渡してください。公開GitHubへ掲載しないでください。
'''
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(text)
    legacy=directory/(args.username+'-invitation.txt')
    if legacy.exists() and legacy.resolve().parent==directory.resolve():legacy.unlink()
    print('Password-only judge created. Private text file:',target)


if __name__=='__main__':main()
