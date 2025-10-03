#!/usr/bin/env python3
"""
A Pythonic stepfile runner that executes commands from a configuration file.
"""
import logging

logging.basicConfig(
    level=logging.DEBUG,  # shows debug messages too
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StepfileConfig:
    """Configuration parsed from a Stepfile."""
    variables: Dict[str, str]
    shell_env: Dict[str, str]
    commands: List[str]


class StepfileRunner:
    """Executes commands defined in a Stepfile with variable expansion."""
    
    def __init__(self, stepfile_path: str = "Stepfile"):
        self.stepfile_path = Path(stepfile_path)
        self.config: Optional[StepfileConfig] = None
    
    def parse(self) -> StepfileConfig:
        """Parse the stepfile and extract configuration."""
        if not self.stepfile_path.exists():
            raise FileNotFoundError(f"Stepfile not found: {self.stepfile_path}")
        
        variables = {}
        shell_env = {}
        commands = []
        
        with self.stepfile_path.open('r') as f:
            for line in f:
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                if self._is_variable_assignment(line):
                    var_name, var_value = self._parse_assignment(line)
                    
                    if var_name.endswith('.sh'):
                        shell_env[var_name[:-3]] = var_value
                    else:
                        variables[var_name] = var_value
                else:
                    commands.append(line)
        
        self.config = StepfileConfig(
            variables=variables,
            shell_env=shell_env,
            commands=commands
        )
        return self.config
    
    @staticmethod
    def _is_variable_assignment(line: str) -> bool:
        """Check if line is a variable assignment."""
        return '=' in line and not line.startswith('$')
    
    @staticmethod
    def _parse_assignment(line: str) -> tuple[str, str]:
        """Parse a variable assignment line."""
        var_name, var_value = line.split('=', 1)
        return var_name.strip(), var_value.strip()
    
    def _expand_variables(self, text: str) -> str:
        """Expand variables in the format $VAR$."""
        def replacer(match):
            var_name = match.group(1)
            # Check config variables first, then environment
            return (
                self.config.variables.get(var_name) or
                os.environ.get(var_name) or
                match.group(0)
            )
        
        return re.sub(r'\$(\w+)\$', replacer, text)
    
    def execute_command(self, command: str, *, capture_output: bool = False) -> subprocess.Popen:
        """
        Execute a single command with variable expansion.
        
        Args:
            command: The command string to execute
            capture_output: Whether to capture stdout/stderr
        
        Returns:
            The Popen process object
        """
        expanded_command = self._expand_variables(command)
        cmd_parts = shlex.split(expanded_command)
        
        # Build environment with shell variables
        env = {**os.environ, **self.config.shell_env}
        
        stdout = subprocess.DEVNULL if not capture_output else subprocess.PIPE
        stderr = subprocess.DEVNULL if not capture_output else subprocess.PIPE
        
        process = subprocess.Popen(
            cmd_parts,
            env=env,
            stdout=stdout,
            stderr=stderr,
            shell=False # security wise
        )
        
        logging.debug(f"Launched: {' '.join(cmd_parts)}")
        return process
    
    def run(self, *, wait_for_completion: bool = False) -> List[subprocess.Popen]:
        """
        Run all commands from the stepfile.
        
        Args:
            wait_for_completion: Whether to wait for each command to complete
        
        Returns:
            List of process objects
        """
        if self.config is None:
            self.parse()
        
        processes = []
        for command in self.config.commands:
            process = self.execute_command(command)
            processes.append(process)
            
            if wait_for_completion:
                process.wait()
        
        return processes


def main():
    """Main entry point."""
    try:
        runner = StepfileRunner()
        runner.parse()
        runner.run()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("No steps available")
        exit(100)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
