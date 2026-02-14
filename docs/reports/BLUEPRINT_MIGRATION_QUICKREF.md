# Blueprint Migration - Quick Reference Guide

## 🚀 Quick Start (5 Minutes)

### **What is Blueprint Migration?**
Generates Terraform/OpenTofu code to migrate your cloud infrastructure between AWS ↔ GCP ↔ Azure.

### **Usage Flow**
```
1. /cloud-blueprint          → Generate code
2. Check your DMs           → Get download token
3. /cloud-blueprint-download → Download zip file
4. Extract & review         → Read the code
5. terraform apply          → Deploy (when ready)
```

---

## 📋 Commands Reference

### **1. Generate Blueprint**
```
/cloud-blueprint
  source_project_id: your-gcp-project
  target_provider: aws
  target_region: us-east-1
  iac_engine: terraform
  include_docs: true
```

**What it does:**
- Maps your cloud resources to target provider
- Generates Terraform code
- Creates downloadable zip file
- DMs you a secure download token

**Time**: 10-30 seconds  
**Memory**: ~80MB spike (temporary)  
**Expiration**: 24 hours

---

### **2. Download Blueprint**
```
/cloud-blueprint-download
  token: abc123def456
```

**What you get:**
- `main.tf` - Terraform configuration
- `variables.tf` - Input variables
- `outputs.tf` - Summary outputs
- `README.md` - Instructions
- `MAPPING_REPORT.md` - Detailed analysis
- `provider_configs/` - Backend configs

**File Size**: 15-50 KB  
**Format**: ZIP archive

---

### **3. Check Status**
```
/cloud-blueprint-status
```

Shows information about:
- How blueprints work
- Time limits (24h)
- Security features
- Memory usage
- Usage instructions

---

## 🎯 Use Cases

### **Use Case 1: Multi-Cloud Migration**
**Scenario**: Moving from GCP to AWS for cost savings

```bash
# 1. Generate blueprint
/cloud-blueprint source_project_id:my-gcp-project target_provider:aws target_region:us-east-1

# 2. Download and extract
/cloud-blueprint-download token:{from-dm}
unzip blueprint_abc123.zip

# 3. Review the code
cat main.tf
cat MAPPING_REPORT.md

# 4. Update variables
vim variables.tf
# Set: project_id, credentials_file, etc.

# 5. Test in staging
terraform init
terraform plan

# 6. Apply to production
terraform apply
```

**Time Saved**: 4-6 hours  
**Success Rate**: 80% (needs manual review)

---

### **Use Case 2: Learning Terraform**
**Scenario**: Want to learn IaC best practices

```bash
# Generate example code for your project
/cloud-blueprint source_project_id:learning-project target_provider:gcp target_region:us-central1

# Study the generated code
- See how resources are structured
- Learn provider configuration
- Understand variable management
- Review best practices
```

**Educational Value**: ⭐⭐⭐⭐⭐

---

### **Use Case 3: Cost Comparison**
**Scenario**: Evaluate cloud provider costs

```bash
# Generate blueprints for all 3 providers
/cloud-blueprint ... target_provider:aws
/cloud-blueprint ... target_provider:gcp
/cloud-blueprint ... target_provider:azure

# Compare MAPPING_REPORT.md from each
- Check complexity levels
- Review migration notes
- Estimate effort required
```

---

## 🔐 Security Features

### **Token-Based Access**
- Download token sent via DM (private)
- 16-character secure hash
- One-time use recommended
- Expires after 24 hours

### **Zero-Trust Architecture**
- ✅ No cloud credentials stored
- ✅ No API calls to real clouds
- ✅ Only configuration mapping
- ✅ Terraform code has placeholders (not secrets)

### **Time-Gated Downloads**
- Blueprint expires after 24 hours
- Automatic cleanup on expiration
- Re-generate if needed (free)

### **Ephemeral Storage**
- Vault data in RAM (lost on bot restart)
- Files on disk (auto-deleted after 24h)
- No database persistence

---

## 📊 Supported Migrations

### **Resource Types**

