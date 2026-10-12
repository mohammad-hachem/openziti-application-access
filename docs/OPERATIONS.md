# Running the setup after installation

## Administrative exposure: what changed

I separated the console and management access from the client-facing port during testing. The important check was which API bindings remained reachable, not just which port opened the login page.

The test layout used client port 1280, management port 1281, and console port 8443. The recorded client listener still included a fabric binding at one checkpoint. That is why the public configuration moves administrative bindings to the restricted listener rather than presenting the intermediate configuration as the final security boundary.

| Public example endpoint | Audience | Binding or purpose |
|---|---|---|
| ziti.example.com:1280 | Enrolling/enrolled clients | edge-client |
| admin.example.com:8443 | Administrators | edge-management, fabric, ZAC |
| ctrl.internal.example.com:6262 | Routers/controller peers as required | Control channel |
| router.example.com:3022 | Clients and hosting endpoints | Edge transport |
| router.example.com:10080 | Router peers, only if needed | Router mesh |

The [controller fragment](../config/controller-listeners.yml) is a refined example. A private bind address, firewall rules and proxy routing implement the restriction. Separate ports on an unrestricted public interface do not.

Keep a documented management recovery path. Hosting the only administration route through the same overlay being repaired can turn a service failure into a lockout.

## Persistent hosting and several identities

I used persistent tunneler configuration with an identity directory as the setup grew. A foreground process is useful for diagnosis; it is not the operational end state.

Prefer the supported package's service. If a custom unit is necessary, [ziti-host.service](../examples/ziti-host.service) illustrates a host-only process loading identities from one directory. Confirm binary location and options with the installed version before adapting it. Do not run it alongside another process loading the same identities.

```bash
# Example Linux preparation; skip account creation if it already exists.
sudo useradd --system --no-create-home --shell /usr/sbin/nologin ziti-host
sudo install -d -m 0700 -o ziti-host -g ziti-host /etc/ziti/identities

# The source is a privately enrolled identity, never a repository file.
sudo install -m 0600 -o ziti-host -g ziti-host \
  /secure-staging/portal-host-01.json /etc/ziti/identities/portal-host-01.json

sudo install -m 0644 examples/ziti-host.service /etc/systemd/system/ziti-host.service
sudo systemctl daemon-reload
sudo systemctl enable --now ziti-host.service
sudo systemctl status ziti-host.service
sudo journalctl -u ziti-host.service --since '10 minutes ago'
```

The service user needs write access where the tunneler updates identity material during credential renewal. Do not make that directory publicly readable to solve a permission error. Host-only operation does not need client DNS interception or a TUN interface.

For another identity, securely enroll it, install its JSON with the same ownership, and restart during an appropriate window. Verify all previously hosted services as well as the new one. A shared process is convenient but a restart affects every identity it loads; separate service instances can provide operational isolation where needed.

A service being `active` is only one check. Confirm the identity authenticates, its service terminator appears, and an authorized client reaches the application after restart. See the [validation worksheet](VALIDATION.md).

Reference: [Linux tunneler options](https://netfoundry.io/docs/openziti/maint/reference/tunnelers/linux/linux-tunnel-options/).

## Event logging and readable identities

I enabled controller event logging and observed connection events with identity IDs. That was useful evidence, but the ID alone was not a readable account name.

The [events fragment](../config/controller-events.yml) illustrates JSON file logging for connection, circuit, router and terminator events. Merge it with existing subscriptions rather than replacing working audit configuration. Create the log directory with ownership for the actual controller service account; configure rotation and retention, and verify events are still written after rotation. Event schemas and supported subscriptions are version-dependent.

For a small inventory, inspect the CLI response and produce an ID/name lookup:

```bash
ziti edge list identities -j > /secure-staging/identity-inventory.json
jq -r '.data[] | [.id, .name] | @tsv' /secure-staging/identity-inventory.json
```

This listing may be paginated. Fetch all pages before using it as a complete inventory. A production enrichment job should retain stable IDs, refresh renamed/deleted identities, timestamp its mapping and distinguish identity IDs from router/service IDs. Do not replace every field ending in `_id` with an identity name indiscriminately.

For a connection event whose schema defines `src_id` as an identity reference, enrich that value from the identity inventory. Preserve the raw event. Combine it with service/circuit context where available; a controller connection event is not proof that a user completed an application login or transaction.

Useful operational questions include:

- Which device identity connected, and who owns it?
- Which service was requested, through which router and hosting identity?
- Did authorization, path creation or the backend connection fail?
- Did a role, identity or policy change precede the failure?
- Is the application healthy through the intended client path?

This describes how to make events actionable. It does not claim that I completed a SIEM integration or an application-level audit pipeline.

Reference: [Controller event configuration](https://netfoundry.io/docs/openziti/maint/reference/configuration/controller/).

## Identity and service lifecycle

Maintain an inventory linking each device identity to its owner, approved roles and purpose. Keep hosting identities separate from human device identities. Review broad grants and unused identities periodically.

Monitor enrollment failures, certificate expiry/renewal, router availability, terminator changes and application reachability. Use synchronized time and investigate clock drift rather than treating a restart as a universal fix.

Back up controller state and required PKI using the installed release's supported procedure. Encrypt and restrict backups, and rehearse restoration in an isolated environment. Availability requires a supported redundant controller/router design and tested failure behavior; moving components to separate VMs is not HA by itself.

For access removal, disable the identity or remove the appropriate grants, inspect other policies, and test fresh access. Observe existing connections explicitly. Application sessions and the overlay's identity lifecycle are related but not identical.
