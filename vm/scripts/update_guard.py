"""Refuses a direct update of a utility deployment that a parent manages.

A parent blueprint (edge-cloudinit-linux, rke2-tech-ops multi-node) creates
this deployment as a ServiceComponent, which labels it csys-component=true and
csys-obj-parent=<parent>. The parent owns its inputs: a change made here
directly is undone by the parent's next update, which sends the parent's values
back (one more reboot). So an update of such a deployment fails here, in the
drift-check phase, before any node changes, unless the parent is running an
update at that moment (the parent's component started this one). The update
record can't tell them apart: it carries the user who started the parent's
update.

Passes: updates while the parent runs an update, the check_drift workflow, and
standalone utility deployments (no csys-component label). Read-only.
"""
from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.manager import get_rest_client

ACTIVE = ("pending", "queued", "started", "scheduled")


def label_values(deployment, key):
    return [str(l.get("value")) for l in deployment.labels or [] if l.get("key") == key]


def update_in_progress(client, deployment_id):
    for execution in client.executions.list(deployment_id=deployment_id,
                                            _include=["id", "workflow_id", "status"]):
        if execution.get("workflow_id") == "update" and execution.get("status") in ACTIVE:
            return execution
    return None


def main():
    client = get_rest_client()
    deployment_id = ctx.deployment.id
    deployment = client.deployments.get(deployment_id, _include=["id", "labels"])
    if "true" not in [v.lower() for v in label_values(deployment, "csys-component")]:
        ctx.logger.info("update guard: standalone deployment, updates allowed")
        ctx.returns(None)
        return
    if not update_in_progress(client, deployment_id):
        ctx.logger.info("update guard: no update in progress (check_drift workflow)")
        ctx.returns(None)
        return

    parents = label_values(deployment, "csys-obj-parent")
    for parent in parents:
        execution = update_in_progress(client, parent)
        if execution:
            ctx.logger.info(f"update guard: started by the parent's update "
                            f"({parent}, execution {execution.get('id')})")
            ctx.returns(None)
            return
    raise NonRecoverableError(
        f"This VM is managed by the parent deployment {', '.join(parents) or '(unknown)'}. "
        "Update the parent deployment instead: a change made here directly is undone "
        "by the parent's next update. Nothing was changed.")


main()
