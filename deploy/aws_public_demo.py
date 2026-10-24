"""Public notice only. The account-pinned AWS controller is private.

The operator keeps the executable controller in runtime/security/. It retains
its original fixed-account check. The public source has no AWS mutation entry
point and contains no account-specific infrastructure identifiers.
See docs/aws-public-demo.md and the operator's private deployment handover.
"""

if __name__ == '__main__':
    raise SystemExit('AWS controller is private. Use the approved operator handover; this public entry performs no AWS action.')
