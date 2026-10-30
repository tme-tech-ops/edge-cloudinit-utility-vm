# Edge Cloudinit Utility VM Blueprint
Utility blueprint for edge-cloudinit-linux multi-vm deployments. 
This blueprint can be used stand-alone or deployed as a ServiceComponent

## Features
- Deploys a VM using edge-plugin NativeEdgeVM component
- Supports cloudinit config
- Supports multiple disk and network configurations
- gathers proxy connection and VP IP details

## Versions and upload

Upload this blueprint with the name **`edge-cloudinit-utility-vm`** and the
**revision equal to its version** (top of `CHANGELOG.md`, also the `version`
label), for example `1.2.0.0`. Parent blueprints pin the exact revision they
were tested with (`Utility VM Blueprint Revision` in edge-cloudinit-linux), so
uploading a newer revision doesn't change running VMs until their parent is
updated to it.

Versions are `MAJOR.MINOR.PATCH.BUILD`. Within a MAJOR the inputs and
capabilities only grow (MINOR adds, PATCH fixes, BUILD is docs only), so a
parent built for 1.2 works with any later 1.x revision.

## Compatibility Matrix

| Release | Compatible DDPC EdgeOS Version | Blueprint version |
|---|---|---|
| `rel-4.2.0.0` | `4.2.0.0` | 1.1.0.x |
| `rel-4.3.0.0` | `4.3.0.0` | 1.1.0.x |
| (next) | `4.3.0.0` | 1.2.0.0 |

## Requirements
This blueprint must be deployed with a VM image that supports ssh login to a shell environment via ssh-key authorization. The ssh authorized_keys must be pre-created on the VM. For that reason it is easiest to use this VM with a cloudinit configuration and pass the ssh public key info at runtime to the cloudinit config and the ssh private key for ssh authentication during vm_info.

**Required Inputs**
- service_tag
- name
- image
- disk
- ssh_private_key_secret

**Requirements for edge-cloudinit-linux blueprint**
- when using with the `edge-cloud-init-linux` top-level blueprint, by default it looks for the blueprint named `edge-cloudinit-utility-vm`. If uploading this utility blueprint with a different name, make sure to update `Utility VM Blueprint Name` input accordingly

## Updating a deployment

**A utility deployment created by a parent blueprint** (edge-cloudinit-linux,
rke2-tech-ops multi-node; label `csys-component=true`) **is updated through its
parent.** An update started on the utility deployment itself is refused before
anything changes ("This VM is managed by the parent deployment ..."), because
the parent's next update would send its own values back and undo it.

A standalone utility deployment can be updated directly. Only these inputs can
change on a running VM; everything else is set when the VM is created:

| Input | Change | Notes |
|---|---|---|
| `cpu`, `memory` | up or down | The VM reboots. |
| `storage` | grow only | The Endpoint refuses to shrink a disk. The root file system grows at boot. |
| `network_settings` | segment, NAT port-forward rules | The VM reboots and keeps its MAC; with DHCP it gets an address on the new segment. Don't add or remove NICs (the guest's netplan matches NICs by name). |
| `usb` | add or remove | The VM reboots. |
| `additional_disks` | add, grow, remove | Removing a disk deletes it and its data. |

- Keep **Run automatic reinstall** unchecked. If the Endpoint refuses a change
  (for example a smaller disk), the update fails and the VM is unchanged; with
  automatic reinstall on, the orchestrator would delete and recreate the VM.
- If an app is deployed on the VM (it is the "Deploy On" target), tick
  **Force**: DAP refuses updates of a deployment that others depend on.
- After a failed update, the deployment keeps the new input values. Run another
  update with the values the VM really has.

## Example ServiceComponent definition for an upstream blueprint

```
node_templates:
  vm:
    type: dell.nodes.ServiceComponent
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: { get_input: utility_blueprint_id }
          revision_id: { get_input: utility_blueprint_revision }
        deployment:
          inputs:
            service_tag: { get_environment_capability: ece_service_tag }
            name: { get_input: vm_name }
            image: { get_attribute: [binary_image, binary_details, extra, artifact_id] }
            os_type: { get_input: os_type }
            cpu: { get_input: vcpus }
            memory: { get_input: memory_size }
            storage: { get_input: os_disk_size }
            disk: { get_input: datastore_name }
            disk_controller: { get_input: disk_controller }
            hardware_options.vTPM: { get_input: hardware_options.vTPM }
            hardware_options.secure_boot: { get_input: hardware_options.secure_boot }
            hardware_options.firmware_type: { get_input: hardware_options.firmware_type }
            enable_management: { get_input: enable_management }
            network_settings: { get_input: network_settings }
            cloudinit: { get_attribute: [cloudinit, cloudinit_config] }
            vm_user_name: { get_input: vm_user_name }
            ssh_private_key_secret:
              concat:
                - get_attribute: [ssh_keys, secret_key_name]
                - "_private"
            vm_hostname: { get_input: vm_hostname }
            additional_disks: { get_input: additional_disks }
```

## Enhancements
- Enable pcie passthrough - TBD