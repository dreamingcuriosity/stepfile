# Stepfile Runner

A Pythonic task runner that executes commands from a simple configuration file called a "Stepfile". Think of it as a lightweight alternative to Makefiles or shell scripts with built-in variable support.

## Features

- **Simple syntax**: Define variables and commands in a clean, readable format
- **Variable expansion**: Use `$VAR$` syntax to reference variables in commands
- **Shell environment variables**: Export variables to command environments with `.sh` suffix
- **Flexible execution**: Run commands sequentially or concurrently
- **Secure by default**: Uses `shlex` for proper command parsing and avoids shell injection

## Installation

```bash
pip install -e .
```

Or copy `stepfile_runner.py` to your project.

## Quick Start

Create a file named `Stepfile` in your project directory:

```
# Variables
PROJECT_NAME=myapp
VERSION=1.0.0
BUILD_DIR=./build

# Shell environment variable (exported to commands)
PYTHONPATH.sh=/opt/custom/lib

# Commands
echo "Building $PROJECT_NAME$ version $VERSION$"
mkdir -p $BUILD_DIR$
python -m pytest tests/
```

Run it:

```bash
python stepfile_runner.py
```

## Stepfile Syntax

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
