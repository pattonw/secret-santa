from setuptools import setup, find_packages

setup(
    name="ss",
    version="0.1",
    url="https://github.com/pattonw/secret-santa",
    author="William Patton",
    author_email="pattonw@janelia.hhmi.org",
    license="MIT",
    packages=find_packages(),
    entry_points="""
            [console_scripts]
            secret-santa=ss.cli:cli
        """,
    include_package_data=True,
    install_requires=[
        "mip",
        "cryptography",
        "click",
        "omegaconf"
    ]
)