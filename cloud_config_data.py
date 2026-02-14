# --- Cloud Provider Configuration Data ---
"""
Provider-specific region and machine type mappings
Used for dynamic dropdown filtering to prevent human errors
"""

# GCP Regions and Machine Types
GCP_REGIONS = {
    "us-central1": {"name": "Iowa, USA", "zones": ["a", "b", "c", "f"]},
    "us-east1": {"name": "South Carolina, USA", "zones": ["b", "c", "d"]},
    "us-west1": {"name": "Oregon, USA", "zones": ["a", "b", "c"]},
    "europe-west1": {"name": "Belgium", "zones": ["b", "c", "d"]},
    "europe-west2": {"name": "London, UK", "zones": ["a", "b", "c"]},
    "asia-southeast1": {"name": "Singapore", "zones": ["a", "b", "c"]},
    "asia-northeast1": {"name": "Tokyo, Japan", "zones": ["a", "b", "c"]},
}

GCP_MACHINE_TYPES = {
    "e2-micro": {"cpu": 2, "ram": 1, "category": "general", "hourly_cost": 0.0084},
    "e2-small": {"cpu": 2, "ram": 2, "category": "general", "hourly_cost": 0.0168},
    "e2-medium": {"cpu": 2, "ram": 4, "category": "general", "hourly_cost": 0.0336},
    "e2-standard-2": {"cpu": 2, "ram": 8, "category": "general", "hourly_cost": 0.0672},
    "e2-standard-4": {"cpu": 4, "ram": 16, "category": "general", "hourly_cost": 0.1344},
    "n1-standard-1": {"cpu": 1, "ram": 3.75, "category": "general", "hourly_cost": 0.0475},
    "n1-standard-2": {"cpu": 2, "ram": 7.5, "category": "general", "hourly_cost": 0.0950},
    "n1-standard-4": {"cpu": 4, "ram": 15, "category": "general", "hourly_cost": 0.1900},
    "n2-standard-2": {"cpu": 2, "ram": 8, "category": "general", "hourly_cost": 0.0971},
    "n2-standard-4": {"cpu": 4, "ram": 16, "category": "general", "hourly_cost": 0.1942},
    "c2-standard-4": {"cpu": 4, "ram": 16, "category": "compute", "hourly_cost": 0.2088},
    "c2-standard-8": {"cpu": 8, "ram": 32, "category": "compute", "hourly_cost": 0.4176},
}

# AWS Regions and Instance Types
AWS_REGIONS = {
    "us-east-1": {"name": "N. Virginia, USA", "zones": ["a", "b", "c", "d", "e", "f"]},
    "us-west-1": {"name": "N. California, USA", "zones": ["a", "b", "c"]},
    "us-west-2": {"name": "Oregon, USA", "zones": ["a", "b", "c", "d"]},
    "eu-west-1": {"name": "Ireland", "zones": ["a", "b", "c"]},
    "eu-central-1": {"name": "Frankfurt, Germany", "zones": ["a", "b", "c"]},
    "ap-southeast-1": {"name": "Singapore", "zones": ["a", "b", "c"]},
    "ap-northeast-1": {"name": "Tokyo, Japan", "zones": ["a", "b", "c", "d"]},
}

AWS_INSTANCE_TYPES = {
    "t2.micro": {"cpu": 1, "ram": 1, "category": "general", "hourly_cost": 0.0116},
    "t2.small": {"cpu": 1, "ram": 2, "category": "general", "hourly_cost": 0.0232},
    "t2.medium": {"cpu": 2, "ram": 4, "category": "general", "hourly_cost": 0.0464},
    "t3.micro": {"cpu": 2, "ram": 1, "category": "general", "hourly_cost": 0.0104},
    "t3.small": {"cpu": 2, "ram": 2, "category": "general", "hourly_cost": 0.0208},
    "t3.medium": {"cpu": 2, "ram": 4, "category": "general", "hourly_cost": 0.0416},
    "m5.large": {"cpu": 2, "ram": 8, "category": "general", "hourly_cost": 0.096},
    "m5.xlarge": {"cpu": 4, "ram": 16, "category": "general", "hourly_cost": 0.192},
    "c5.large": {"cpu": 2, "ram": 4, "category": "compute", "hourly_cost": 0.085},
    "c5.xlarge": {"cpu": 4, "ram": 8, "category": "compute", "hourly_cost": 0.170},
}

