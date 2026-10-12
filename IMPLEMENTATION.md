# Implementation guide

## 1. Establish the components and addresses

My testing combined controller, router, and console components on one machine. That made initial setup convenient. The production design needs independent availability and administrative boundaries: separate the controller from exposed routers, keep management access restricted, and add redundant components according to the supported release.

ZAC is the administration UI, not a replacement for the controller. A separate ZAC host still calls controller management APIs. Protect both.

Use supported packages from the [official deployment documentation](https://netfoundry.io/docs/openziti/how-to-guides/deployments/). Record controller, router, CLI, and desktop/mobile client versions. Generate the base configurations and PKI using the matching release's installation procedure. Do not use this repository to overwrite a working controller's database, identity, enrollment signer, or cluster settings.

Example names and ports:

| Function | Example address | Permitted reachability |
|---|---|---|
| Client API | ziti.example.com:1280 | Enrolling and enrolled clients |
| Router control channel | ctrl.internal.example.com:6262 | Routers and required controller peers |
| ZAC and management APIs | admin.example.com:8443 | Administrative network only |
| Edge client listener | router.example.com:3022 | Authorized endpoints must be able to connect |
| Router mesh listener, if used | router.example.com:10080 | Required peer routers |
| Private application | portal.internal.example.com:443 | Intercepted service on clients |
| Local backend | 127.0.0.1:8443 | Hosting tunneler on the application server |

Ports are examples, not a universal OpenZiti port list. A single-router lab does not need an exposed mesh listener. DNS, outbound dependencies, NAT, certificates, and advertised endpoints must match the chosen topology.

## 2. The admin-port change that mattered

During testing I found management, client access, and the console sharing the initial listener. I worked on separating the client port, management API port, and console port. The test configuration used 1280 for client access, 1281 for management, and 8443 for the console.

The durable lesson is to separate *administrative APIs*, not only the HTML portal. Leaving `edge-management` or `fabric` on the public client listener defeats that boundary.

The public example in [controller-listeners.yml](config/controller-listeners.yml) uses a simpler layout: client API on 1280, and ZAC plus management APIs together on a restricted 8443 listener. This follows the current console deployment guidance requiring its binding alongside the management API. It is an adaptation of the test arrangement, not a verbatim production configuration.

Merge the sections into generated configuration, replacing the old `web` list so that administrative bindings are not accidentally retained on another public listener. Keep any additional authentication endpoints required by your version and auth method, such as its OIDC listener, reachable by their intended clients.

Bind management to a real private interface and restrict its firewall. If a reverse proxy is used, inspect every route it publishes; a public catch-all can expose a private backend's management API again.

Validate from two places:

- From an ordinary client network, the client API works while management API paths and the console are inaccessible.
- From the administrator network, ZAC loads and authenticates against the intended management API.

For an API path exposed on the public listener, a `401` or `403` still shows that the API is reachable. Authentication protection is different from removing the public route. Confirm the response comes from the intended service rather than a proxy or SPA fallback.

Reference: [Controller configuration](https://netfoundry.io/docs/openziti/reference/configuration/controller/) and [console binding requirements](https://netfoundry.io/docs/openziti/how-to-guides/deployments/docker/console/).

## 3. Advertised names and certificate trust

Changing the name used in the browser did not by itself fix the advertised controller address in my test. I corrected the bootstrap advertised-address setting.

For a new deployment, check the generated configuration and its bootstrap environment together. In the package setup I used, the relevant variable was `ZITI_CTRL_ADVERTISED_ADDRESS`. Package paths and regeneration behavior differ across versions; inspect the installed service definition to locate the configuration it actually runs.

The client API address, advertised router address, DNS resolution, certificate SANs, and enrollment endpoint must agree. Editing an environment file does not necessarily update already generated configuration, certificates, or previously issued enrollment material. Inspect each artifact and issue fresh enrollment material where necessary.

Use trusted TLS certificates and verify CA fingerprints through a trusted channel when establishing CLI trust. Avoid making certificate-verification bypasses part of the procedure.

## 4. Register and configure the router

From an authenticated administrator CLI session on the management network:

```bash
ziti edge login https://admin.example.com:8443

# This example enables optional router-hosted tunneling.
umask 077
ziti edge create edge-router edge-router-01 \
  --role-attributes app-routers \
  --tunneler-enabled \
  --jwt-output-file edge-router-01.jwt
```

Keep the enrollment JWT private. Generate a router configuration using the installed release's supported tool, then merge the address/listener choices from [router-listeners.yml](config/router-listeners.yml). Preserve its generated identity paths, CSR configuration, and other required sections.

On the router host, enroll against that configuration:

```bash
ziti router enroll /etc/ziti/router.yml --jwt /secure-staging/edge-router-01.jwt
```

The example path must be replaced with the actual service configuration path. Start the installed router service after enrollment. Verify it is online in the controller and that its advertised edge address is reachable from both client and hosting environments.

Router tunneling requires both the administrative tunneler setting and the tunnel listener configuration. If using only separate hosting tunnelers, omit the optional tunnel listener and register a router without that feature.

References: [Router registration](https://netfoundry.io/docs/openziti/how-to-guides/deployments/linux/router/cli-mgmt/) and [router configuration](https://netfoundry.io/docs/openziti/reference/configuration/router/).

## 5. Put the hosting identity close to the application

For an application server that supports a tunneler, run it there. In my testing, the hosting process connected to the application's loopback listener. The application did not need an inbound connection from the edge router to its application port; the hosting tunneler established overlay connectivity outward.

Create and enroll a dedicated hosting identity:

```bash
umask 077
ziti edge create identity portal-host-01 \
  --role-attributes portal-hosts \
  --jwt-output-file portal-host-01.jwt
```

Transfer the JWT through an approved channel. On the application server:

```bash
ziti-edge-tunnel enroll \
  --jwt /secure-staging/portal-host-01.jwt \
  --identity /etc/ziti/identities/portal-host-01.json

ziti-edge-tunnel run-host \
  --identity /etc/ziti/identities/portal-host-01.json
```

The last command demonstrates host-only operation in the foreground. Use the supported service packaging for persistent operation, with a service account that can read its identity and no broader privileges than required.

The hosting identity JSON contains private credential material. It is not a file to reuse across users or publish.

### Legacy application alternative

If the application cannot run a tunneler, host the service on a supported gateway. That gateway can be the router machine, using either:

- A separate `ziti-edge-tunnel` process with its own hosting identity; or
- The router's built-in tunnel binding in `host` mode, with Bind authorization assigned to the router's tunneler identity.

These are alternatives; do not configure both unintentionally for the same backend.

In gateway mode, use the application's actual backend address, such as [portal-host-legacy.json](config/portal-host-legacy.json). `127.0.0.1` would refer to the gateway itself, not the remote application.

Restrict gateway-to-application traffic to the exact backend port. The overlay terminates at the gateway, so protect the final network segment with appropriate application TLS and firewall rules. Keep the original application inaccessible through unintended direct paths.

Reference: [Service hosting and intercept configuration](https://netfoundry.io/docs/openziti/get-started/services/).

## 6. Create one narrowly scoped application service

Run these commands from the repository root after administrator login. They create new named objects; inspect existing objects before rerunning.

```bash
ziti edge create config portal-intercept intercept.v1 \
  "$(cat config/portal-intercept.json)"

ziti edge create config portal-host host.v1 \
  "$(cat config/portal-host.json)"

ziti edge create service portal \
  --configs portal-intercept,portal-host \
  --role-attributes private-apps
```

Choose the legacy host JSON instead when using a gateway; do not attach both backend configurations.

The client intercept is only `portal.internal.example.com:443/TCP`. The hosting configuration forwards to one fixed backend. There is no CIDR interception, wildcard destination, or arbitrary port-forwarding range.

Keep the application certificate valid for the hostname the user opens. A TCP tunnel does not repair certificate-name mismatches, rewrite application redirects, or fix an application that redirects to a different internal name.

## 7. Roles are selectors, policies grant access

My provisioning workflow assigned application-specific roles to identities. In OpenZiti these are role attributes used by policies. They are not automatically controller administrator privileges or application-level permissions.

This example uses:

| Object | Attribute | Intended purpose |
|---|---|---|
| User/device identity | portal-users | Dial the portal |
| Application-host identity | portal-hosts | Bind the portal |
| Router | app-routers | Carry the selected application services |
| Service | private-apps | Select services for the router policy |

Create the policies:

```bash
ziti edge create service-policy portal-dial Dial \
  --identity-roles '#portal-users' \
  --service-roles '@portal' \
  --semantic AnyOf

ziti edge create service-policy portal-bind Bind \
  --identity-roles '#portal-hosts' \
  --service-roles '@portal' \
  --semantic AnyOf

ziti edge create edge-router-policy portal-router-access \
  --identity-roles '#portal-users,#portal-hosts' \
  --edge-router-roles '#app-routers' \
  --semantic AnyOf

ziti edge create service-edge-router-policy private-app-router-access \
  --service-roles '#private-apps' \
  --edge-router-roles '#app-routers' \
  --semantic AnyOf
```

For built-in router hosting, assign `portal-hosts` to the router's *tunneler identity*, not merely to the router object's attributes. Inspect and preserve existing identity attributes when updating them.

`#attribute` selects matching attributes; `@name-or-id` targets an object. `AnyOf` matches at least one listed selector; `AllOf` requires all applicable selectors. Dial permits connection; Bind permits hosting. Router policies determine eligible paths.

Review pre-existing broad policies, especially quickstart `#all` grants. A narrow new policy does not cancel a broader grant. Do not delete unrelated policies blindly.

Reference: [OpenZiti policies](https://netfoundry.io/docs/openziti/active/learn/core-concepts/security/authorization/policies/overview/).

## 8. Create users and make phone enrollment easier

My Bash workflow generated an identity, its enrollment JWT, and a QR image. The JWT and image were sent to users, giving phone users another way to import enrollment material.

The recreated [create-user.sh](scripts/create-user.sh) accepts an identity name and approved application role, then creates a private enrollment bundle. It defaults to dry-run:

```bash
bash scripts/create-user.sh alex-phone portal-users
bash scripts/create-user.sh alex-phone portal-users --apply
```

Authenticate the CLI against the intended management endpoint first. The script does not log in, send email, grant controller-admin status, or enroll the user's identity on the administrator's machine. Delivery remains a separate approved step.

Its QR contains the enrollment JWT itself:

```bash
qrencode -r identity.jwt -o enrollment.png
```

The QR is another representation of the same enrollment credential, not a second factor. Anyone obtaining unused enrollment material may be able to enroll that identity before the intended user. Keep it out of repositories, screenshots, public download directories, and logs.

On a phone, use the OpenZiti client application's supported enrollment/import flow. QR import support and accepted payload format depend on the client/version; retain JWT file import as the fallback. A normal phone camera need not understand a raw JWT. When the image is on the same phone, use the client's supported image/file import or display the QR on another trusted screen.

Use a separate identity for each device. After enrollment, the client holds its own identity credentials; the one-time enrollment JWT is not the credential used for each application connection. Expired or consumed enrollment material must be replaced through the supported enrollment process.

References: [Creating identities](https://netfoundry.io/docs/openziti/learn/core-concepts/identities/creating/), [enrollment](https://netfoundry.io/docs/openziti/learn/core-concepts/security/enrollment/), and [client enrollment](https://netfoundry.io/docs/openziti/learn/core-concepts/identities/enrolling/).

## 9. The role-discovery problem I encountered

My initial script contained explicit role-to-application mappings. When I extended discovery, the output showed service IDs where names were expected and omitted an application.

The practical lesson is that selectors are not display names. A policy can reference a service directly by ID or select a group through attributes. Producing a readable application list requires resolving both forms and handling selector semantics.

A robust discovery implementation must also handle pagination, multiple policies, disabled identities, posture requirements, and the actual effective grants. A service-edge-router policy chooses eligible routers; it does not by itself grant a user Dial access.

The public script deliberately uses an explicit allowlist for provisioning. Its printed application link is a configured convenience, not proof of effective authorization. Confirm access with policy inspection and a real client test.

## 10. Checks that helped during testing

I used the policy advisor to check hosting permissions and common router availability. I also verified that a hosting terminator appeared. An online router alone was not the whole service path.

```bash
ziti edge list identities
ziti edge list edge-routers
ziti edge list services
ziti edge list terminators
ziti edge policy-advisor services
```

For troubleshooting, work through the layers:

| Symptom | Check |
|---|---|
| Enrollment fails | JWT validity, advertised client endpoint, DNS, time, TLS trust |
| Identity enrolled but service absent | Dial policy selectors, other grants, posture requirements |
| Service visible but connection fails | Bind policy, terminator, common reachable router |
| Gateway cannot connect to backend | Actual backend address, firewall, TLS, application listener |
| Portal loads but authentication fails | Console-to-management API URL, allowed origin/proxy behavior, credentials |
| Service list contains IDs or misses an app | ID/name resolution, attribute selectors, pagination |
| User reaches unrelated apps | Broad policies, intercept scope, other network paths |

I also enabled controller event logging and observed connection events containing identity IDs. Friendly-name reporting needs enrichment from the identity inventory; an ID in an event is not automatically a human-readable username.

For a new rollout, include negative tests: a user without the role cannot access the service; an authorized user cannot access an unrelated service or backend port; ordinary clients cannot reach the management endpoints. Test policy removal using new connections and observe existing-session behavior rather than assuming immediate termination.

## 11. Moving beyond the combined test host

- Separate the controller from router/data-plane exposure and protect administrative access.
- Use redundant routers and a supported controller availability design; splitting VMs alone does not provide HA.
- Back up controller state and PKI with a restore procedure.
- Monitor certificate expiry, enrollment failures, router health, and service availability.
- Treat role changes as access changes with review and offboarding.
- Retain application authentication, authorization, and TLS.
- Protect JWT delivery and retire temporary enrollment artifacts after the intended process.
- Keep a recovery path for management access that does not depend solely on the service being repaired.

The implementation gave me application-specific access and a repeatable enrollment workflow. The details that made it usable were listener separation, correct advertised addresses, an appropriate hosting location, understandable roles, and phone-friendly enrollment.
