"""
Git Integration - Version control for Terraform configurations

Automatically commits and tracks infrastructure changes.
"""

import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime


class GitManager:
    """
    Manage Git version control for Terraform configurations
    
    Features:
    - Auto-initialize repos
    - Commit on deployment
    - Tag releases
    - Push to remote (optional)
    """
    
    def __init__(self, base_dir: str = "terraform_runs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    async def init_repo(self, project_id: str) -> bool:
        """
        Initialize Git repository for a project
        
        Args:
            project_id: Project identifier
        
        Returns:
            True if successful
        """
        repo_dir = self.base_dir / project_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if already initialized
        if (repo_dir / '.git').exists():
            return True
        
        try:
            # Initialize repo
            await self._run_git_command(['init'], cwd=repo_dir)
            
            # Create .gitignore
            gitignore = repo_dir / '.gitignore'
            gitignore.write_text("""
# Terraform
.terraform/
*.tfstate
*.tfstate.*
*.tfvars
.terraform.lock.hcl

# Sensitive
*.pem
*.key
secrets.auto.tfvars

# OS
.DS_Store
Thumbs.db
""")
            
            # Initial commit
            await self._run_git_command(['add', '.gitignore'], cwd=repo_dir)
            await self._run_git_command(
                ['commit', '-m', 'Initial commit'],
                cwd=repo_dir
            )
            
            return True
        
        except Exception as e:
            print(f"Git init failed for {project_id}: {e}")
            return False
    
    async def commit_configuration(
        self,
        project_id: str,
        user_id: int,
        message: str,
        files: list = None
    ) -> Dict:
        """
        Commit Terraform configuration changes
        
        Args:
            project_id: Project identifier
            user_id: User who made changes
            message: Commit message
            files: Specific files to commit (None = all)
        
        Returns:
            Dict with success, commit_hash, message
        """
        repo_dir = self.base_dir / project_id
        
        # Ensure repo exists
        if not (repo_dir / '.git').exists():
            await self.init_repo(project_id)
        
        try:
            # Add files
            if files:
                for file in files:
                    await self._run_git_command(['add', file], cwd=repo_dir)
            else:
                await self._run_git_command(['add', '.'], cwd=repo_dir)
            
            # Commit with user context
            commit_msg = f"{message}\n\nDeployed-By: User-{user_id}\nTimestamp: {datetime.utcnow().isoformat()}"
            
            result = await self._run_git_command(
                ['commit', '-m', commit_msg],
                cwd=repo_dir
            )
            
            # Get commit hash
            commit_hash = await self._run_git_command(
                ['rev-parse', 'HEAD'],
                cwd=repo_dir
            )
            
            return {
                'success': True,
                'commit_hash': commit_hash.strip(),
                'message': message
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def tag_release(
        self,
        project_id: str,
        tag_name: str,
        message: str = ""
    ) -> bool:
        """
        Tag a release in Git
        
        Args:
            project_id: Project identifier
            tag_name: Tag name (e.g., v1.0.0, prod-2024-01-30)
            message: Tag annotation message
        
        Returns:
            True if successful
        """
        repo_dir = self.base_dir / project_id
        
        try:
            await self._run_git_command(
                ['tag', '-a', tag_name, '-m', message or tag_name],
                cwd=repo_dir
            )
            return True
        except Exception:
            return False
    
    async def get_commit_history(
        self,
        project_id: str,
        limit: int = 10
    ) -> list:
        """
        Get commit history for a project
        
        Args:
            project_id: Project identifier
            limit: Max commits to return
        
        Returns:
            List of commit dicts
        """
        repo_dir = self.base_dir / project_id
        
        if not (repo_dir / '.git').exists():
            return []
        
        try:
            # Get log in JSON-like format
            output = await self._run_git_command(
                ['log', f'-{limit}', '--pretty=format:%H|%an|%ae|%ai|%s'],
                cwd=repo_dir
            )
            
            commits = []
            for line in output.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('|')
                if len(parts) == 5:
                    commits.append({
                        'hash': parts[0],
                        'author': parts[1],
                        'email': parts[2],
                        'date': parts[3],
                        'message': parts[4]
                    })
            
            return commits
        
        except Exception:
            return []
    
    async def diff_changes(
        self,
        project_id: str,
        commit1: str = None,
        commit2: str = 'HEAD'
    ) -> str:
        """
        Show diff between commits
        
        Args:
            project_id: Project identifier
            commit1: First commit (None = working directory)
            commit2: Second commit (default: HEAD)
        
        Returns:
            Diff output as string
        """
        repo_dir = self.base_dir / project_id
        
        try:
            if commit1:
                output = await self._run_git_command(
                    ['diff', commit1, commit2],
                    cwd=repo_dir
                )
            else:
                output = await self._run_git_command(
                    ['diff'],
                    cwd=repo_dir
                )
            
            return output
        
        except Exception as e:
            return f"Error getting diff: {e}"
    
    async def rollback_to_commit(
        self,
        project_id: str,
        commit_hash: str
    ) -> bool:
        """
        Rollback to a specific commit
        
        Args:
            project_id: Project identifier
            commit_hash: Commit to rollback to
        
        Returns:
            True if successful
        """
        repo_dir = self.base_dir / project_id
        
        try:
            # Create rollback commit
            await self._run_git_command(
                ['revert', '--no-commit', f'{commit_hash}..HEAD'],
                cwd=repo_dir
            )
            
            await self._run_git_command(
                ['commit', '-m', f'Rollback to {commit_hash[:8]}'],
                cwd=repo_dir
            )
            
            return True
        
        except Exception:
            return False
    
    async def setup_remote(
        self,
        project_id: str,
        remote_url: str,
        remote_name: str = 'origin'
    ) -> bool:
        """
        Setup remote repository
        
        Args:
            project_id: Project identifier
            remote_url: Git remote URL
            remote_name: Remote name (default: origin)
        
        Returns:
            True if successful
        """
        repo_dir = self.base_dir / project_id
        
        try:
            # Check if remote exists
            remotes = await self._run_git_command(['remote'], cwd=repo_dir)
            
            if remote_name in remotes:
                # Update existing remote
                await self._run_git_command(
                    ['remote', 'set-url', remote_name, remote_url],
                    cwd=repo_dir
                )
            else:
                # Add new remote
                await self._run_git_command(
                    ['remote', 'add', remote_name, remote_url],
                    cwd=repo_dir
                )
            
            return True
        
        except Exception:
            return False
    
    async def push_to_remote(
        self,
        project_id: str,
        remote_name: str = 'origin',
        branch: str = 'main'
    ) -> bool:
        """
        Push commits to remote repository
        
        Args:
            project_id: Project identifier
            remote_name: Remote name
            branch: Branch name
        
        Returns:
            True if successful
        """
        repo_dir = self.base_dir / project_id
        
        try:
            await self._run_git_command(
                ['push', remote_name, branch],
                cwd=repo_dir
            )
            return True
        
        except Exception:
            return False
    
    def has_remote(self, project_id: str) -> bool:
        """
        Check if project has a remote configured
        
        Args:
            project_id: Project identifier
        
        Returns:
            True if remote exists
        """
        repo_dir = self.base_dir / project_id
        
        if not (repo_dir / '.git' / 'config').exists():
            return False
        
        config = (repo_dir / '.git' / 'config').read_text()
        return '[remote "origin"]' in config
    
    async def _run_git_command(
        self,
        args: list,
        cwd: Path
    ) -> str:
        """
        Run a Git command asynchronously
        
        Args:
            args: Git command arguments
            cwd: Working directory
        
        Returns:
            Command output
        """
        try:
            process = await asyncio.create_subprocess_exec(
                'git', *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Git command failed: {stderr.decode()}")
            
            return stdout.decode()
        
        except FileNotFoundError:
            raise Exception("Git not installed. Please install git.")
