import setuptools


setuptools.setup(
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
)
