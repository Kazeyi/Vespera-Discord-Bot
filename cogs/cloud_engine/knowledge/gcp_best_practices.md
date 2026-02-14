# GCP Best Practices Knowledge Base

## Compute Engine [performance]
- For web applications, use E2 instances (e2-medium, e2-standard-2) for cost-effective general-purpose computing
- Memory-optimized (n2-highmem) for databases and in-memory caches
- Compute-optimized (c2-standard) for batch processing and scientific computing
- Use N2D instances (AMD EPYC) for 10-15% better price-performance than N2
- Always enable Ops Agent for detailed monitoring and logging

## Cloud Storage [cost]
- Use Standard storage for frequently accessed data
- Nearline storage for data accessed < once per month (30-day minimum)
- Coldline for data accessed < once per quarter (90-day minimum)
- Archive for data accessed < once per year (365-day minimum)
- Enable lifecycle policies to automatically transition between storage classes
- Use Cloud CDN for global content delivery to reduce egress costs

## Cloud SQL [reliability]
- Always enable automated backups with point-in-time recovery
- Use high availability (HA) configuration for production workloads
- Enable SSL/TLS connections for all database traffic
- Use Cloud SQL Proxy for secure connections from applications
- Set maintenance windows during low-traffic periods
- Configure read replicas for read-heavy workloads

## VPC Security [security]
- Create separate VPCs for production, staging, and development
- Use private Google Access to access Google services without public IPs
- Implement firewall rules following least privilege principle
- Enable VPC Flow Logs for network monitoring and troubleshooting
- Use Cloud Armor for DDoS protection and WAF capabilities
- Implement Private Service Connect for private connectivity to Google services

## IAM Best Practices [security]
- Use service accounts for application authentication
- Grant roles at the smallest scope necessary (resource > project > organization)
- Use predefined roles instead of primitive roles (Owner, Editor, Viewer)
- Enable multi-factor authentication (MFA) for all users
- Regularly audit IAM policies and remove unused permissions
- Use workload identity for GKE workloads instead of service account keys

## Cloud Run [performance]
- Best for stateless containerized applications with variable traffic
- Set minimum instances to 0 for development, ≥1 for production
- Configure CPU allocation to "always" for CPU-intensive workloads
- Use Cloud Run Gen2 for better performance and features
- Set appropriate concurrency limits (default 80, max 1000)
- Estimated cost: $0.00002400/vCPU-second, $0.00000250/GiB-second

## GKE (Kubernetes Engine) [reliability]
- Use Autopilot mode for simplified cluster management
- Enable Workload Identity for secure pod authentication
- Configure horizontal pod autoscaling (HPA) for traffic spikes
- Use node auto-provisioning for automatic node pool scaling
- Enable binary authorization for container image security
- Implement Network Policies for pod-level network segmentation
- Always use at least 3 nodes across multiple zones for high availability

## Cloud Functions [cost]
- Best for event-driven, short-duration tasks (< 9 minutes)
- Use 2nd gen Cloud Functions for better performance
- Set appropriate memory allocation (128MB-8GB)
- Configure max instances to prevent runaway costs
- Use Cloud Scheduler for periodic tasks
- Estimated cost: First 2M invocations free, then $0.40/M invocations

## Secret Manager [security]
- Store all sensitive data (API keys, passwords, certificates) in Secret Manager
- Enable secret versioning for rollback capability
- Use IAM conditions for time-based or attribute-based access
- Rotate secrets regularly using automated rotation
- Audit secret access using Cloud Audit Logs
- Estimated cost: $0.06 per secret version per month

## Cloud Monitoring & Logging [reliability]
- Enable Cloud Monitoring for all resources
- Set up uptime checks for critical endpoints
- Configure alerting policies for important metrics
- Use log-based metrics for custom monitoring
- Set log retention policies to balance cost and compliance
- Export logs to Cloud Storage or BigQuery for long-term retention

## Cost Optimization [cost]
- Use committed use discounts for predictable workloads (37% savings)
- Enable sustained use discounts (automatic up to 30% for month-long usage)
- Use preemptible VMs for fault-tolerant workloads (up to 80% savings)
- Rightsize VMs using Recommender suggestions
- Delete unused resources (disks, IPs, load balancers)
- Use Budget Alerts to prevent unexpected costs
- Enable auto-scaling to match demand

## Network Load Balancing [performance]
- Use Global HTTP(S) Load Balancer for internet-facing applications
- Internal Load Balancer for private services
- Configure health checks for automatic failover
- Enable Cloud CDN for static content caching
- Use SSL policies to enforce TLS 1.2+
- Estimated cost: $0.025/hour + $0.008/GB processed

## Cloud Armor Security [security]
- Implement rate limiting to prevent abuse
- Use preconfigured WAF rules for OWASP Top 10
- Configure geo-based access controls
- Enable Bot Management for advanced protection
- Set up custom rules for application-specific threats
- Review security policy logs regularly

## Disaster Recovery [reliability]
- Implement 3-2-1 backup strategy (3 copies, 2 different media, 1 offsite)
- Use cross-region replication for critical data
- Document and test recovery procedures quarterly
- Use Cloud Scheduler for automated backups
- Set RPO (Recovery Point Objective) and RTO (Recovery Time Objective)
- Consider multi-region deployment for critical services
