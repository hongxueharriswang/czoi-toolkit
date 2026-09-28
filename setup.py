from setuptools import find_packages, setup

setup(
    name="czoi-toolkit",
    version="1.0.0",
    description="Constrained Zoned-Object Architecture (CZOA) implementation",
    author="Harris Wang",
    packages=find_packages(exclude=["tests", "examples"]),
    python_requires=">=3.9",
    install_requires=[
        "unilog-toolkit>=2.0",
        "numpy>=1.19",
    ],
    extras_require={
        "neural": ["scikit-learn>=1.0"],
        "embedding": ["sentence-transformers"],
        "tree": ["networkx>=2.6"],
        "dev": ["pytest>=7.0", "pytest-asyncio"],
    },
)