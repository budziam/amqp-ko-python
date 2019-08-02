from setuptools import setup

setup(
    name="amqp_ko",
    version="1.0.0",
    url="https://github.com/budziam/amqp-ko-python",
    license="MIT",
    packages=["amqp_ko"],
    install_requires=[
        "aio-pika",
        "asyncio",
        "cached-property",
        "python-dateutil",
        "pika",
    ],
    python_requires=">=3.7",
)
