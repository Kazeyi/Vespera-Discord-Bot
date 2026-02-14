"""
Async Terraform Runner - Executes terraform plan/apply

This handles the actual terraform subprocess execution with async I/O.
Streams output to Discord threads for real-time monitoring.
"""

import asyncio
import os
import re
from typing import Optional, Tuple, AsyncGenerator
from pathlib import Path

from ..models.session import PlanResult


class TerraformRunner:
    """
    Async terraform execution engine
    
    Runs terraform commands as subprocesses and streams output.
    """
    
    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)
    
    async def init(self) -> Tuple[bool, str]:
        """
        Run terraform init
        
        Returns: (success, output)
        """
        cmd = ["terraform", "init", "-no-color"]
        return await self._run_command(cmd)
    
    async def plan(self, out_file: str = "tfplan") -> PlanResult:
        """
        Run terraform plan
        
        This is the critical "Plan-First" step.
        Returns: PlanResult with change summary
        """
        # First ensure terraform is initialized
        init_success, init_output = await self.init()
        
        if not init_success:
            return PlanResult(
                success=False,
                errors=[f"Terraform init failed: {init_output}"]
            )
        
        # Run plan
        cmd = ["terraform", "plan", "-no-color", f"-out={out_file}"]
        success, output = await self._run_command(cmd)
        
        if not success:
            return PlanResult(
                success=False,
                plan_output=output,
                errors=["Terraform plan failed"]
            )
        
        # Parse plan output
        plan_result = self._parse_plan_output(output)
        plan_result.success = True
        plan_result.plan_output = output
        
        return plan_result
    
    async def apply(self, plan_file: str = "tfplan") -> Tuple[bool, str]:
        """
        Run terraform apply with pre-generated plan
        
        Returns: (success, output)
        """
        cmd = ["terraform", "apply", "-no-color", "-auto-approve", plan_file]
        return await self._run_command(cmd)
    
    async def destroy(self) -> Tuple[bool, str]:
        """
        Run terraform destroy
        
        Returns: (success, output)
        """
        cmd = ["terraform", "destroy", "-no-color", "-auto-approve"]
        return await self._run_command(cmd)
    
    async def stream_plan(self) -> AsyncGenerator[str, None]:
        """
        Stream terraform plan output line-by-line
        
        Use this for Discord thread output streaming
        """
        cmd = ["terraform", "plan", "-no-color"]
        
        async for line in self._stream_command(cmd):
            yield line
    
    async def stream_apply(self, plan_file: str = "tfplan") -> AsyncGenerator[str, None]:
        """
        Stream terraform apply output line-by-line
        
        Use this for Discord thread output streaming
        """
        cmd = ["terraform", "apply", "-no-color", "-auto-approve", plan_file]
        
        async for line in self._stream_command(cmd):
            yield line
    
    async def _run_command(self, cmd: list) -> Tuple[bool, str]:
        """
        Run a terraform command and capture output
        
        Returns: (success, output)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.working_dir)
            )
            
            stdout, _ = await process.communicate()
            output = stdout.decode('utf-8', errors='replace')
            
            success = process.returncode == 0
            return success, output
        
        except FileNotFoundError:
            return False, "Terraform not found. Please install terraform."
        except Exception as e:
            return False, f"Command execution failed: {e}"
    
    async def _stream_command(self, cmd: list) -> AsyncGenerator[str, None]:
        """
        Stream command output line-by-line
        
        Yields: Individual output lines
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.working_dir)
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                yield line.decode('utf-8', errors='replace').rstrip()
            
            await process.wait()
        
        except Exception as e:
            yield f"Error: {e}"
    
    def _parse_plan_output(self, output: str) -> PlanResult:
        """
        Parse terraform plan output to extract change summary
        
        Looks for: "Plan: X to add, Y to change, Z to destroy"
        """
        result = PlanResult(success=True)
        
        # Look for plan summary line
        # Example: "Plan: 2 to add, 0 to change, 0 to destroy."
        plan_pattern = r'Plan:\s+(\d+)\s+to\s+add,\s+(\d+)\s+to\s+change,\s+(\d+)\s+to\s+destroy'
        match = re.search(plan_pattern, output)
        
        if match:
            result.resources_to_add = int(match.group(1))
            result.resources_to_change = int(match.group(2))
            result.resources_to_destroy = int(match.group(3))
        
        # Look for "No changes" message
        if "No changes" in output or "Your infrastructure matches the configuration" in output:
            result.resources_to_add = 0
            result.resources_to_change = 0
            result.resources_to_destroy = 0
        
        # Extract warnings
        warning_patterns = [
            r'Warning:\s+(.+)',
            r'⚠\s+(.+)',
        ]
        
        for pattern in warning_patterns:
            warnings = re.findall(pattern, output, re.MULTILINE)
            result.warnings.extend(warnings[:5])  # Limit to 5 warnings
        
        return result
    
    @staticmethod
    def create_for_session(session_id: str) -> 'TerraformRunner':
        """
        Factory method to create runner for a specific session
        
        Working directory: terraform_runs/<session_id>/
        """
        working_dir = f"terraform_runs/{session_id}"
        return TerraformRunner(working_dir)
