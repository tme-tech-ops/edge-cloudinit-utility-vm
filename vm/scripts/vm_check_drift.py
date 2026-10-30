"""check_drift for the VM (replaces the edge-plugin's).

The edge-plugin's check_drift always reports drift, so every deployment update
sends the VM an update even when nothing about the VM changed (for example an
iot_factory setting). The Endpoint sometimes never completes such a no-op
update, and update_apply then polls for up to an hour.

This compares the desired vm_config (the node properties, evaluated with the
update's inputs) with expected_configuration, the config the edge-plugin
stored after the last successful create or update, field by field over
everything the plugin sends in an update. No difference: no drift, and the VM
update is skipped. Any difference, or anything it can't compare: drift, and
the plugin updates the VM as before. Read-only.
"""
import json
import re
from datetime import datetime

from dell import ctx

UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}


def to_bytes(size):
    if isinstance(size, int):
        return size
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]B)\s*", str(size or "").upper())
    return int(float(match.group(1)) * UNITS[match.group(2)]) if match else size


def rule(r):
    """A NAT rule with its values as strings (the plugin stores ports as integers)."""
    return {k: str(v) for k, v in (r or {}).items() if v not in (None, "")}


def disk_bytes(d):
    """Additional disk size in bytes. The plugin stores bytes without a unit;
    the node properties carry storage + storage_unit."""
    if "storage_unit" not in d and isinstance(d.get("storage"), int):
        return d["storage"]
    return to_bytes(f"{d.get('storage')}{str(d.get('storage_unit') or 'GB').upper()}")


def canonical(config):
    """The fields the edge-plugin sends in a VM update, in one comparable form."""
    limits = config.get("resource_constraints") or {}
    ports = config.get("ports") or {}
    return {
        "name": config.get("name"),
        "cpu": limits.get("cpu"),
        "memory": to_bytes(limits.get("memory")),
        "storage": to_bytes(limits.get("storage")),
        "controller": str(limits.get("controller") or "").upper(),
        "disconnect_flag": bool((config.get("main_disk") or {}).get("disconnect_flag")),
        "network_settings": sorted(
            json.dumps({"name": n.get("name"), "segment_name": n.get("segment_name"),
                        "model_type": n.get("model_type") or "VIRTIO",
                        "port_fwd_rules": sorted(json.dumps(rule(r), sort_keys=True)
                                                 for r in n.get("port_fwd_rules") or [])},
                       sort_keys=True)
            for n in config.get("network_settings") or []),
        "ports": {k: sorted(json.dumps(p, sort_keys=True) for p in ports.get(k) or [])
                  for k in ("usb", "serial_port", "gpu", "video", "pcie")},
        "boot_order": list(config.get("boot_order") or []),
        "additional_disks": sorted(
            json.dumps({"name": d.get("name"), "disk": d.get("disk"), "size": disk_bytes(d)},
                       sort_keys=True)
            for d in config.get("additional_disks") or []),
        "custom_parameters": config.get("custom_parameters") or {},
        "advanced_hypervisor_parameters": config.get("advanced_hypervisor_parameters") or {},
    }


def drift(lines):
    ctx.logger.info("vm drift: " + "; ".join(lines))
    ctx.returns({
        "resource_id": "vm_config",
        "diff_count": len(lines),
        "diff": "\n".join(lines),
        "state_drift": None,
        "time": datetime.now().isoformat(timespec="microseconds"),
    })


def shrinks(desired, applied):
    """Disks the update would make smaller (the Endpoint refuses that)."""
    found = []
    if desired["storage"] and applied["storage"] and desired["storage"] < applied["storage"]:
        found.append("OS disk")
    old = {d["name"]: d["size"] for d in map(json.loads, applied["additional_disks"])}
    for d in map(json.loads, desired["additional_disks"]):
        if old.get(d["name"]) and d["size"] and d["size"] < old[d["name"]]:
            found.append(f"disk {d['name']}")
    return found


def direct_update_of_managed_vm():
    """A user's update of a deployment a parent manages (see update_guard.py)."""
    try:
        from dell.manager import get_rest_client
        client = get_rest_client()
        dep = client.deployments.get(ctx.deployment.id, _include=["id", "labels"])
        labels = [(l.get("key"), str(l.get("value"))) for l in dep.labels or []]
        if ("csys-component", "true") not in [(k, v.lower()) for k, v in labels]:
            return False

        def updating(dep_id):
            return any(e.get("workflow_id") == "update"
                       and e.get("status") in ("pending", "queued", "started", "scheduled")
                       for e in client.executions.list(deployment_id=dep_id,
                                                        _include=["workflow_id", "status"]))
        if not updating(ctx.deployment.id):
            return False
        return not any(updating(v) for k, v in labels if k == "csys-obj-parent")
    except Exception as err:  # can't tell: treat as allowed
        ctx.logger.warning(f"vm: could not check who started the update ({err})")
        return False


def main():
    expected = ctx.instance.runtime_properties.get("expected_configuration")
    if not expected:
        drift(["no expected_configuration recorded by the edge-plugin"])
        return
    try:
        desired, applied = canonical(ctx.node.properties["vm_config"]), canonical(expected)
    except Exception as err:  # can't compare: let the plugin update the VM
        drift([f"could not compare the VM config ({err})"])
        return
    lines = [f"{key}: {applied[key]!r} -> {desired[key]!r}" for key in desired if desired[key] != applied[key]]
    # Never send the VM an update the Endpoint refuses, or one a parent doesn't
    # know about: a failed VM update can turn into delete + create of the VM
    # (automatic reinstall here, or in the parent). The VM is left as it is;
    # update_guard reports the reason.
    if lines and direct_update_of_managed_vm():
        ctx.logger.warning("vm: update not applied - this VM is managed by its parent deployment")
        ctx.returns(None)
        return
    refused = shrinks(desired, applied) if lines else []
    if refused:
        ctx.logger.warning("vm: update not applied - disks can only grow: " + ", ".join(refused))
        ctx.returns(None)
        return
    if lines:
        drift(lines)
    else:
        ctx.logger.info("vm: no drift (the VM config is unchanged)")
        ctx.returns(None)


main()
