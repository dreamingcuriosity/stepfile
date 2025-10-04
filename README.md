# Stepfile Runner

A Pythonic task runner that executes commands from a simple configuration file called a "Stepfile". Features **DAG-based dependency management** for complex build pipelines, making it a lightweight alternative to Makefiles with powerful orchestration capabilities.

## Features

- **DAG-based dependencies**: Define command dependencies with automatic topological sorting
- **Simple syntax**: Clean, readable format for variables, commands, and dependencies
- **Variable expansion**: Use `$VAR$` syntax to reference variables in commands
- **Shell environment variables**: Export variables to command environments with `.sh` suffix
- **Dependency validation**: Automatic circular dependency detection
- **Execution control**: Stop on errors or continue, sequential or parallel execution
- **Visualization**: View your dependency graph with `--visualize`
- **Secure by default**: Uses `shlex` for proper command parsing and avoids shell injection

## Installation

```bash
pip install -e .
```

Or copy `stepfile_runner.py` to your project.

## Quick Start

Create a file named `Stepfile` in your project directory:

```bash
# Variables
PROJECT_NAME=myapp
VERSION=1.0.0
BUILD_DIR=./build

# Named commands
clean = rm -rf $BUILD_DIR$
install = npm install

# Commands with dependencies
@depends(install) build = npm run build
@depends(install) test = npm test
@depends(build, test) package = tar -czf app.tar.gz dist/

# Unnamed commands run after all named commands
echo "Pipeline complete!"
```

Run it:

```bash
python stepfile_runner.py
```

## Stepfile Syntax

### Comments

Lines starting with `#` are ignored:

```bash
# This is a comment
```

### Variable Definitions

Assign variables using `NAME=value`:

```bash
APP_NAME=myproject
PORT=8080
BUILD_DIR=./dist
```

### Shell Environment Variables

Variables ending with `.sh` are exported to the command environment:

```bash
PATH.sh=/usr/local/bin:$PATH
DATABASE_URL.sh=postgresql://localhost/mydb
NODE_ENV.sh=production
```

### Named Commands

Commands with names can be referenced as dependencies:

```bash
build = npm run build
test = python -m pytest
deploy = ./deploy.sh
```

### Dependencies

Use `@depends()` to specify command dependencies:

```bash
# Single dependency
@depends(build) package = tar -czf app.tar.gz

# Multiple dependencies
@depends(lint, test, build) deploy = ./deploy.sh

# Unnamed command with dependencies
@depends(deploy) echo "Deployment complete!"
```

### Unnamed Commands

Commands without names run after all named commands complete:

```bash
echo "All tasks finished!"
date
```

### Variable Expansion

Reference variables using `$VARNAME$` syntax:

```bash
OUTPUT_DIR=./dist
mkdir -p $OUTPUT_DIR$
cp config.json $OUTPUT_DIR$/config.json
```

Variables are resolved from:
1. Variables defined in the Stepfile
2. System environment variables
3. If not found, the literal `$VAR$` text remains

## Command Line Usage

```bash
# Normal execution
python stepfile_runner.py

# Visualize dependency graph
python stepfile_runner.py --visualize

# Enable debug logging
python stepfile_runner.py --debug

# Combine flags
python stepfile_runner.py --visualize --debug
```

## Dependency Resolution

