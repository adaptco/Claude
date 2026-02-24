"""
Setup script for Google Cloud Industry Discovery Agent
"""

from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="gcp-industry-discovery-agent",
    version="1.0.0",
    description="Google Cloud Industry Discovery Agent using Vertex AI",
    author="Google Cloud",
    python_requires=">=3.9",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gcp-discovery-agent=google_cloud_agent.agent:main",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ]
)