| Resource | AWS | GCP | Azure |
|----------|-----|-----|-------|
| **VM** | ✅ aws_instance | ✅ google_compute_instance | ✅ azurerm_virtual_machine |
| **Database** | ✅ aws_db_instance | ✅ google_sql_database_instance | ✅ azurerm_sql_database |
| **Bucket** | ✅ aws_s3_bucket | ✅ google_storage_bucket | ✅ azurerm_storage_account |

**More types coming soon**: VPC, Kubernetes, Load Balancers

---

### **Migration Matrix**

| From → To | Complexity | Notes |
|-----------|-----------|-------|
| **GCP → AWS** | Medium | Machine type mapping required |
| **GCP → Azure** | Medium | Resource group creation needed |
| **AWS → GCP** | Medium | Region differences |
| **AWS → Azure** | Medium | IAM vs Azure AD |
| **Azure → GCP** | Medium | Resource group → project |
| **Azure → AWS** | Medium | VNet → VPC |

**Same Provider**: Low complexity (mostly copy)

---

## 🧪 Testing Your Blueprint

### **Step 1: Extract**
```bash
unzip blueprint_abc123.zip
cd blueprint_abc123/
```

### **Step 2: Review**
```bash
# Read the README
cat README.md

# Check resource mapping
cat MAPPING_REPORT.md

# Inspect Terraform code
cat main.tf
```

### **Step 3: Validate**
```bash
# Initialize Terraform
terraform init

# Validate syntax
terraform validate

# Expected: "Success! The configuration is valid."
```

### **Step 4: Plan (Dry Run)**
```bash
# Update variables first
vim variables.tf

# Run plan (does NOT apply)
terraform plan

# Review output carefully
# Check resource counts, types, configurations
```

### **Step 5: Apply (STAGING ONLY)**
```bash
# NEVER apply directly to production
# Use staging environment first

terraform apply

# Review changes
# Test functionality
# Verify costs
```

---

## ⚠️ Important Warnings

### **NOT Production-Ready As-Is**
❌ The generated code is a **BLUEPRINT**, not final code  
❌ Requires manual review and adjustments  
❌ Test in staging environment first  
❌ Consider data migration separately  

### **What You MUST Do**
✅ Review ALL generated code  
✅ Update variables with real values  
✅ Add security configurations  
✅ Configure networking properly  
✅ Plan data migration (databases)  
✅ Test thoroughly before production  

### **Complexity Levels**

**Low**: Simple VMs, buckets (2-4 hours work)  
**Medium**: VPCs, networking (1-2 days work)  
**High**: Databases, Kubernetes (1-2 weeks work)

---

## 🐛 Troubleshooting

### **Problem: Blueprint Generation Failed**

**Error**: "No resources found in project"  
**Solution**: Add resources to project first

**Error**: "Memory is too high"  
**Solution**: Restart bot or wait for cleanup

**Error**: "Invalid target region"  
**Solution**: Use correct region name (e.g., "us-east-1", not "US East")

---

### **Problem: Download Not Found**

**Error**: "Blueprint not found or expired"  
**Causes**:
- Token is incorrect (check DM)
- Blueprint expired (>24h old)
- Bot was restarted (vault cleared)

**Solution**: Generate new blueprint

---

### **Problem: Terraform Validation Fails**

**Error**: "Missing required argument"  
**Solution**: Update variables.tf with real values

**Error**: "Invalid provider configuration"  
**Solution**: Set credentials via environment variables or config files

---

## 💡 Pro Tips

### **Tip 1: Test with Small Projects First**
Start with 2-3 resources to understand the process before migrating large projects.

### **Tip 2: Use Version Control**
```bash
cd blueprint_abc123/
git init
git add .
git commit -m "Initial blueprint"
# Make changes incrementally with commits
```

### **Tip 3: Split Large Migrations**
Don't migrate everything at once. Split into phases:
1. Networking (VPC)
2. Compute (VMs)
3. Data (Databases)
4. Applications

### **Tip 4: Document Your Changes**
Keep a migration journal:
```markdown
# Migration Log

## 2026-02-01
- Generated blueprint (ID: abc123)
- Reviewed mapping report
- Identified 3 high-complexity resources

## 2026-02-02
- Updated variables
- Ran terraform plan
- Found 2 issues (fixed)

## 2026-02-03
- Applied to staging
- Tested functionality
- Ready for production
```

