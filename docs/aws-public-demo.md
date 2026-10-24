# Isolated public judge environment

The public judge app is a separate AWS deployment in Tokyo. It contains public source/demo assets and a new judge account. Laptop operator credentials, captures, private history and GT data never enter this release.

`deploy/aws_public_demo.py prepare --commit SHA` only reads AWS metadata and saves a CloudFormation template. `deploy --commit SHA --account 510266171733` is a separate, explicitly authorized action. The stack creates an HTTP API, VPC Link, internal ALB, EC2 t3.small, encrypted 12 GiB gp3 root volume, WAF, security groups and a scoped instance role/profile. A private encrypted source bucket and SecureString origin token are prepared by the deployment command. No domain purchase, NAT gateway, SSH key or public inbound instance port is required. EC2's public IPv4 supports outbound package installation and SSM; inbound connections are restricted to the ALB group. The internal ALB accepts only the VPC Link group.

The AWS-managed `execute-api.ap-northeast-1.amazonaws.com` URL supports TLS 1.2/1.3. API Gateway overwrites the origin token, HTTPS context and viewer IP headers. `PublicOrigin` verifies the secret before trusting those headers, fixes the public authority and discards untrusted forwarding headers. Exact-Origin/CSRF checks, Secure/HttpOnly/SameSite cookies, password failure limits and principal isolation remain active. Public mode disables operator login, operator session creation and MFA enrollment entirely. The local operator MFA is unchanged. The health probe returns only fixed readiness metadata.

The judge password is generated on EC2 and stored in `~/.bzx-public/judge-login.txt` (0600) on CloudShell after private retrieval. The deployment helper encrypts the handout with a temporary RSA-4096 public key and OAEP/SHA-256 before returning it through SSM; CloudShell alone holds the private transfer key, which is removed after decryption. A live encrypted retrieval round trip was verified. The initial bootstrap retrieval used base64 in administrator-restricted SSM output; treat that command history as sensitive credential material. The handout is transferred privately to the operator and excluded from Git/ZIPs. Accounts last 30 days, sessions one hour or 15 minutes idle. Judge access is restricted to demos and their own observations.

The API throttles to 2 requests/second with burst 40. WAF includes a viewer-IP rate rule (using the overwritten IP header) and AWS Known Bad Inputs rules. The app retains bounded request/image sizes and two concurrent expensive tasks. A durable byte budget allows 500 MiB/day and 5 GiB over the deployment lifetime; reservations survive restart and exhausted budgets return a small 429 instead of an asset. These reduce abuse/spending and are not an AWS account-wide hard dollar cap.

Estimated 30-day base resources cost USD 45–60 before tax, plus requests/transfer. The task budget is USD 100. A root-owned expiry timer is prepared for 30 days: delete this API, ALB and WAF, remove the origin parameter and terminate its EC2/EBS. Judge-only history on the temporary volume is deleted at expiry. The source object expires after 45 days. Remaining free metadata resources can be removed through the named CloudFormation stack; unrelated resources are out of scope.

The service runs as a non-login user with read-only source/venv, a private runtime directory, NoNewPrivileges/ProtectSystem/ProtectHome, memory/CPU limits, IMDSv2 and standard CPU credits. The instance role provides SSM channels, its exact source object/origin parameter and cleanup actions scoped to its own API/ALB/WAF; it has no administrator policy. Secrets are absent from user data/output and fetched from SecureString into a 0600 file.

Before declaring the URL operational, verify Chrome login, secure cookies, foreign-history denial, segmentation, inferred geometry, supported bundles and continuous twine guidance. A prepared template or created resource alone is not successful deployment.

## Live deployment, 24 October 2026

- URL: https://8cojy59x54.execute-api.ap-northeast-1.amazonaws.com/judge
- Expiry timer verified active: 23 November 2026, 09:31:56 UTC / 18:31:56 JST.
- CloudFormation stack: `bzx-public-7ffd2117`, status `UPDATE_COMPLETE`.
- Bootstrap source: `f93937b04cbdcce3abe61f31a2706e6c63d66aee`. Runtime source revision after SHA-256-verified static patches: `b303e8a1e31e8f46e77ed3735fe21b2cb7dc4fa6`.
- HTTP API header literals were corrected through CloudFormation. HTTP API mappings use raw literal values; extra single quotes would reach the origin as part of the header.
- The live host reports OpenCV 5.0.0, zero operator credential rows, only the active judge account, zero private capture PNGs, a non-root service and a 0600 origin-token file.
- Anonymous API and demo-photo requests return 401. The login response uses HSTS, CSP, Secure cookies and no-store. ALB and app ingress are security-group-to-security-group only.
- Chrome verified five Primary sheets regions, two supported bundles, panel preparation, layer placement, crossed wraps and the continuous surgeon-knot route. Demonstrated actions are simulations, not physical measurements.

Local private operational evidence is saved at `runtime/evidence/aws-public-deployment.json`. The handout is `runtime/security/aws-judge-login.txt`; neither file enters the public source release.

References: [TLS policy](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-ciphers.html), [parameter mapping](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-parameter-mapping.html), [viewer context](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-logging-variables.html), [ALB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).
