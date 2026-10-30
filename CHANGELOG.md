# Changelog for edge-cloudinit-utility-vm

All notable changes to this blueprint are recorded here. The version is also
the catalog revision to upload the blueprint as (see the README).

## 1.2.0.0 - unreleased

Deployment updates (Day-2). Same input and capability names as 1.1.0.4, so parents
built for 1.1 work with it.

- Fixed: the VM's drift check always reported drift (the edge-plugin's own
  check is synthetic). Every update sent the VM a no-op update, which reboots
  it or never completes, and the deployment stayed "drifted" afterwards, which
  failed the parent's update. A real check (`vm/scripts/vm_check_drift.py`)
  compares the requested VM config with the one last applied.
- Added: after a VM update, `update_postapply` reads the VM record from the
  Endpoint and fails the update if the change wasn't applied
  (`vm/scripts/vm_postupdate.py`).
- Fixed: the IP capabilities (`vm_primary_ip`, `tap_ip`, `vm_add_nics`) went
  stale after an update. `get_vm_info.sh` now saves them as one top-level
  runtime property (nested writes are dropped in update operations).
  `vm_add_nics` is now a list (or "N/A") instead of a string.
- Added: `cloudinit` and `format_serial_ports` report no drift (they only
  apply when the VM is created), so an update never reinstalls them.
- Added: refused updates fail with the reason and leave the VM as it is. A
  user's update that changes a utility deployment created by a parent
  blueprint (label `csys-component=true`) is refused: update the parent
  instead. An update with no change is allowed, to repair a deployment left
  in "failed update". In a standalone deployment, a disk that would shrink is
  refused (the Endpoint can't shrink disks). The VM's drift check skips the VM
  in these cases and `update_guard` fails the update; with "Run automatic
  reinstall" the guard is reinstalled and fails the same way. Updates started
  by the parent never fail here, so a refused change can never make the
  parent recreate the VM.
- Changed: inputs have display groups, labels, descriptions and constraints
  with error messages. Only inputs the edge-plugin can change on a running VM
  are updatable: vCPUs, memory, OS disk size (grow only), network settings
  (segment and NAT rules), USB devices and additional disks.
- Changed: `CHANGELOG.yaml` is now `CHANGELOG.md`.

## 1.1.0.4

- Return the configured VM name from the `vm_name` capability using the
  current VM configuration schema and centralize plugin imports.
