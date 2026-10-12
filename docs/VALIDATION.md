# Evidence and validation

## Observations from my implementation

| Observation | What it established |
|---|---|
| Controller FQDN worked after the bootstrap advertised address was corrected | That advertised-address correction resolved the observed FQDN issue |
| Policy advisor showed Bind permission and a common online router for a hosting identity | Policy/path prerequisites were satisfied at that checkpoint |
| Multiple application terminators appeared, including a newly added service | Hosting registrations existed for multiple applications |
| Enrollment email arrived with JWT/QR attachments | The tested message and its attachments reached the recipient |
| A laptop held an enrolled identity but an application name did not resolve | Enrollment success and application access could diverge |
| Controller connection events were written with identity IDs | Connection event logging worked |
| A router issue cleared after restart | Recovery occurred in that instance, without proving the underlying cause |

The setup also used persistent tunneler service configuration and role-based provisioning. No reboot/recovery result or complete negative-access test record is asserted here.

## Acceptance worksheet for a deployment

Record date, component versions, identity, service, expected outcome, actual outcome, and sanitized evidence for each check. The rows below are required checks to perform, not claimed results from my original deployment.

| Test | Expected result | Evidence to record |
|---|---|---|
| Valid enrollment for the intended device | Identity enrolled | Client identity state; token omitted |
| Consumed/expired enrollment token | Cannot create an unauthorized additional enrollment | Controlled client result |
| User with portal-users opens portal | Application reachable and its own login works | Client and application result |
| Same user opens reports without reports-users | Access denied through this overlay | Effective policies and fresh attempt |
| User attempts unrelated backend port/address | No access through the configured service | Client result; rule out another VPN/direct path |
| Hosting identity attempts unauthorized Dial | No grant unless separately intended | Effective policy and fresh attempt |
| Ordinary client attempts management API or ZAC | No administrative route exposed | Endpoint/response source verification |
| Hosting process restarted | Terminator and service recover | Logs and fresh application access |
| Host rebooted in a maintenance window | Service starts and access recovers | Service status and end-to-end check |
| Identity disabled or roles removed | New unauthorized access fails | Fresh connection and observed existing-session behavior |
| Router unavailable | Expected failure or alternate path according to topology | Client result and router state |
| Legacy hosting path | Only intended gateway-to-backend port permitted | Firewall review and backend test |
| Enrollment delivery | Intended recipient receives usable material | Delivery confirmation without token contents |

Use test accounts and isolated service changes. A negative test is meaningful only if broad pre-existing grants and alternate network paths are understood.

## Public example verification

The repository's script tests use fake CLI and QR executables and synthetic tokens. They verify input handling, role mapping, duplicate protection, bundle permissions, email attachment construction, and failures. They do not contact a controller, send email, or prove deployment compatibility.

JSON/YAML parsing and shell syntax checks establish file structure only. Apply version-matched configuration in a lab and complete the worksheet before promoting changes.

