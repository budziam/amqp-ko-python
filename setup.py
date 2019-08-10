#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from setuptools import setup

__version__ = "1.0.1"

if sys.argv[-1] == "publish":
    os.system("python setup.py sdist")
    os.system("twine upload dist/*")
    os.system("git tag -a %s -m 'version %s'" % (__version__, __version__))
    os.system("git push --tags")
    sys.exit()

setup(
    name="amqp-ko",
    packages=["amqp-ko"],
    version=__version__,
    license="MIT",
    description="Object oriented AMQP layer for microservices communication.",
    author="Michał Budziak",
    author_email="michal.mariusz.b@gmail.com",
    url="https://github.com/budziam/amqp-ko-python",
    download_url="https://github.com/budziam/amqp-ko-python/archive/%s.tar.gz" % __version__,
    keywords=["amqp-ko", "amqp", "microservice", "rabbitmq", "queue", "tools"],
    install_requires=["aio-pika", "asyncio", "cached-property", "pika"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
    ],
    python_requires=">=3.7",
)
