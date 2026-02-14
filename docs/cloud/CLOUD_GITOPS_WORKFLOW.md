# ☁️ Cloud ChatOps - GitOps Plan-to-Apply Workflow

## Overview

The Cloud ChatOps now implements a **Plan-to-Apply** workflow inspired by production GitOps tools like Atlantis and Terraform Cloud. This prevents accidental infrastructure deployments by requiring plan review before applying changes.

## Workflow Steps

### 1. 🔍 Run Plan (Dry Run)
- User clicks **"Run Plan (Dry Run)"** button in deployment lobby
- Creates a Discord Thread for plan output (keeps main channel clean)
- Runs `terraform init`, `terraform validate`, and `terraform plan` asynchronously
- Posts step-by-step progress updates in thread

### 2. 📊 Plan Review
- Terraform plan output is displayed in thread
- Shows resource changes:
  - ➕ Resources to add
  - 🔄 Resources to change
  - ❌ Resources to destroy
- Displays detailed resource-level changes

### 3. 🤖 AI Analysis
- AI Advisor automatically analyzes the plan using **Groq Llama 3.3** (fast)
- Provides:
  - 💰 **Cost Estimate**: Monthly spending prediction
  - 🔒 **Security Warnings**: Missing encryption, public exposure, etc.
  - ⚠️ **Best Practice Violations**: IAM issues, naming conventions
- AI uses RAG with 186 cloud best practices from GCP/AWS/Azure

### 4. ✅ Confirm Apply
- After plan review, **"Confirm Apply"** button becomes enabled
- User must explicitly approve the deployment
- Prevents accidental "one-click" deployments

### 5. 🚀 Deployment
- Runs `terraform apply` asynchronously in background (5-10 minutes)
- Avoids Discord's 3-second interaction timeout
- Posts progress updates to plan thread
- Notifies user via DM when complete

## Technical Implementation

### Asynchronous Execution
```python
# Prevent Discord timeout (3 seconds) with background tasks
asyncio.create_task(self._execute_plan_async(interaction, work_dir, thread))
asyncio.create_task(self._execute_apply_async(interaction, thread))
```

### State Tracking
```python
class DeploymentLobbyView:
    def __init__(self, session_id, bot, timeout=1800):
        self.plan_output = None        # Stores terraform plan result
        self.plan_thread = None        # Discord thread for status updates
        self.plan_completed = False    # Enables Apply button when True
```

### Button Layout
- **Row 0**: 🔍 Run Plan | ✅ Confirm Apply (disabled until plan completes)
- **Row 1**: ❌ Cancel | 📊 View Details

## Comparison with D&D Combat Lobby

| Feature | D&D Combat | Cloud Infrastructure |
|---------|-----------|---------------------|
| **Session Tracking** | Combat rounds, turn order | Deployment session, plan state |
| **State Management** | HP, conditions, initiative | Plan output, thread, completion flag |
| **Async Operations** | Dice rolls (instant) | Terraform plan/apply (5-10 min) |
| **Thread Usage** | Combat log | Plan output & deployment status |
| **User Interaction** | Attack, cast spell, end turn | Run plan, confirm apply, cancel |
| **Timeout** | 30 minutes | 30 minutes |

## GitOps Best Practices Implemented

✅ **Plan Before Apply**: Never deploy without reviewing changes
✅ **Async Execution**: Long-running tasks don't block Discord
✅ **Audit Trail**: All plan output saved in threads
✅ **AI Safety Review**: Automated security & cost analysis
✅ **Explicit Approval**: Two-step confirmation required
✅ **Status Tracking**: Progress updates during deployment
✅ **Session Management**: Automatic cleanup after 30 minutes

## Real-World Pattern Match

### Atlantis (GitHub + Terraform)
```
1. User opens PR → terraform plan runs
2. Plan posted as PR comment
3. Maintainer reviews plan
4. User comments "atlantis apply" → deployment starts
```

### Terraform Cloud
```
1. Workspace triggers plan
2. Plan shows cost estimate and policy checks
3. User confirms plan
4. Apply runs with detailed logs
```

### Cloud ChatOps (Discord)
```
1. User clicks "Run Plan" → terraform plan runs in thread
2. AI analyzes plan for cost/security
3. User reviews plan output
4. User clicks "Confirm Apply" → deployment starts
```

## AI Model Selection

- **Default**: Groq Llama 3.3 70B (fast, cost-effective)
- **Optional**: Google Gemini Pro (use `use_gemini=True` flag)
- Pattern matches DND cog (Groq default) and Translate/TLDR (Gemini optional)

## Usage Example

```
1. User: /cloud-deploy project_id:my-gcp-project resource_type:Compute Instance resource_name:web-server-01
2. Bot: [Creates deployment lobby with "Run Plan" button]
3. User: [Clicks "Run Plan"]
4. Bot: [Creates thread "☁️ Terraform Plan: abc123"]
5. Bot in Thread: 
   ⚙️ Running terraform init...
   ✅ Validation passed
   📊 Analyzing plan...
   
   Changes:
   ➕ To Add: 3 resources
   - google_compute_instance.web-server-01
   - google_compute_disk.boot-disk
   - google_compute_firewall.allow-http
   
   🤖 AI Analysis:
   💰 Estimated Cost: $73.20/month
   ⚠️ Warning: Firewall rule allows 0.0.0.0/0 (public access)
   
   ✅ Plan review complete! Return to lobby and click "Confirm Apply"
6. User: [Returns to lobby, clicks "Confirm Apply"]
7. Bot in Thread:
   🚀 STARTING DEPLOYMENT
   ⚙️ Running terraform apply -auto-approve...
   📊 Creating resources...
   ✅ Resources provisioned successfully
8. Bot: [Sends DM] ✅ Your cloud deployment is complete!
```

## Error Handling

- **Plan Failures**: Posted to thread with validation errors
- **Apply Failures**: Logged to thread, session marked as 'failed'
- **Timeout**: Session auto-cancelled after 30 minutes
- **Thread Closure**: Plan thread archived when deployment cancelled

## Benefits

1. **Safety**: Prevents accidental infrastructure changes
2. **Cost Control**: AI warns about expensive resources
3. **Security**: AI flags public exposure, missing encryption
4. **Compliance**: Automated policy checks via RAG knowledge base
5. **Audit**: Complete deployment history in threads
6. **UX**: No Discord timeouts during long deployments

## Next Steps

To use the new workflow:

1. Ensure bot has `CREATE_PUBLIC_THREADS` permission
2. AI Advisor is initialized with knowledge base (186 entries)
3. Terraform CLI is installed on bot server
4. Run `/cloud-deploy` and follow the 4-step workflow

## Technical Notes

- Plan execution: ~30-60 seconds
- Apply execution: 5-10 minutes (depending on resources)
- Thread auto-archives after 60 minutes (plan) or 24 hours (deployment)
- AI analysis adds ~2-5 seconds (Groq is fast)
- Knowledge base loaded from `cloud_engine/knowledge/*.md`
