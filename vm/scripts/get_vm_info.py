"""Read the ansible-produced VM info JSON and surface it as runtime
properties on this node instance.

The ansible playbook in vm/ansible/get_vm_info.yaml runs on the deployed
VM, gathers interface facts, and (via the get_vm_info role) writes a JSON
blob to /tmp/{node_instance_id}/vm_info.json on the orchestrator
(delegated to localhost). This script runs immediately after on the
central_deployment_agent, reads that JSON, and sets the runtime properties
the outputs.yaml capability layer expects.

Property shape is kept identical to the legacy fabric-plugin bash script
(get_vm_info.sh) so outputs.yaml + downstream consumers (edge-cloudinit-linux
parent) do not need changes:

  capabilities.vm_public_ip      : "<primary NIC IPv4>"
  capabilities.tap_ip            : "<mgmt NIC IPv4>" or "N/A"
  capabilities.vm_add_nics_ips   : '["enp2s0:1.2.3.4","enp3s0:5.6.7.8"]'
                                   string (legacy format) or "N/A"
"""
import json
import shutil
from pathlib import Path

from dell import ctx
from dell.exceptions import NonRecoverableError


def main():
    instance_id = ctx.instance.id
    data_path = Path(f"/tmp/{instance_id}/vm_info.json")

    if not data_path.exists():
        raise NonRecoverableError(
            f"VM info JSON not found at {data_path}. Did the get_vm_info "
            f"ansible playbook run successfully?"
        )

    with data_path.open() as fh:
        data = json.load(fh)

    primary_ip = data.get("primary_ip", "").strip()
    if not primary_ip:
        raise NonRecoverableError(
            "Primary IP missing from ansible-produced vm_info.json. "
            "Cannot continue."
        )

    tap_ip = data.get("tap_ip", "N/A") or "N/A"
    additional = data.get("additional_nics", {}) or {}

    # Surface capabilities to match the legacy fabric script's shape.
    caps = ctx.instance.runtime_properties.get("capabilities", {})
    caps["vm_public_ip"] = primary_ip
    caps["tap_ip"] = tap_ip

    if additional:
        entries = [f"{iface}:{ip}" for iface, ip in additional.items()]
        # Match legacy bash output: '["enp2s0:1.2.3.4","enp3s0:5.6.7.8"]'
        caps["vm_add_nics_ips"] = "[" + ",".join(f'"{e}"' for e in entries) + "]"
    else:
        caps["vm_add_nics_ips"] = "N/A"

    ctx.instance.runtime_properties["capabilities"] = caps

    ctx.logger.info(
        f"vm_info: primary={primary_ip} tap={tap_ip} "
        f"additional={caps['vm_add_nics_ips']}"
    )

    # Best-effort cleanup of orchestrator-side temp dir.
    try:
        shutil.rmtree(f"/tmp/{instance_id}")
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"Failed to clean /tmp/{instance_id}: {exc}")


main()
