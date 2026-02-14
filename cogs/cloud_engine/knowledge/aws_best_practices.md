# AWS Best Practices Knowledge Base

## EC2 Instance Selection [performance]
- For web applications, use T3/T4g instances for burstable performance (t3.medium, t3.large)
- Memory-optimized (R6g, R6i) for databases and in-memory applications
- Compute-optimized (C6g, C6i) for batch processing and HPC workloads
- Use Graviton instances (ARM) for 20-40% better price-performance
- Always enable detailed monitoring for production instances
- Use EC2 Instance Savings Plans for 72% savings on committed workloads

## S3 Storage [cost]
- S3 Standard for frequently accessed data
- S3 Intelligent-Tiering for automatic cost optimization
- S3 Standard-IA for infrequent access (< once per month)
- S3 Glacier Instant Retrieval for archive data with instant access
- S3 Glacier Flexible Retrieval for long-term archives (minutes to hours)
- S3 Glacier Deep Archive for compliance archives (12+ hour retrieval)
- Enable S3 Lifecycle policies for automatic tiering
- Use S3 Transfer Acceleration for faster uploads

## RDS Database [reliability]
- Use Aurora for mission-critical workloads (5x MySQL performance)
- RDS MySQL/PostgreSQL for standard relational databases
- Enable Multi-AZ deployment for high availability (automatic failover)
- Configure automated backups with 7-35 day retention
- Enable encryption at rest using KMS
- Use read replicas for read-heavy workloads
- Set maintenance windows during low-traffic periods

## VPC Security [security]
- Create separate VPCs for production, staging, and development
- Use private subnets for application and database tiers
- Implement NAT Gateway for outbound internet access from private subnets
- Configure Security Groups (stateful firewall at instance level)
- Use Network ACLs (stateless firewall at subnet level)
- Enable VPC Flow Logs for network monitoring
- Use AWS WAF for application-level protection

## IAM Best Practices [security]
- Enable MFA for all user accounts, especially root
- Use IAM roles for EC2 instances instead of access keys
- Follow principle of least privilege
- Use IAM policies with conditions for fine-grained access
- Enable CloudTrail for audit logging of all API calls
- Rotate access keys every 90 days
- Use AWS SSO for centralized access management
- Never share access keys or embed in code

## Lambda Functions [cost]
- Best for event-driven, short-duration tasks (< 15 minutes)
- Set appropriate memory allocation (128MB-10GB)
- Use Lambda Power Tuning to optimize cost vs performance
- Configure reserved concurrency to prevent runaway costs
- Use Lambda layers for shared dependencies
- First 1M requests free, then $0.20 per 1M requests
- Costs $0.0000166667 per GB-second

## ECS/EKS Containers [reliability]
- Use ECS Fargate for serverless container orchestration
- EKS for Kubernetes-native workloads
- Configure auto-scaling for task/pod count
- Use Application Load Balancer for traffic distribution
- Enable Container Insights for monitoring
- Implement health checks for automatic recovery
- Use Spot instances for fault-tolerant workloads (70% savings)

## CloudWatch Monitoring [reliability]
- Set up CloudWatch alarms for critical metrics
- Use CloudWatch Logs for centralized logging
- Create CloudWatch Dashboards for visualization
- Configure SNS notifications for alerts
- Use CloudWatch Events for event-driven automation
- Set log retention policies to control costs
- Enable detailed monitoring for EC2 instances

## Secrets Manager [security]
- Store all credentials, API keys, and certificates in Secrets Manager
- Enable automatic rotation for supported databases
- Use IAM policies to control secret access
- Enable versioning for rollback capability
- Audit access using CloudTrail
- Estimated cost: $0.40 per secret per month + $0.05 per 10,000 API calls

## Cost Optimization [cost]
- Use AWS Compute Optimizer for rightsizing recommendations
- Enable AWS Cost Explorer for cost analysis
- Configure Budget Alerts to prevent overages
- Use Savings Plans for predictable workloads (up to 72% savings)
- Purchase Reserved Instances for steady-state workloads
- Delete unused EBS volumes, snapshots, and Elastic IPs
- Use S3 Intelligent-Tiering for automatic storage optimization
- Terminate idle EC2 instances

## Elastic Load Balancing [performance]
- Use Application Load Balancer (ALB) for HTTP/HTTPS traffic
- Network Load Balancer (NLB) for ultra-low latency TCP/UDP
- Configure health checks for automatic failover
- Enable access logging for troubleshooting
- Use SSL/TLS policies to enforce encryption
- Estimated cost: $0.0225/hour + $0.008/LCU-hour

## Auto Scaling [performance]
- Configure target tracking scaling for CPU, memory, or custom metrics
- Use scheduled scaling for predictable traffic patterns
- Set appropriate cooldown periods to prevent flapping
- Define min/desired/max instance counts carefully
- Use mixed instance types for cost optimization
- Test scaling policies under load

## CloudFront CDN [performance]
- Use CloudFront for global content delivery
- Enable caching for static assets
- Configure custom SSL certificates
- Use Lambda@Edge for edge computing
- Set appropriate TTL values for cache
- Enable compression for faster transfers
- Estimated cost: $0.085/GB (first 10 TB/month)

## Disaster Recovery [reliability]
- Implement backup strategy using AWS Backup
- Use cross-region replication for critical data
- Configure multi-region deployment for critical services
- Define RPO and RTO requirements
- Test disaster recovery procedures quarterly
- Use CloudFormation for infrastructure as code
- Enable versioning on S3 buckets for data protection

## Security Best Practices [security]
- Enable GuardDuty for threat detection
- Use AWS Security Hub for centralized security posture
- Configure AWS Config for compliance monitoring
- Enable VPC endpoints for private AWS service access
- Use AWS KMS for encryption key management
- Implement least privilege access with IAM
- Regular security audits using Trusted Advisor
