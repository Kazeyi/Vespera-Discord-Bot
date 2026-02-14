# Azure Best Practices Knowledge Base

## Virtual Machines [performance]
- Use B-series (B2s, B2ms) for burstable workloads and development
- D-series (Dsv5, Dasv5) for general-purpose production workloads
- E-series (Esv5) for memory-optimized applications
- F-series (Fsv2) for compute-optimized workloads
- Use Azure Spot VMs for fault-tolerant workloads (up to 90% savings)
- Enable Azure Monitor for detailed telemetry
- Use Availability Zones for high availability

## Blob Storage [cost]
- Hot tier for frequently accessed data
- Cool tier for infrequent access (30-day minimum, < once per month)
- Archive tier for long-term storage (180-day minimum, rare access)
- Use lifecycle management for automatic tiering
- Enable soft delete for accidental deletion protection
- Use Azure CDN for global content delivery
- Configure geo-redundant storage (GRS) for disaster recovery

## Azure SQL Database [reliability]
- Use General Purpose tier for most workloads
- Business Critical tier for mission-critical applications
- Enable active geo-replication for disaster recovery
- Configure automated backups (7-35 days retention)
- Use Always Encrypted for sensitive data protection
- Enable Transparent Data Encryption (TDE) by default
- Use read scale-out for read-heavy workloads

## Virtual Network Security [security]
- Create separate VNets for production, staging, and development
- Use Network Security Groups (NSGs) for subnet-level security
- Implement Azure Firewall for centralized network protection
- Enable DDoS Protection Standard for critical applications
- Use Private Endpoints for Azure service access
- Configure VNet peering for inter-VNet communication
- Enable NSG flow logs for network monitoring

## Azure Active Directory [security]
- Enable Multi-Factor Authentication (MFA) for all users
- Use Conditional Access for context-based access control
- Implement Privileged Identity Management (PIM) for just-in-time access
- Enable Azure AD Identity Protection for risk detection
- Use Managed Identities for Azure resource authentication
- Regular access reviews for permission auditing
- Enable Azure AD audit logs for compliance

## Azure Functions [cost]
- Best for event-driven, serverless workloads
- Use Consumption plan for variable workloads
- Premium plan for VNet integration and no cold starts
- Set appropriate timeout values (default 5 min, max 10 min)
- Use Durable Functions for stateful workflows
- First 1M executions free, then $0.20 per million
- Costs $0.000016/GB-s for execution

## Azure Kubernetes Service (AKS) [reliability]
- Use system node pools for AKS components
- User node pools for application workloads
- Enable cluster autoscaler for automatic scaling
- Use availability zones for high availability
- Implement Azure CNI for advanced networking
- Enable Azure Monitor for containers
- Use Azure Policy for governance

## Azure Monitor [reliability]
- Enable Application Insights for application monitoring
- Configure alerts for critical metrics
- Use Log Analytics workspaces for centralized logging
- Create Azure Dashboards for visualization
- Set up Action Groups for alert notifications
- Configure diagnostic settings for all resources
- Use Workbooks for advanced analysis

## Key Vault [security]
- Store all secrets, keys, and certificates in Key Vault
- Enable soft delete and purge protection
- Use Managed Identities for secret access
- Implement network restrictions using Private Endpoints
- Enable audit logging for compliance
- Rotate secrets regularly using automation
- Estimated cost: $0.03 per secret per month

## Cost Optimization [cost]
- Use Azure Cost Management for cost analysis
- Configure budget alerts to prevent overages
- Purchase Azure Reservations for 1-3 year commitments (up to 72% savings)
- Use Azure Hybrid Benefit for Windows Server/SQL licenses
- Rightsize VMs using Azure Advisor recommendations
- Delete unused resources (disks, NICs, public IPs)
- Use Azure Dev/Test pricing for non-production workloads
- Enable auto-shutdown for development VMs

## Load Balancer [performance]
- Use Application Gateway for HTTP/HTTPS load balancing with WAF
- Azure Load Balancer for network layer (layer 4) load balancing
- Azure Front Door for global application delivery
- Configure health probes for automatic failover
- Enable zone redundancy for high availability
- Use SSL offloading to reduce backend load
- Estimated cost: $0.025/hour + data processing fees

## Auto Scaling [performance]
- Configure VM Scale Sets for automatic scaling
- Use metric-based autoscale rules (CPU, memory, custom)
- Scheduled autoscale for predictable patterns
- Set appropriate min/max instance counts
- Define scale-in/scale-out cooldown periods
- Test scaling under load before production

## Azure Front Door [performance]
- Global application delivery with automatic failover
- WAF integration for security protection
- Caching for improved performance
- Custom domains with managed SSL certificates
- URL-based routing and path-based routing
- Session affinity for stateful applications
- Estimated cost: $0.01/hour + data transfer fees

## Disaster Recovery [reliability]
- Use Azure Site Recovery for VM replication
- Configure geo-redundant storage for critical data
- Implement Azure Backup for automated backups
- Define Recovery Point Objective (RPO) and Recovery Time Objective (RTO)
- Test failover procedures quarterly
- Use Azure Resource Manager templates for IaC
- Enable soft delete on storage accounts

## Security Best Practices [security]
- Enable Microsoft Defender for Cloud for security posture management
- Use Azure Policy for compliance enforcement
- Implement Just-In-Time (JIT) VM access
- Enable vulnerability assessment for VMs and containers
- Use Azure Private Link for secure service access
- Regular security assessments using Secure Score
- Enable threat protection for all supported services

## Container Instances [cost]
- Best for simple containerized applications without orchestration
- Fast startup time (< 1 second)
- Pay per second of execution
- Support for both Linux and Windows containers
- Use container groups for multi-container pods
- Estimated cost: $0.0000125/vCPU-second + $0.0000013/GB-second
- Ideal for batch jobs and temporary workloads
