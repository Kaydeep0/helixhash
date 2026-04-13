from setuptools import setup, find_packages

setup(
    name="helixhash",
    version="0.1.1",
    author="Kirandeep Kaur",
    description="The Helix Hash Function — path integral of E = ΔI/A made computable",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
