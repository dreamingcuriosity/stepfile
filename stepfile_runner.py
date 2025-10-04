#!/usr/bin/env python3
"""
A Pythonic stepfile runner with DAG-based dependency management and group support.
"""
import logging
import os
import re
import shlex
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)


@dataclass
class Command:
    """Represents a command with dependencies and groups."""
    name: Optional[str]
    cmd: str
    depends_on: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)  # New: groups this command belongs to
    process: Optional[subprocess.Popen] = None
    exit_code: Optional[int] = None


@dataclass
class StepfileConfig:
    """Configuration parsed from a Stepfile."""
    variables: Dict[str, str]
    shell_env: Dict[str, str]
    named_commands: Dict[str, Command]
    unnamed_commands: List[Command]
    groups: Dict[str, Set[str]] = field(default_factory=dict)  # New: group -> command names


class StepfileRunner:
    """Executes commands with DAG-based dependency resolution and group support."""

    def __init__(self, stepfile_path: str = "Stepfile"):
        self.stepfile_path = Path(stepfile_path)
        self.config: Optional[StepfileConfig] = None

    def parse(self) -> StepfileConfig:
        """Parse the stepfile and extract configuration with dependencies and groups."""
        if not self.stepfile_path.exists():
            raise FileNotFoundError(f"Stepfile not found: {self.stepfile_path}")

        variables = {}
        shell_env = {}
        named_commands = {}
        unnamed_commands = []
        groups = defaultdict(set)  # group_name -> set of command names

        with self.stepfile_path.open('r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1

            if not line or line.startswith('#'):
                continue

            # Check for @group annotation
            if line.startswith('@group'):
                group_name, name, cmd = self._parse_group_line(line)
                if name:
                    command = Command(name=name, cmd=cmd, groups=[group_name])
                    named_commands[name] = command
                    groups[group_name].add(name)
                else:
                    unnamed_commands.append(Command(name=None, cmd=cmd, groups=[group_name]))
                continue

            # Check for @depends annotation
            if line.startswith('@depends'):
                deps, name, cmd = self._parse_depends_line(line)
                if name:
                    named_commands[name] = Command(name=name, cmd=cmd, depends_on=deps)
                else:
                    unnamed_commands.append(Command(name=None, cmd=cmd, depends_on=deps))
                continue

            # Check for @depends_group annotation
            if line.startswith('@depends_group'):
                group_deps, name, cmd = self._parse_depends_group_line(line)
                if name:
                    named_commands[name] = Command(name=name, cmd=cmd, depends_on=group_deps)
                else:
                    unnamed_commands.append(Command(name=None, cmd=cmd, depends_on=group_deps))
                continue

            # Check for variable assignment
            elif self._is_variable_assignment(line):
                var_name, var_value = self._parse_assignment(line)

                if var_name.endswith('.sh'):
                    shell_env[var_name[:-3]] = var_value
                else:
                    variables[var_name] = var_value
            # Check for named command (name = command)
            elif '=' in line and not line.startswith('$'):
                name, cmd = line.split('=', 1)
                name = name.strip()
                cmd = cmd.strip()
                named_commands[name] = Command(
                    name=name,
                    cmd=cmd,
                    depends_on=[]
                )
            # Regular unnamed command
            else:
                unnamed_commands.append(Command(
                    name=None,
                    cmd=line,
                    depends_on=[]
                ))

        self.config = StepfileConfig(
            variables=variables,
            shell_env=shell_env,
            named_commands=named_commands,
            unnamed_commands=unnamed_commands,
            groups=dict(groups)
        )
        
        # Expand group dependencies
        self._expand_group_dependencies()
        return self.config

    @staticmethod
    def _parse_depends_line(line: str) -> tuple[List[str], Optional[str], str]:
        """
        Parse @depends annotation.
        Formats:
          @depends(cmd1, cmd2) name = command
          @depends(cmd1) command
        """
        # Try with name assignment
        match = re.match(r'@depends\(([\w\-,\s]+)\)\s+(\w[\w\-]*)\s*=\s*(.+)', line)
        if match:
            deps = [d.strip() for d in match.group(1).split(',')]
            name = match.group(2)
            cmd = match.group(3).strip()
            return deps, name, cmd

        # Try without name (unnamed command with dependencies)
        match = re.match(r'@depends\(([\w\-,\s]+)\)\s+(.+)', line)
        if match:
            deps = [d.strip() for d in match.group(1).split(',')]
            cmd = match.group(2).strip()
            return deps, None, cmd

        raise ValueError(f"Invalid @depends syntax: {line}")

    @staticmethod
    def _parse_group_line(line: str) -> tuple[str, Optional[str], str]:
        """Parse @group annotation.
        Format: @group(group_name) [name =] command
        """
        # With name assignment
        match = re.match(r'@group\(([\w\-]+)\)\s+(\w[\w\-]*)\s*=\s*(.+)', line)
        if match:
            return match.group(1), match.group(2), match.group(3).strip()

        # Without name (unnamed command)
        match = re.match(r'@group\(([\w\-]+)\)\s+(.+)', line)
        if match:
            return match.group(1), None, match.group(2).strip()

        raise ValueError(f"Invalid @group syntax: {line}")

    @staticmethod
    def _parse_depends_group_line(line: str) -> tuple[List[str], Optional[str], str]:
        """Parse @depends_group annotation.
        Format: @depends_group(group1, group2) [name =] command
        """
        # With name assignment
        match = re.match(r'@depends_group\(([\w\-,\s]+)\)\s+(\w[\w\-]*)\s*=\s*(.+)', line)
        if match:
            groups = [g.strip() for g in match.group(1).split(',')]
            name = match.group(2)
            cmd = match.group(3).strip()
            return groups, name, cmd

        # Without name
        match = re.match(r'@depends_group\(([\w\-,\s]+)\)\s+(.+)', line)
        if match:
            groups = [g.strip() for g in match.group(1).split(',')]
            cmd = match.group(2).strip()
            return groups, None, cmd

        raise ValueError(f"Invalid @depends_group syntax: {line}")

    def _expand_group_dependencies(self):
        """Expand group dependencies into individual command dependencies."""
        for cmd_name, command in self.config.named_commands.items():
            expanded_deps = []
            for dep in command.depends_on:
                if dep in self.config.groups:
                    # Expand group to its member commands
                    expanded_deps.extend(self.config.groups[dep])
                else:
                    expanded_deps.append(dep)
            command.depends_on = expanded_deps

        # Also expand for unnamed commands
        for command in self.config.unnamed_commands:
            expanded_deps = []
            for dep in command.depends_on:
                if dep in self.config.groups:
                    expanded_deps.extend(self.config.groups[dep])
                else:
                    expanded_deps.append(dep)
            command.depends_on = expanded_deps

    @staticmethod
    def _is_variable_assignment(line: str) -> bool:
        """Check if line is a variable assignment (not a command)."""
        # Variable assignments are uppercase by convention
        if '=' not in line:
            return False
        var_name = line.split('=', 1)[0].strip()
        # Consider it a variable if it's UPPER_CASE or ends with .sh
        return var_name.isupper() or var_name.endswith('.sh')

    @staticmethod
    def _parse_assignment(line: str) -> tuple[str, str]:
        """Parse a variable assignment line."""
        var_name, var_value = line.split('=', 1)
        return var_name.strip(), var_value.strip()

    def _expand_variables(self, text: str) -> str:
        """Expand variables in the format $VAR$."""
        def replacer(match):
            var_name = match.group(1)
            return (
                self.config.variables.get(var_name) or
                os.environ.get(var_name) or
                match.group(0)
            )

        return re.sub(r'\$(\w+)\$', replacer, text)

    def _topological_sort(self) -> List[Command]:
        """
        Sort commands using topological sort (Kahn's algorithm).
        Returns commands in execution order.
        """
        # Build dependency graph
        in_degree = defaultdict(int)
        graph = defaultdict(list)
        all_commands = {name: cmd for name, cmd in self.config.named_commands.items()}

        # Calculate in-degrees
        for name, cmd in all_commands.items():
            if name not in in_degree:
                in_degree[name] = 0

            for dep in cmd.depends_on:
                if dep not in all_commands:
                    raise ValueError(f"Unknown dependency: '{dep}' required by '{name}'")
                graph[dep].append(name)
                in_degree[name] += 1

        # Find all nodes with no dependencies
        queue = deque([cmd for name, cmd in all_commands.items()
                       if in_degree[name] == 0])
        sorted_commands = []

        while queue:
            cmd = queue.popleft()
            sorted_commands.append(cmd)

            # Reduce in-degree for dependent commands
            if cmd.name:
                for dependent_name in graph[cmd.name]:
                    in_degree[dependent_name] -= 1
                    if in_degree[dependent_name] == 0:
                        queue.append(all_commands[dependent_name])

        # Check for circular dependencies
        if len(sorted_commands) != len(all_commands):
            remaining = set(all_commands.keys()) - {cmd.name for cmd in sorted_commands}
            raise ValueError(f"Circular dependency detected involving: {remaining}")

        # Add unnamed commands at the end (they run after all named commands)
        sorted_commands.extend(self.config.unnamed_commands)

        return sorted_commands

    def execute_command(self, command: Command) -> None:
        """Execute a single command and store the process."""
        expanded_command = self._expand_variables(command.cmd)
        cmd_parts = shlex.split(expanded_command)

        # Build environment with shell variables
        env = {**os.environ, **self.config.shell_env}

        logging.info(f"Executing: {command.name or command.cmd}")
        logging.debug(f"  Command: {' '.join(cmd_parts)}")

        command.process = subprocess.Popen(
            cmd_parts,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )

    def run(self, *, stop_on_error: bool = True, parallel: bool = False) -> Dict[str, Command]:
        """
        Run all commands respecting dependencies.

        Args:
            stop_on_error: Stop execution if a command fails
            parallel: Run independent commands in parallel (not fully implemented)

        Returns:
            Dictionary of command name -> Command (with exit codes)
        """
        if self.config is None:
            self.parse()

        sorted_commands = self._topological_sort()
        completed: Set[str] = set()
        results = {}

        logging.info(f"Executing {len(sorted_commands)} commands...")

        for cmd in sorted_commands:
            # Verify all dependencies completed successfully
            for dep in cmd.depends_on:
                if dep not in completed:
                    raise RuntimeError(f"Dependency '{dep}' not completed for '{cmd.name or cmd.cmd}'")

                dep_cmd = results[dep]
                if dep_cmd.exit_code != 0:
                    logging.error(f"Skipping '{cmd.name or cmd.cmd}' - dependency '{dep}' failed")
                    if stop_on_error:
                        return results
                    continue

            # Execute the command
            self.execute_command(cmd)

            # Wait for completion
            stdout, stderr = cmd.process.communicate()
            cmd.exit_code = cmd.process.returncode

            # Log output
            if stdout:
                logging.debug(f"  stdout: {stdout.decode().strip()}")
            if stderr:
                logging.debug(f"  stderr: {stderr.decode().strip()}")

            if cmd.exit_code == 0:
                logging.info(f"✓ Success: {cmd.name or cmd.cmd}")
            else:
                logging.error(f"✗ Failed: {cmd.name or cmd.cmd} (exit code: {cmd.exit_code})")
                if stop_on_error:
                    logging.error("Stopping execution due to failure")
                    return results

            # Mark as completed
            if cmd.name:
                completed.add(cmd.name)
                results[cmd.name] = cmd

        logging.info(f"Execution complete: {len(completed)} commands succeeded")
        return results

    def visualize_dag(self) -> str:
        """Generate a text-based visualization of the dependency graph."""
        if self.config is None:
            self.parse()

        lines = ["Dependency Graph:", "=" * 50]

        for name, cmd in self.config.named_commands.items():
            if cmd.depends_on:
                deps = ", ".join(cmd.depends_on)
                lines.append(f"{name} -> depends on: [{deps}]")
            else:
                lines.append(f"{name} -> no dependencies")

        if self.config.unnamed_commands:
            lines.append(f"\n{len(self.config.unnamed_commands)} unnamed commands (run last)")

        # Add group information
        if self.config.groups:
            lines.append(f"\nGroups:")
            for group_name, commands in self.config.groups.items():
                lines.append(f"  {group_name}: {', '.join(commands)}")

        return "\n".join(lines)


def main():
    """Main entry point."""
    import sys

    # Check for flags
    visualize = '--visualize' in sys.argv or '-v' in sys.argv
    debug = '--debug' in sys.argv or '-d' in sys.argv

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        runner = StepfileRunner()
        runner.parse()

        if visualize:
            print(runner.visualize_dag())
            return

        results = runner.run(stop_on_error=True)

        # Exit with error if any command failed
        failed = [name for name, cmd in results.items() if cmd.exit_code != 0]
        if failed:
            logging.error(f"Failed commands: {', '.join(failed)}")
            sys.exit(1)

    except FileNotFoundError as e:
        logging.error(f"{e}")
        print("No steps available")
        sys.exit(100)
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(2)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=debug)
        sys.exit(1)


if __name__ == "__main__":
    main()
