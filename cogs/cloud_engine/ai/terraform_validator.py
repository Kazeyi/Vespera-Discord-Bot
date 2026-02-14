"""
Terraform Validator
Validates generated terraform configurations using terraform validate and plan
"""

import asyncio
import os
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result from terraform validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    plan_summary: Optional[Dict] = None
    raw_output: str = ""


class TerraformValidator:
    """Validate terraform configurations before deployment"""
    
    def __init__(self):
        self.terraform_binary = "terraform"
    
    async def validate_and_plan(self, terraform_code: str, provider: str, 
                               work_dir: Optional[str] = None) -> ValidationResult:
        """
        Validate terraform code and run plan
        
        Args:
            terraform_code: Terraform code to validate
            provider: Cloud provider (aws/gcp/azure)
            work_dir: Working directory (creates temp if None)
            
        Returns:
            ValidationResult with validation status and plan summary
        """
        
        # Create or use working directory
        cleanup_dir = False
        if not work_dir:
            work_dir = tempfile.mkdtemp(prefix=f"tf_validate_{provider}_")
            cleanup_dir = True
        
        work_path = Path(work_dir)
        work_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write terraform code
            tf_file = work_path / "main.tf"
            tf_file.write_text(terraform_code)
            
            # Step 1: terraform fmt (format check)
            fmt_result = await self._run_terraform_command(['fmt', '-check'], work_dir)
            warnings = []
            if fmt_result.returncode != 0:
                warnings.append("Terraform formatting issues detected")
            
            # Step 2: terraform init
            init_result = await self._run_terraform_command(['init', '-no-color'], work_dir)
            if init_result.returncode != 0:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Terraform init failed: {init_result.stderr}"],
                    warnings=warnings,
                    raw_output=init_result.stderr
                )
            
            # Step 3: terraform validate
            validate_result = await self._run_terraform_command(['validate', '-json'], work_dir)
            
            errors = []
            if validate_result.returncode != 0:
                try:
                    validate_json = json.loads(validate_result.stdout)
                    if 'diagnostics' in validate_json:
                        for diag in validate_json['diagnostics']:
                            severity = diag.get('severity', 'error')
                            summary = diag.get('summary', '')
                            detail = diag.get('detail', '')
                            
                            msg = f"{summary}: {detail}" if detail else summary
                            
                            if severity == 'error':
                                errors.append(msg)
                            else:
                                warnings.append(msg)
                except json.JSONDecodeError:
                    errors.append(validate_result.stderr)
            
            if errors:
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    raw_output=validate_result.stdout + "\n" + validate_result.stderr
                )
            
            # Step 4: terraform plan
            plan_result = await self._run_terraform_command(
                ['plan', '-out=tfplan', '-no-color', '-input=false'],
                work_dir
            )
            
            if plan_result.returncode != 0:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Terraform plan failed: {plan_result.stderr}"],
                    warnings=warnings,
                    raw_output=plan_result.stderr
                )
            
            # Parse plan output
            plan_summary = self._parse_plan_output(plan_result.stdout)
            
            # Step 5: terraform show -json (get detailed plan)
            show_result = await self._run_terraform_command(
                ['show', '-json', 'tfplan'],
                work_dir
            )
            
            if show_result.returncode == 0:
                try:
                    plan_json = json.loads(show_result.stdout)
                    plan_summary['resource_changes'] = self._extract_resource_changes(plan_json)
                except json.JSONDecodeError:
                    pass
            
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings,
                plan_summary=plan_summary,
                raw_output=plan_result.stdout
            )
        
        finally:
            # Cleanup temp directory
            if cleanup_dir:
                import shutil
                try:
                    shutil.rmtree(work_dir)
                except Exception as e:
                    print(f"Warning: Could not cleanup temp dir {work_dir}: {e}")
    
    async def _run_terraform_command(self, args: List[str], cwd: str) -> asyncio.subprocess.Process:
        """Run terraform command asynchronously"""
        
        process = await asyncio.create_subprocess_exec(
            self.terraform_binary,
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Create a simple namespace to hold results
        class Result:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout.decode('utf-8') if stdout else ''
                self.stderr = stderr.decode('utf-8') if stderr else ''
        
        return Result(process.returncode, stdout, stderr)
    
    def _parse_plan_output(self, plan_output: str) -> Dict:
        """Parse terraform plan output"""
        
        summary = {
            'to_add': 0,
            'to_change': 0,
            'to_destroy': 0,
            'has_changes': False
        }
        
        # Look for plan summary line
        # Example: "Plan: 5 to add, 0 to change, 0 to destroy."
        import re
        plan_match = re.search(
            r'Plan:\s+(\d+)\s+to\s+add,\s+(\d+)\s+to\s+change,\s+(\d+)\s+to\s+destroy',
            plan_output
        )
        
        if plan_match:
            summary['to_add'] = int(plan_match.group(1))
            summary['to_change'] = int(plan_match.group(2))
            summary['to_destroy'] = int(plan_match.group(3))
            summary['has_changes'] = (summary['to_add'] + summary['to_change'] + summary['to_destroy']) > 0
        
        # Check for "No changes" message
        if 'No changes' in plan_output or 'Your infrastructure matches the configuration' in plan_output:
            summary['has_changes'] = False
        
        return summary
    
    def _extract_resource_changes(self, plan_json: Dict) -> List[Dict]:
        """Extract resource changes from plan JSON"""
        
        changes = []
        
        if 'resource_changes' in plan_json:
            for change in plan_json['resource_changes']:
                resource_type = change.get('type', '')
                resource_name = change.get('name', '')
                actions = change.get('change', {}).get('actions', [])
                
                changes.append({
                    'resource': f"{resource_type}.{resource_name}",
                    'type': resource_type,
                    'name': resource_name,
                    'actions': actions,
                    'action_summary': ', '.join(actions)
                })
        
        return changes
    
    async def check_terraform_available(self) -> bool:
        """Check if terraform binary is available"""
        try:
            result = await self._run_terraform_command(['version'], '.')
            return result.returncode == 0
        except Exception:
            return False
