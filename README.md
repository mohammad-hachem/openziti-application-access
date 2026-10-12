# OpenZiti: Private Application Access with User and Machine Identities

I implemented and tested OpenZiti to give users access to specific applications without granting a general route into the internal network. The work included the controller, administration console, edge router, application hosting, role-based access, and a provisioning script that generated enrollment JWTs and QR codes for phone clients.

Several details needed attention beyond getting the first connection working: separating administrative access from client access, choosing where the hosting tunneler runs, making role assignments predictable, and getting enrollment onto a phone without awkward file handling.

This repository explains those decisions with fictional names and reconstructed examples. It contains no production identities, enrollment tokens, private keys, internal addresses, or employer configurations.

**Start here:** [Implementation guide](IMPLEMENTATION.md) · [Provisioning script](scripts/create-user.sh) · [Configuration examples](config/)

## Why I chose application access over broad network access

The useful difference was the authorization boundary. A user needed permission to reach an application, not membership in an internal network.

| Question | A traditional routed remote-access VPN | This OpenZiti design |
|---|---|---|
| What does the endpoint receive? | Network routes, with access constrained by VPN/firewall policy | Access to explicitly authorized services |
| What identifies the caller? | Often a user/device login associated with a tunnel or assigned IP | An enrolled identity evaluated against service policies |
| What becomes reachable? | Whatever the routes and network rules permit | The configured application address, protocol, and port |
| How is the application reached? | Through a routed network path | Through the overlay to an authorized hosting identity |
| What changes for a new application? | Routes and firewall rules may need updating | Define the service, hosting configuration, and access policies |

A VPN can also use certificates, MFA, device controls, and restrictive firewall rules. The distinction here is the application-oriented design, not a claim that every VPN grants unrestricted access.

OpenZiti supports broad interception too. **The narrow access boundary comes from configuring specific services and policies.** This example does not advertise a subnet or a general-purpose forwarding service. A client tunneler may install local interception routes, but these do not grant general routed access to the application's internal network.

An enrolled identity proves possession of its credentials. Stronger claims about the human or device require the relevant authentication, MFA, external identity provider, or posture policy. Application login and authorization remain in place.

## What I deployed and adjusted

- I used a combined test host for controller, console, and router components.
- I separated the administrative portal from the client-facing port and worked on management API separation.
- I hosted an application through a tunneler on its server, connecting to the local application listener.
- I used role attributes and policies to control application access.
- My Bash provisioning workflow created identities and enrollment JWTs, generated QR images, and delivered enrollment material to users.
- While extending role-to-application discovery, I encountered service IDs appearing where readable names were expected and an application missing from the generated list.

The guide explains the legacy-system alternative: a hosting tunneler or router-hosted tunneling function can connect to an application that cannot run an agent. That changes the final network segment and its security boundary.

## Components and terminology

| Component | Responsibility |
|---|---|
| Controller | Identities, enrollment, authentication, policies, and control-plane coordination |
| Ziti Administration Console (ZAC), called “manager” here | Administrative web UI using controller management APIs |
| Edge router | Carries overlay connections between authorized endpoints |
| Client tunneler | Intercepts configured application traffic on the user's device |
| Hosting tunneler | Binds an authorized service and connects to its backend application |

The manager is not a separate controller role. ZAC can be served by the controller or deployed separately. For production, separate controller/control-plane duties from exposed router/data-plane duties, restrict the administrative interface, and design availability explicitly. Hosting the console on a different VM is optional; a different VM or port alone does not protect the management API.

## Application-hosted and legacy access

```mermaid
flowchart TB
    C["Enrolled user or device"]
    E["Edge router"]
    T["Hosting tunneler on application server"]
    A["Local application listener"]
    G["Legacy gateway hosting identity"]
    L["Legacy application"]
    C -->|"Authorized service"| E
    E <-->|"Overlay connection"| T
    T -->|"Loopback connection"| A
    E <-->|"Alternative hosting path"| G
    G -->|"Restricted backend connection"| L
```

The paths are alternatives for a service. The legacy gateway can be a separate host or a function on the router machine. The diagram shows logical roles, not the original deployment.

## Files

- [IMPLEMENTATION.md](IMPLEMENTATION.md): listeners, router setup, services, policies, enrollment, troubleshooting, and production considerations.
- [config/controller-listeners.yml](config/controller-listeners.yml): partial controller example separating client APIs from management.
- [config/router-listeners.yml](config/router-listeners.yml): partial router example for edge connectivity and optional service hosting.
- [config/portal-intercept.json](config/portal-intercept.json): one client-visible application.
- [config/portal-host.json](config/portal-host.json): application-hosted backend.
- [config/portal-host-legacy.json](config/portal-host-legacy.json): alternative gateway backend.
- [scripts/create-user.sh](scripts/create-user.sh): recreated role-scoped identity and QR provisioning, dry-run by default.

The implementation history comes from the 1.6.x era. These files illustrate the configuration decisions; start with configuration generated for your supported release and merge the relevant sections. They are not a complete PKI bootstrap or an HA deployment. The public script is a reconstruction, not the original private script.
