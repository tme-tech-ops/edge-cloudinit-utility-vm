"""check_drift for nodes whose settings only apply when the VM is created.

They never drift, so a deployment update never reinstalls them. Read-only.
"""
from dell import ctx

ctx.logger.info(f"{ctx.node.id}: no drift (set at creation only)")
ctx.returns(None)