# Azure Regions and VM Sizes
AZURE_REGIONS = {
    "eastus": {"name": "East US (Virginia)", "zones": ["1", "2", "3"]},
    "westus": {"name": "West US (California)", "zones": ["1", "2", "3"]},
    "westeurope": {"name": "West Europe (Netherlands)", "zones": ["1", "2", "3"]},
    "northeurope": {"name": "North Europe (Ireland)", "zones": ["1", "2", "3"]},
    "southeastasia": {"name": "Southeast Asia (Singapore)", "zones": ["1", "2", "3"]},
    "japaneast": {"name": "Japan East (Tokyo)", "zones": ["1", "2", "3"]},
}

AZURE_VM_SIZES = {
    "Standard_B1s": {"cpu": 1, "ram": 1, "category": "general", "hourly_cost": 0.0104},
    "Standard_B2s": {"cpu": 2, "ram": 4, "category": "general", "hourly_cost": 0.0416},
    "Standard_D2s_v3": {"cpu": 2, "ram": 8, "category": "general", "hourly_cost": 0.096},
    "Standard_D4s_v3": {"cpu": 4, "ram": 16, "category": "general", "hourly_cost": 0.192},
    "Standard_F2s_v2": {"cpu": 2, "ram": 4, "category": "compute", "hourly_cost": 0.085},
    "Standard_F4s_v2": {"cpu": 4, "ram": 8, "category": "compute", "hourly_cost": 0.169},
}

# Map provider to regions and machine types
PROVIDER_CONFIG = {
    "gcp": {
        "regions": GCP_REGIONS,
        "machine_types": GCP_MACHINE_TYPES,
        "default_region": "us-central1"
    },
    "aws": {
        "regions": AWS_REGIONS,
        "machine_types": AWS_INSTANCE_TYPES,
        "default_region": "us-east-1"
    },
    "azure": {
        "regions": AZURE_REGIONS,
        "machine_types": AZURE_VM_SIZES,
        "default_region": "eastus"
    }
}


def get_regions_for_provider(provider: str) -> dict:
    """Get all regions for a cloud provider"""
    return PROVIDER_CONFIG.get(provider, {}).get("regions", {})


def get_machine_types_for_provider(provider: str) -> dict:
    """Get all machine types for a cloud provider"""
    return PROVIDER_CONFIG.get(provider, {}).get("machine_types", {})


def get_machine_type_details(provider: str, machine_type: str) -> dict:
    """Get details for a specific machine type"""
    machine_types = get_machine_types_for_provider(provider)
    return machine_types.get(machine_type, {})


def validate_region_machine_combo(provider: str, region: str, machine_type: str) -> bool:
    """
    Validate that a machine type is available in a region
    (In reality, most machine types are available in all regions,
    but some specialized types are region-specific)
    """
    regions = get_regions_for_provider(provider)
    machine_types = get_machine_types_for_provider(provider)
    
    return region in regions and machine_type in machine_types


def estimate_monthly_cost(provider: str, machine_type: str, hours_per_month: int = 730) -> float:
    """Estimate monthly cost for a machine type"""
    details = get_machine_type_details(provider, machine_type)
    hourly_cost = details.get("hourly_cost", 0.0)
    return hourly_cost * hours_per_month


def categorize_workload_size(cpu: int, ram: float) -> str:
    """Categorize a workload based on specs"""
    if cpu <= 2 and ram <= 4:
        return "small"  # Dev/test, small web apps
    elif cpu <= 4 and ram <= 16:
        return "medium"  # Production web apps, small DBs
    elif cpu <= 8 and ram <= 32:
        return "large"  # High-traffic apps, medium DBs
    else:
        return "xlarge"  # Big data, ML, large DBs
