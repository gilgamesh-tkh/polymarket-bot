# Package setup for Polymarket Smart Money Detection

from setuptools import setup, find_packages
import os

# Read README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="polymarket-smart-money-detection",
    version="1.0.0",
    author="Bachelor 3 AI & Big Data Project",
    author_email="student@example.com",
    description="Smart Money Detection System for Polymarket using warproxxx/poly_data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/polymarket-smart-money-detection",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "pre-commit>=3.3.0",
        ],
        "big-data": [
            "apache-spark>=3.4.0",
            "kubernetes>=28.0.0",
            "redis>=4.6.0",
            "celery>=5.3.0",
        ],
        "api": [
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
            "sqlalchemy-utils>=0.41.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "polymarket-smart-money=src.visualization.dashboard.app:main",
            "data-ingestion=scripts.data_ingestion:main",
            "model-training=scripts.model_training:main",
            "analysis-runner=scripts.analysis_runner:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.txt"],
    },
    zip_safe=False,
    keywords="polymarket, smart-money, trading, blockchain, machine-learning, data-science",
    project_urls={
        "Bug Reports": "https://github.com/username/polymarket-smart-money-detection/issues",
        "Source": "https://github.com/username/polymarket-smart-money-detection",
        "Documentation": "https://github.com/username/polymarket-smart-money-detection/docs",
    },
)