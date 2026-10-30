"""Makes a refused update fail visibly, without touching the VM.

Refused updates:
- a user's update that changes a deployment a parent blueprint manages (label
  csys-component=true). The parent's next update would undo it. An update the
  parent starts (it runs while the parent's own update runs) is allowed, and so
  is a user's update that doesn't change the VM: it repairs a deployment left
  in "failed update" (the parent can't heal it while an app is deployed on it);
- in a standalone deployment, a disk that would shrink (the Endpoint refuses).

The VM's own check_drift (vm_check_drift.py) leaves the VM alone in these cases.
This node makes the reason visible: its check_drift reports it as drift, so its
update operation runs and fails with the reason. With "Run automatic reinstall"
this node is reinstalled instead, and its create fails with the same reason.
Either way the update fails and nothing else changes. Updates a parent starts
never fail here: the parent would otherwise reinstall the whole VM deployment.

The same script runs as check_drift, update and create (ctx.operation.name).
"""
import json
import re

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.manager import get_rest_client
from dell.state import ctx_parameters as inputs

ACTIVE = ("pending", "queued", "started", "scheduled")
UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}


def to_bytes(size, unit=None):
    if isinstance(size, int) and not unit:
        return size
    if unit:
        size = f"{size}{unit}"
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]B)\s*", str(size or "").upper())
    return int(float(match.group(1)) * UNITS[match.group(2)]) if match else None


def disk_sizes(disks):
    return {d.get("name"): (d["storage"] if "storage_unit" not in d and isinstance(d.get("storage"), int)
                            else to_bytes(d.get("storage"), d.get("storage_unit") or "GB"))
            for d in disks or [] if isinstance(d, dict)}


def updating(client, deployment_id):
    return any(e.get("workflow_id") == "update" and e.get("status") in ACTIVE
               for e in client.executions.list(deployment_id=deployment_id,
                                                _include=["workflow_id", "status"]))


def vm_would_change(client):
    """Would this update change the VM? Compares the vm node's properties
    (already evaluated with the update's inputs) with the config the edge-plugin
    last applied, the same way the VM's own check_drift does."""
    try:
        path = ctx.download_resource("vm/scripts/vm_check_drift.py")
        check = {"__name__": "vm_check_drift"}
        exec(compile(open(path).read(), path, "exec"), check)
        node = client.nodes.get(ctx.deployment.id, "vm", evaluate_functions=True)
        vms = client.node_instances.list(deployment_id=ctx.deployment.id, node_id="vm")
        applied = (vms[0].runtime_properties or {}).get("expected_configuration") if vms else None
        if not applied:
            return True
        return check["canonical"](node.properties["vm_config"]) != check["canonical"](applied)
    except Exception as err:  # can't tell: treat it as a change
        ctx.logger.warning(f"update guard: could not compare the VM config ({err})")
        return True


def shrinks(client):
    """Disks the requested sizes would make smaller than the VM's."""
    vms = client.node_instances.list(deployment_id=ctx.deployment.id, node_id="vm")
    applied = ((vms[0].runtime_properties or {}).get("expected_configuration") or {}) if vms else {}
    if not applied:
        return []
    found = []
    new = to_bytes(inputs.get("storage"))
    old = to_bytes((applied.get("resource_constraints") or {}).get("storage"))
    if new and old and new < old:
        found.append(f"OS disk {old // 2**30}GB -> {new // 2**30}GB")
    old_disks, new_disks = disk_sizes(applied.get("additional_disks")), disk_sizes(inputs.get("additional_disks"))
    for name, size in new_disks.items():
        if old_disks.get(name) and size and size < old_disks[name]:
            found.append(f"disk {name} {old_disks[name] // 2**30}GB -> {size // 2**30}GB")
    return found


def problem():
    """Why this update must be refused, or None."""
    client = get_rest_client()
    if not updating(client, ctx.deployment.id):
        return None  # install, or the check_drift workflow
    deployment = client.deployments.get(ctx.deployment.id, _include=["id", "labels"])
    labels = [(l.get("key"), str(l.get("value"))) for l in deployment.labels or []]
    parents = [v for k, v in labels if k == "csys-obj-parent"]
    if ("csys-component", "true") in [(k, v.lower()) for k, v in labels]:
        if any(updating(client, p) for p in parents):
            return None  # started by the parent: never fail it
        if not vm_would_change(client):
            return None  # changes nothing on the VM: a repair (or the parent's value back)
        return (f"This VM is managed by the parent deployment {', '.join(parents) or '(unknown)'}. "
                "Update the parent deployment instead: a change made here directly is undone "
                "by the parent's next update. Nothing was changed.")
    refused = shrinks(client)
    if refused:
        return ("Disks can only grow (the Endpoint refuses to shrink them): " + "; ".join(refused)
                + ". Nothing was changed; update again with sizes at least as large as now.")
    return None


def main():
    op = ctx.operation.name.split(".")[-1]
    try:
        reason = problem()
    except Exception as err:  # API not reachable: don't block the update
        ctx.logger.warning(f"update guard: could not check this update ({err})")
        reason = None
    if op == "check_drift":
        if reason:
            ctx.logger.warning(f"update guard: {reason}")
            ctx.returns({"resource_id": "update_guard", "diff_count": 1, "diff": reason})
        else:
            ctx.returns(None)
    elif reason:
        raise NonRecoverableError(reason)
    else:
        ctx.logger.info(f"update guard: {op}: nothing to refuse")


main()
