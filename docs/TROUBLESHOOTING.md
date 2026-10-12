# What required investigation during implementation

These are the implementation issues I encountered. They are presented with fictional application labels and without production logs. Where an observation established only one layer of the connection, I keep that boundary explicit.

## 1. Management and user access shared a listener

**Observation:** the initial arrangement exposed client access, management functions, and the console through shared listener configuration.

**Change:** I worked through separate client, management, and console ports. My test arrangement used 1280, 1281, and 8443 respectively.

**Result:** the test configuration separated those listeners. A port split alone does not establish that firewall restrictions were verified from every external network.

**Lesson:** inspect API bindings as well as the portal. See [the before/after access model](OPERATIONS.md#administrative-exposure-what-changed). The published listener example intentionally follows the current ZAC layout with the management API on its restricted listener.

## 2. A controller FQDN change did not take effect everywhere

**Observation:** changing the name used to reach the controller was insufficient while the advertised address still reflected the old value.

**Change:** I corrected `ZITI_CTRL_ADVERTISED_ADDRESS` in the package bootstrap environment.

**Result:** the FQDN change then worked in my test.

**Lesson:** there are several consumers of an address: bootstrap settings, generated configuration, certificates, client discovery, and enrollment material. Check the configuration the running service actually uses. Do not assume a browser URL change updates them all.

## 3. A router enrollment/token problem cleared after restart

**Observation:** I encountered a router token/enrollment-related issue during setup.

**Change and observed result:** restarting the router cleared that occurrence.

**Limit:** that observation does not establish one universal root cause. Restarting is not the first response to every enrollment failure.

**Diagnostic sequence for another occurrence:** capture logs, inspect time and token validity, verify controller reachability and TLS, compare loaded configuration with the intended configuration, then use a controlled restart if appropriate.

## 4. An application reported NO_EDGE_ROUTERS_AVAILABLE

**Observation:** while adding another HTTPS application, the host tunneler loaded the service but initially reported `NO_EDGE_ROUTERS_AVAILABLE`. Time was also corrected during that troubleshooting.

**Later observation:** the application had an active terminator, alongside existing applications whose terminators remained present.

**Limit:** the available record does not isolate time correction as the sole cause of recovery, and a terminator does not establish successful browser login.

**Lesson:** distinguish an identity loading, a service being authorized, a usable router path, and the backend application responding. Inspect identity-router and service-router policies together with Dial/Bind policies, router availability, and advertised addresses.

## 5. Local application hosting changed the firewall requirement

**Observation:** the application-host tunneler connected to the local application listener at `127.0.0.1:8443`. Policy-advisor checks showed Bind permission and a common online router; a hosting terminator appeared.

**Result:** the hosting arrangement did not require an incoming router-to-application connection to that application port.

**Lesson:** `localhost` is relative to the hosting process. Move that process onto a gateway and the same address points at the gateway. The legacy backend then needs an explicit network destination and a restricted final hop.

## 6. Enrollment email arrived, but an application name did not resolve

**Observation:** after fixing the script's email workflow, I confirmed receipt of the JWT and QR attachments. A subsequent laptop had enrolled its identity, but an application name did not resolve and links did not open.

**Limit:** I do not have a recorded final fix for that client-specific issue to include here.

**Investigation path:** verify service visibility and effective Dial permissions, exact intercept hostname and port, client tunneler state, DNS interception, and competing VPN/DNS settings. Only then investigate the overlay and backend connection.

For Linux clients, use the installed tunneler's diagnostics and `resolvectl status` where systemd-resolved is used. On Windows, inspect the client's service list and resolver configuration. Compare with another enrolled test identity; do not publish internal diagnostic dumps.

## 7. Provisioning output used service IDs and missed an application

**Observation:** dynamic service discovery displayed IDs instead of friendly names and did not include every expected application.

**Change in the approach:** resolve direct references and attribute selectors rather than treating all selectors as names. The public version uses a reviewed static catalog while explaining the requirements for dynamic discovery.

**Limit:** the catalog avoids that parsing dependency; it is not presented as proof that the original dynamic implementation was fully corrected.

## 8. Events contained identity IDs

**Observation:** controller connection events were written successfully and contained source identity IDs.

**Lesson:** retain stable IDs and enrich them with inventory names. A connection event is not proof of access to a particular application or action inside it. Use circuit/service records and application logs for those questions.

See [event logging and identity correlation](OPERATIONS.md#event-logging-and-readable-identities).

## A repeatable diagnostic order

1. Controller and router health, time, and advertised endpoints.
2. Enrollment and identity authentication.
3. Service visibility and effective policy.
4. Client interception and hostname resolution.
5. Hosting terminator and usable router path.
6. Backend TCP/TLS connection.
7. Application authentication and behavior.

This order keeps an application error from being confused with enrollment, and a registered hosting endpoint from being confused with successful user access.