The runner uses **topological sorting** (Kahn's algorithm) to:

1. Determine correct execution order
2. Detect circular dependencies
3. Ensure dependencies complete before dependents run
4. Stop execution if a dependency fails

### Execution Order Example

Given this Stepfile:
```bash
install = npm install
@depends(install) lint = npm run lint
@depends(install) test = npm test
@depends(install) build = npm run build
@depends(lint, test, build) package = tar -czf app.tar.gz
```

Execution order will be:
1. `install`
2. `lint`, `test`, `build` (after install)
3. `package` (after lint, test, and build all succeed)

## Usage

### As a Script

```bash
# Run your Stepfile
./stepfile_runner.py

# Visualize dependencies before running
./stepfile_runner.py --visualize
```

### As a Library

```python
from stepfile_runner import StepfileRunner

# Parse and run with dependency resolution
runner = StepfileRunner("path/to/Stepfile")
runner.parse()

# Visualize the DAG
print(runner.visualize_dag())

# Execute all commands
results = runner.run(stop_on_error=True)

# Check results
for name, cmd in results.items():
    print(f"{name}: exit code {cmd.exit_code}")
```

### Error Handling

```python
runner = StepfileRunner()
runner.parse()

# Stop on first error (default)
results = runner.run(stop_on_error=True)

# Continue even if commands fail
results = runner.run(stop_on_error=False)

# Check for failures
failed = [name for name, cmd in results.items() if cmd.exit_code != 0]
if failed:
    print(f"Failed commands: {', '.join(failed)}")
```

### Custom Command Execution

```python
runner = StepfileRunner()
runner.parse()

# Get sorted command list
commands = runner._topological_sort()

# Execute specific command
for cmd in commands:
    if cmd.name == "build":
        runner.execute_command(cmd)
        cmd.process.wait()
```

## Example Stepfiles

### Simple Build Pipeline

```bash
# Configuration
APP_NAME=myapp
VERSION=1.0.0

# Pipeline steps
clean = rm -rf dist/
install = npm install
@depends(install) build = npm run build
@depends(build) test = npm test
@depends(test) package = tar -czf $APP_NAME$-$VERSION$.tar.gz dist/
```

### Complex CI/CD Pipeline

```bash
# Environment
DOCKER_REPO=mycompany/images
DEPLOY_ENV.sh=production

# Setup phase
clean = rm -rf build/ dist/
deps = pip install -r requirements.txt
deps-dev = pip install -r requirements-dev.txt

# Quality checks (parallel after deps)
@depends(deps-dev) lint = flake8 src/
@depends(deps-dev) typecheck = mypy src/
@depends(deps-dev) security = bandit -r src/

# Testing (after quality checks)
@depends(lint, typecheck, security) test-unit = pytest tests/unit
@depends(lint, typecheck, security) test-integration = pytest tests/integration

# Build (after tests pass)
@depends(deps, test-unit, test-integration) build = python setup.py sdist bdist_wheel

# Packaging
@depends(build) docker-build = docker build -t $DOCKER_REPO$/app:latest .
@depends(docker-build) docker-push = docker push $DOCKER_REPO$/app:latest

# Deployment
@depends(docker-push) deploy = kubectl apply -f k8s/

# Notification
@depends(deploy) echo "Deployment successful!"
@depends(deploy) curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK
```

### Multi-Stage Application Build

```bash
# Variables
FRONTEND_DIR=./frontend
BACKEND_DIR=./backend
DIST_DIR=./dist

# Frontend pipeline
frontend-install = cd $FRONTEND_DIR$ && npm install
@depends(frontend-install) frontend-lint = cd $FRONTEND_DIR$ && npm run lint
@depends(frontend-install) frontend-test = cd $FRONTEND_DIR$ && npm test
@depends(frontend-lint, frontend-test) frontend-build = cd $FRONTEND_DIR$ && npm run build

# Backend pipeline
backend-install = cd $BACKEND_DIR$ && pip install -r requirements.txt
@depends(backend-install) backend-lint = cd $BACKEND_DIR$ && flake8 .
@depends(backend-install) backend-test = cd $BACKEND_DIR$ && pytest
@depends(backend-lint, backend-test) backend-build = cd $BACKEND_DIR$ && python setup.py bdist_wheel

# Integration
@depends(frontend-build, backend-build) package = ./package.sh $DIST_DIR$
@depends(package) deploy = ./deploy.sh $DIST_DIR$
```

## Visualization

View your dependency graph:

```bash
$ python stepfile_runner.py --visualize

Dependency Graph:
==================================================
clean -> no dependencies
install -> no dependencies
lint -> depends on: [install]
test -> depends on: [install]
build -> depends on: [install]
quality-gate -> depends on: [lint, test]
package -> depends on: [build, quality-gate]
deploy -> depends on: [package]

2 unnamed commands (run last)
```

## Logging

The runner provides detailed logging:

```
12:34:56 [INFO] Executing 8 commands...
12:34:56 [INFO] Executing: clean
12:34:56 [INFO] ✓ Success: clean
12:34:57 [INFO] Executing: install
12:34:58 [INFO] ✓ Success: install
12:34:58 [INFO] Executing: build
12:35:02 [INFO] ✓ Success: build
...
```

Enable debug mode for more details:

```bash
python stepfile_runner.py --debug
```

## Error Handling

The runner provides specific exit codes:

- **Exit 0**: All commands succeeded
- **Exit 1**: Command execution failed
- **Exit 2**: Configuration error (invalid dependencies, circular deps, etc.)
- **Exit 100**: Stepfile not found

### Dependency Errors

```bash
# Missing dependency
@depends(nonexistent) build = npm run build
# Error: Unknown dependency: 'nonexistent' required by 'build'

# Circular dependency
@depends(b) a = echo a
@depends(a) b = echo b
# Error: Circular dependency detected involving: {'a', 'b'}
```

## Security Notes

- Commands are parsed with `shlex` to prevent shell injection
- `shell=False` is used in subprocess calls
- No arbitrary shell execution
- Environment variables are explicitly controlled

## Limitations

- Variable syntax uses `$VAR$` (not `${VAR}` or `$VAR`) to avoid conflicts
- Shell features like pipes (`|`) and redirects (`>`) won't work directly (use shell scripts)
- Parallel execution of independent tasks is not yet fully implemented
- Variable assignments must be UPPERCASE or end with `.sh` to distinguish from named commands

## Roadmap

- [ ] True parallel execution of independent commands
- [ ] Conditional execution (skip commands based on conditions)
- [ ] Retry logic with backoff
- [ ] Watch mode for development
- [ ] Output capture and logging options
- [ ] Integration with CI/CD platforms
- [ ] Command timeout support

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please submit pull requests or open issues for bugs and feature requests.

Key areas for contribution:
- Parallel execution implementation
- Enhanced visualization (Graphviz/Mermaid output)
- Performance optimizations
- Additional test coverage
### Comments

Lines starting with `#` are ignored:

```
# This is a comment
```

### Variable Definitions

Assign variables using `NAME=value`:

```
APP_NAME=myproject
PORT=8080
```

### Shell Environment Variables

Variables ending with `.sh` are exported to the command environment:

```
PATH.sh=/usr/local/bin:$PATH
DATABASE_URL.sh=postgresql://localhost/mydb
```

### Commands

Any line that isn't a comment or assignment is treated as a command:

```
npm install
python manage.py migrate
docker build -t $APP_NAME$ .
```

### Variable Expansion

Reference variables using `$VARNAME$` syntax:

```
OUTPUT_DIR=./dist
mkdir -p $OUTPUT_DIR$
cp config.json $OUTPUT_DIR$/config.json
```

Variables are resolved from:
1. Variables defined in the Stepfile
2. System environment variables
3. If not found, the literal `$VAR$` text remains

## Usage

### As a Library

```python
from stepfile_runner import StepfileRunner

# Parse and run all commands
runner = StepfileRunner("path/to/Stepfile")
runner.parse()
processes = runner.run()

# Wait for all processes to complete
for proc in processes:
    proc.wait()
```

### Sequential Execution

Wait for each command to complete before starting the next:

```python
runner = StepfileRunner()
runner.parse()
runner.run(wait_for_completion=True)
```

### Custom Command Execution

Execute specific commands with output capture:

```python
runner = StepfileRunner()
runner.parse()

process = runner.execute_command(
    "echo Hello $PROJECT_NAME$",
    capture_output=True
)
stdout, stderr = process.communicate()
print(stdout.decode())
```

## Example Stepfile

```
# Project configuration
PROJECT=webserver
VERSION=2.1.0
BUILD_DIR=./build
DOCKER_REPO=mycompany/images

# Environment setup
FLASK_ENV.sh=production
DATABASE_URL.sh=postgresql://db:5432/prod

# Build pipeline
echo "Starting build for $PROJECT$ v$VERSION$"
python -m pytest --cov=src tests/
python setup.py sdist bdist_wheel
mkdir -p $BUILD_DIR$
cp dist/* $BUILD_DIR$/
docker build -t $DOCKER_REPO$/$PROJECT$:$VERSION$ .
docker push $DOCKER_REPO$/$PROJECT$:$VERSION$
echo "Build complete!"
```

## Logging

The runner uses Python's `logging` module at DEBUG level. You'll see output like:

```
12:34:56 [DEBUG] Launched: ['echo', 'Building', 'myapp', 'version', '1.0.0']
12:34:57 [DEBUG] Launched: ['mkdir', '-p', './build']
```

## Error Handling

- **Missing Stepfile**: Exits with code 100
- **Other errors**: Exits with code 1

## Security Notes

- Commands are parsed with `shlex` to prevent shell injection
- `shell=False` is used in subprocess calls
- No arbitrary shell execution

## Limitations

- Variable syntax uses `$VAR$` (not `${VAR}` or `$VAR`) to avoid conflicts
- No conditional execution or loops (use Python for complex logic)
- Commands run with `shell=False`, so shell features like pipes (`|`) won't work directly

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please submit pull requests or open issues for bugs and feature requests.
