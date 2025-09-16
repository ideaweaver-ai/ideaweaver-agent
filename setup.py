#!/usr/bin/env python3
"""
Setup script for iagent.
"""

import os
import re
from setuptools import setup, find_packages

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

def get_version():
    """Get version from __init__.py file."""
    init_file = os.path.join(os.path.dirname(__file__), "src", "iagent", "__init__.py")
    with open(init_file, "r", encoding="utf-8") as f:
        content = f.read()
        version_match = re.search(r'^__version__ = [\'"]([^\'"]*)[\'"]', content, re.M)
        if version_match:
            return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

# Read requirements from pyproject.toml
def get_requirements():
    """Get requirements from pyproject.toml."""
    return [
        "huggingface-hub>=0.31.2",
        "requests>=2.32.3",
        "rich>=13.9.4",
        "jinja2>=3.1.4",
        "python-dotenv",
        "openai>=1.58.1",
        "litellm>=1.60.2",
        "pandas>=1.3.0",
        "python-dateutil>=2.8.0",
    ]

setup(
    name="iagent",
    version=get_version(),  # Read version from __init__.py
    author="Prashant Lakhera",
    author_email="plakhera@ideaweaver.ai",
    description="🤖 iagent: Intelligent Agents that Think in Code",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/iagent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.10",
    install_requires=get_requirements(),
    extras_require={
        "torch": [
            "torch",
            "transformers>=4.0.0",
            "accelerate",
        ],
        "gradio": [
            "gradio>=5.14.0",
        ],
        "all": [
            "iagent[torch,gradio]",
        ],
    },
    entry_points={
        "console_scripts": [
            "iagent=iagent.cli:main",
            "iagent-cicd-debug=iagent.cicd_debugger.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
