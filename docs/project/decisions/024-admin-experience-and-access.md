# 024 — Coverage-led Admin with owner and approved viewers

Date: 2026-10-08. Status: Accepted product scope; concrete implementation defaults selected under delegated authority. Not implemented.

Acceptance source: the user accepted the coverage-led recommendation, requested visual workflow guidance, their own superadmin account, owner-approved read-only requests with name/email/message and a public Admin link, then asked for detailed planning while delegating most choices.

Build M6 as a separate Admin bundle on the existing API, with Coverage, Jobs, Publications, How it works and owner-only Access. Use two human roles, email-link sign-in and server-side sessions; bootstrap the owner out of band. Viewer grants default to 30 days and expose only explicitly safe operational projections. Keep bearer automation isolated from account administration. Reuse existing import jobs, add recoverable load-operation metadata, and require an explicit owner action for v2 detection/publication. Explain Highlights separately from detectors.

The [specification](../features/admin.md) owns detailed defaults, permission matrix, lifecycle, limits and acceptance. [NEM-095–107](../backlog.md#nem-095) deliver the slices; NEM-093 planning completion does not imply feature delivery.

Alternatives: a shared password/token would lose person-specific revocation/audit; unrestricted read-only GET access would disclose personal and diagnostic information; a new backend or enterprise IAM suite exceeds this project's scope. Email sign-in avoids password storage/recovery but depends on mailbox security and delivery, and is not phishing-resistant MFA. Provider/sender and owner identity are setup inputs; no default credentials or paid-service selection is made.

Supersedes decision 021's UI deferral and decision 023's undecided Admin UI scope. M5 remains locally complete; M6 is planned; M7 owns deployed release validation.

Implementation references checked during planning: [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [single-use token guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), and [CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). These inform controls, not a claim of certification.
