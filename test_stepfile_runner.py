#!/usr/bin/env python3
"""
Test suite for the Stepfile Runner.
Run with: pytest test_stepfile_runner.py -v
"""
import os
import pytest
import tempfile
# test_stepfile_runner.py
import sys
from pathlib import Path

# Add current folder (the folder containing test_stepfile_runner.py) to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Now this should work
from stepfile_runner import StepfileRunner, StepfileConfig


class TestStepfileParser:
    """Tests for parsing Stepfile configuration."""

    def test_parse_variables(self, tmp_path):
        """Test parsing regular variables."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
# Comment line
NAME = myproject
VERSION = 1.0.0
""")
        
        runner = StepfileRunner(str(stepfile))
        config = runner.parse()
        
        assert config.variables["NAME"] == "myproject"
        assert config.variables["VERSION"] == "1.0.0"

    def test_parse_shell_env(self, tmp_path):
        """Test parsing shell environment variables."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
PATH.sh = /usr/local/bin:/usr/bin
DEBUG.sh = true
""")
        
        runner = StepfileRunner(str(stepfile))
        config = runner.parse()
        
        assert config.shell_env["PATH"] == "/usr/local/bin:/usr/bin"
        assert config.shell_env["DEBUG"] == "true"

    def test_parse_commands(self, tmp_path):
        """Test parsing command lines."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
echo hello
ls -la
python script.py
""")
        
        runner = StepfileRunner(str(stepfile))
        config = runner.parse()
        
        assert len(config.commands) == 3
        assert config.commands[0] == "echo hello"
        assert config.commands[1] == "ls -la"
        assert config.commands[2] == "python script.py"

    def test_parse_mixed_content(self, tmp_path):
        """Test parsing a mix of variables, env, and commands."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
# Project configuration
PROJECT = awesome-app
VERSION = 2.0

# Environment
NODE_ENV.sh = production

# Commands
echo Starting $PROJECT$
npm install
npm run build
""")
        
        runner = StepfileRunner(str(stepfile))
        config = runner.parse()
        
        assert config.variables["PROJECT"] == "awesome-app"
        assert config.shell_env["NODE_ENV"] == "production"
        assert len(config.commands) == 3

    def test_ignore_comments_and_empty_lines(self, tmp_path):
        """Test that comments and empty lines are ignored."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
# This is a comment
VAR = value

# Another comment

echo test
""")
        
        runner = StepfileRunner(str(stepfile))
        config = runner.parse()
        
        assert len(config.variables) == 1
        assert len(config.commands) == 1

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing file."""
        runner = StepfileRunner("nonexistent_file")
        
        with pytest.raises(FileNotFoundError):
            runner.parse()


class TestVariableExpansion:
    """Tests for variable expansion functionality."""

    def test_expand_simple_variable(self, tmp_path):
        """Test expanding a simple variable."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
NAME = world
echo Hello $NAME$
""")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        expanded = runner._expand_variables("Hello $NAME$")
        assert expanded == "Hello world"

    def test_expand_multiple_variables(self, tmp_path):
        """Test expanding multiple variables in one string."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
FIRST = John
LAST = Doe
echo $FIRST$ $LAST$
""")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        expanded = runner._expand_variables("$FIRST$ $LAST$")
        assert expanded == "John Doe"

    def test_expand_with_env_fallback(self, tmp_path):
        """Test that expansion falls back to environment variables."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("echo test")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        os.environ["TEST_VAR"] = "from_env"
        expanded = runner._expand_variables("Value: $TEST_VAR$")
        assert expanded == "Value: from_env"
        
        del os.environ["TEST_VAR"]

    def test_undefined_variable_unchanged(self, tmp_path):
        """Test that undefined variables remain unchanged."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("echo test")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        expanded = runner._expand_variables("$UNDEFINED$")
        assert expanded == "$UNDEFINED$"


class TestCommandExecution:
    """Tests for command execution functionality."""

    def test_execute_simple_command(self, tmp_path):
        """Test executing a simple command."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("echo test")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        process = runner.execute_command("echo test", capture_output=True)
        process.wait()
        
        assert process.returncode == 0

    def test_execute_with_variable_expansion(self, tmp_path):
        """Test executing a command with variable expansion."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
MSG = hello
echo $MSG$
""")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        process = runner.execute_command("echo $MSG$", capture_output=True)
        stdout, _ = process.communicate()
        
        assert b"hello" in stdout

    def test_run_all_commands(self, tmp_path):
        """Test running all commands from stepfile."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
echo first
echo second
echo third
""")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        processes = runner.run(wait_for_completion=True)
        
        assert len(processes) == 3
        for process in processes:
            assert process.returncode == 0

    def test_run_with_shell_env(self, tmp_path):
        """Test that shell environment variables are passed to commands."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
CUSTOM_VAR.sh = test_value
printenv CUSTOM_VAR
""")
        
        runner = StepfileRunner(str(stepfile))
        runner.parse()
        
        processes = runner.run(wait_for_completion=True)
        assert len(processes) == 1


class TestStaticMethods:
    """Tests for static helper methods."""

    def test_is_variable_assignment(self):
        """Test detecting variable assignments."""
        assert StepfileRunner._is_variable_assignment("VAR = value")
        assert StepfileRunner._is_variable_assignment("PATH.sh=/usr/bin")
        assert not StepfileRunner._is_variable_assignment("echo test")
        assert not StepfileRunner._is_variable_assignment("$VAR$")

    def test_parse_assignment(self):
        """Test parsing variable assignments."""
        var, val = StepfileRunner._parse_assignment("NAME = John")
        assert var == "NAME"
        assert val == "John"
        
        var, val = StepfileRunner._parse_assignment("PATH=/usr/bin:/bin")
        assert var == "PATH"
        assert val == "/usr/bin:/bin"


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow(self, tmp_path):
        """Test a complete workflow with variables, env, and commands."""
        stepfile = tmp_path / "Stepfile"
        stepfile.write_text("""
# Configuration
PROJECT = test-project
OUTPUT = /tmp/output

# Environment
DEBUG.sh = 1

# Commands
echo Building $PROJECT$
mkdir -p $OUTPUT$
echo Done
""")
        
        runner = StepfileRunner(str(stepfile))
        config = runner.parse()
        
        assert config.variables["PROJECT"] == "test-project"
        assert config.shell_env["DEBUG"] == "1"
        assert len(config.commands) == 3
        
        processes = runner.run(wait_for_completion=True)
        assert len(processes) == 3


# Fixtures
@pytest.fixture
def sample_stepfile(tmp_path):
    """Create a sample Stepfile for testing."""
    stepfile = tmp_path / "Stepfile"
    stepfile.write_text("""
# Sample configuration
NAME = sample
VERSION = 1.0

# Environment
ENV.sh = test

# Commands
echo Starting
echo Done
""")
    return stepfile
