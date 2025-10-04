from setuptools import setup, find_packages

setup(
    name="stepfile-runner",
    version="0.2.0",
    description="A Pythonic stepfile runner that executes commands from a configuration file.",
    long_description=open("README.md").read() if open("README.md") else "",
    long_description_content_type="text/markdown",
    author="ZaiperUnbound",
    author_email="altheahueteah@gmail.com",
    url="https://github.com/dreamingcuriosity/stepfile-runner",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "stepfile-runner=stepfile_runner:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # or whatever license you want
        "Operating System :: OS Independent",
    ],
)
