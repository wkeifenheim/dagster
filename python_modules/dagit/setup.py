import os

from setuptools import find_packages, setup


def long_description():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, "README.rst"), "r") as fh:
        return fh.read()


def get_version():
    version = {}
    with open("dagit/version.py") as fp:
        exec(fp.read(), version)  # pylint: disable=W0122

    return version["__version__"]


if __name__ == "__main__":
    ver = get_version()
    # dont pin dev installs to avoid pip dep resolver issues
    pin = "" if ver == "dev" else f"=={ver}"
    setup(
        name="dagit",
        version=ver,
        author="Elementl",
        author_email="hello@elementl.com",
        license="Apache-2.0",
        description="Web UI for dagster.",
        long_description=long_description(),
        long_description_content_type="text/markdown",
        url="https://github.com/dagster-io/dagster",
        classifiers=[
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: OS Independent",
        ],
        packages=find_packages(exclude=["dagit_tests"]),
        include_package_data=True,
        install_requires=[
            "PyYAML",
            # cli
            "click>=7.0,<9.0",
            f"dagster{pin}",
            f"dagster-graphql{pin}",
            # server
            "flask-cors>=3.0.6",
            "Flask-GraphQL>=2.0.0",
            "Flask-Sockets>=0.2.1",
            # https://github.com/dagster-io/dagster/issues/4167
            "flask>=0.12.4,<2.0.0",
            "gevent-websocket>=0.10.1",
            "gevent",
            "graphql-ws>=0.3.0,<0.4.0",
            "requests",
            # watchdog
            "watchdog>=0.8.3",
            # https://github.com/dagster-io/dagster/issues/4167
            "Werkzeug<2.0.0",
            # notebooks support
            "nbconvert>=5.4.0,<6.0.0",
        ],
        extras_require={
            "starlette": [
                "starlette",
                "uvicorn[standard]",
                "gunicorn",
            ],
            "test": [
                "types-Flask",  # version will be resolved against flask
            ],
        },
        entry_points={
            "console_scripts": ["dagit = dagit.cli:main", "dagit-debug = dagit.debug:main"]
        },
    )
