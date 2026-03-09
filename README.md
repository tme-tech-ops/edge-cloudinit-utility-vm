# Edge Cloudinit Utility VM Blueprint
Utility blueprint for edge-cloudinit-linux multi-vm deployments. 
This blueprint can be used stand-alone or deployed as a ServiceComponent

## Features
- Deploys a VM using edge-plugin NativeEdgeVM component
- Supports cloudinit config
- Supports multiple disk and network configurations
- gathers proxy connection and VP IP details

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