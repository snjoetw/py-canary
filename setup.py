import setuptools

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="py-canary",
    version="0.5.2",
    author="snjoetw",
    author_email="snjoetw@gmail.com",
    packages=["canary"],
    description="Python API for Canary Security Camera",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/snjoetw/py-canary",
    license="MIT",
    python_requires=">=3.6",
    install_requires=["requests"],
)