### **Tip 5: Save Tokens Securely**
Store download tokens in password manager or secure notes (not plaintext files).

---

## 📞 Getting Help

### **Common Questions**

**Q: Can I regenerate a blueprint?**  
A: Yes! Run `/cloud-blueprint` again (no limit)

**Q: Does this actually migrate my data?**  
A: No, it only generates Terraform code. Data migration is manual.

**Q: Is this free?**  
A: Yes, blueprint generation is free. Cloud provider costs apply when you deploy.

**Q: Can I edit the generated code?**  
A: Yes! That's expected. The blueprint is a starting point.

**Q: What if I need more than 20 resources?**  
A: Currently limited to 20 for memory. Generate multiple blueprints or request increase.

---

### **Support Channels**

1. **Discord**: Ask in your server's support channel
2. **Status Command**: `/cloud-blueprint-status` for info
3. **README**: Check generated README.md in blueprint
4. **Mapping Report**: MAPPING_REPORT.md has detailed notes

---

## 📈 Performance Expectations

| Operation | Time | Memory |
|-----------|------|--------|
| **Generation** | 10-30 sec | 80 MB spike |
| **Download** | 2-4 sec | 0 MB (file transfer) |
| **Terraform Plan** | 5-20 sec | 50 MB (local) |
| **Terraform Apply** | 2-10 min | 50 MB (local) |

---

## 🎓 Learning Resources

### **Terraform Basics**
- [Terraform Documentation](https://www.terraform.io/docs)
- [Learn Terraform](https://learn.hashicorp.com/terraform)

### **Cloud Provider Docs**
- [AWS Terraform Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [GCP Terraform Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Azure Terraform Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)

### **Migration Guides**
- AWS Migration Hub
- Google Cloud Migrate
- Azure Migrate

---

## 🔄 Workflow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  BLUEPRINT MIGRATION WORKFLOW                           │
└─────────────────────────────────────────────────────────┘

Step 1: GENERATE
┌──────────────┐
│ Discord User │
└──────┬───────┘
       │ /cloud-blueprint
       ▼
┌──────────────┐       ┌─────────────┐
│  Cloud Bot   │──────▶│ Generator   │
└──────────────┘       └──────┬──────┘
                              │ Map resources
                              │ Generate Terraform
                              │ Create zip
                              ▼
                       ┌─────────────┐
                       │ Vault Store │
                       └──────┬──────┘
                              │ Save token
                              ▼
                       ┌─────────────┐
                       │  DM User    │
                       └─────────────┘

Step 2: DOWNLOAD
┌──────────────┐
│ Discord User │
└──────┬───────┘
       │ /cloud-blueprint-download
       ▼
┌──────────────┐       ┌─────────────┐
│  Cloud Bot   │──────▶│ Vault Check │
└──────────────┘       └──────┬──────┘
                              │ Validate token
                              │ Check expiration
                              ▼
                       ┌─────────────┐
                       │ Send File   │
                       └─────────────┘

Step 3: DEPLOY
┌──────────────┐
│   User       │
└──────┬───────┘
       │ Extract zip
       │ Review code
       │ Update vars
       ▼
┌──────────────┐
│  Terraform   │
└──────┬───────┘
       │ init → plan → apply
       ▼
┌──────────────┐
│ Cloud Infra  │
└──────────────┘
```

---

## ✅ Final Checklist

Before using blueprints in production:

- [ ] Generated blueprint successfully
- [ ] Downloaded zip file
- [ ] Extracted all files
- [ ] Read README.md completely
- [ ] Reviewed MAPPING_REPORT.md
- [ ] Checked complexity levels
- [ ] Updated variables.tf with real values
- [ ] Ran `terraform init` successfully
- [ ] Ran `terraform plan` without errors
- [ ] Reviewed plan output carefully
- [ ] Tested in staging environment
- [ ] Verified functionality
- [ ] Checked costs
- [ ] Planned data migration (if databases)
- [ ] Created rollback plan
- [ ] Documented changes
- [ ] Got approval (if required)
- [ ] Ready for production!

---

**End of Quick Reference**  
For detailed technical docs, see: [BLUEPRINT_MIGRATION_IMPLEMENTATION.md](./BLUEPRINT_MIGRATION_IMPLEMENTATION.md)
