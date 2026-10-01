from setuptools import setup

with open("README.rst", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pygnmi",
    packages=["pygnmi", "pygnmi.spec.v0100", "pygnmi.artefacts"],
    version="0.8.15",
    license="bsd-3-clause",
    description="Pure Python gNMI client to manage network functions and collect telemetry.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    author="Anton Karneliuk",
    author_email="anton@karneliuk.com",
    url="https://github.com/akarneliuk/pygnmi",
    download_url="https://github.com/akarneliuk/pygnmi/archive/v0.8.15.tar.gz",
    keywords=["gnmi", "automation", "grpc", "network"],
    python_requires=">=3.10",
    install_requires=["grpcio>=1.84.0", "protobuf>=7.35.1,<8", "cryptography", "dictdiffer"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "Operating System :: OS Independent",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    scripts=["scripts/pygnmicli"],
)
