# Expanding from one application to several

My deployment grew beyond one service. The public examples use fictional applications, but preserve the distinction between a user's Dial access, an application's Bind identity, and eligible routers.

| Service | Client intercept | Host-only backend on its own server | Dial attribute | Bind attribute |
|---|---|---|---|---|
| portal | portal.internal.example.com:443 | 127.0.0.1:8443 | portal-users | portal-hosts |
| reports | reports.internal.example.com:443 | 127.0.0.1:9443 | reports-users | reports-hosts |
| hosting-console | hosting.internal.example.com:443 | 127.0.0.1:8443 | hosting-users | hosting-hosts |

Loopback refers to the machine running the hosting process. These examples assume a separate application host for each service. For a legacy gateway, use the backend's actual private name/address and restrict the final network hop.

## Configure the two additional services

First follow the [implementation guide](../IMPLEMENTATION.md) for the router and portal. Its `private-app-router-access` service-edge-router policy covers services tagged `private-apps`. The commands below add application configs and explicit per-application grants. Run them only in the intended authenticated CLI context, inspect existing objects first, and use version-matched CLI help.

```bash
# Run from the repository root. Requires jq; commands create objects immediately.
add_application() {
  local name="$1" host="$2" port="$3" users="$4" hosts="$5"
  local intercept backend
  intercept="$(jq -cn --arg address "$host" \
    '{protocols:["tcp"],addresses:[$address],portRanges:[{low:443,high:443}]}')" || return
  backend="$(jq -cn --argjson port "$port" \
    '{protocol:"tcp",address:"127.0.0.1",port:$port}')" || return

  ziti edge create config "$name-intercept" intercept.v1 "$intercept" || return
  ziti edge create config "$name-host" host.v1 "$backend" || return
  ziti edge create service "$name" \
    --configs "$name-intercept,$name-host" --role-attributes private-apps || return
  ziti edge create service-policy "$name-dial" Dial \
    --identity-roles "#$users" --service-roles "@$name" --semantic AnyOf || return
  ziti edge create service-policy "$name-bind" Bind \
    --identity-roles "#$hosts" --service-roles "@$name" --semantic AnyOf || return
  ziti edge create edge-router-policy "$name-router-access" \
    --identity-roles "#$users,#$hosts" --edge-router-roles '#app-routers' \
    --semantic AnyOf
}

add_application reports reports.internal.example.com 9443 reports-users reports-hosts
add_application hosting-console hosting.internal.example.com 8443 hosting-users hosting-hosts
```

These commands are not transactional or idempotent. If one fails, inspect which objects exist and correct the partial configuration before continuing. Do not rerun blindly or delete unrelated objects.

Create a distinct hosting identity with `reports-hosts` or `hosting-hosts`, enroll it on the corresponding application host, and run the hosting service as in the implementation guide. Do not give these Bind roles to ordinary user devices.

The [application catalog](../config/applications.json) drives onboarding links and permitted input role names. Editing it does not create services or policies. Keep the catalog and deployed policy model under the same change review.

## Check the access boundary

Provision a test device with `portal-users,reports-users`. Confirm both applications work and the hosting console does not. Inspect broad pre-existing grants before interpreting a denied-access test. A device with a Bind role should not acquire Dial access unless a separate policy grants it.

Check each application's HTTPS certificate, redirects, external dependencies and login flow. If an application redirects to another hostname or needs another service, model that dependency explicitly instead of widening interception to an entire subnet.

The OpenZiti role selects overlay access. It does not replace the application's account, administrator role or authorization checks.
