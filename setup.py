"""
Setup script for Calorico Telegram Bot.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="calorico-bot",
    version="2.0.0",
    author="Calorico Team",
    author_email="contact@calorico.com",
    description="A smart Telegram bot for personalized nutrition management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/calorico/calorico-bot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Communications :: Chat",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pylint",
            "black",
            "autopep8",
            "pytest",
            "pytest-asyncio",
        ],
    },
    entry_points={
        "console_scripts": [
            "calorico-bot=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
) 