from setuptools import setup, find_packages

setup(
    name='kvstore',
    version='1.0.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'kvstore-server=kvstore.cli.server_cli:main',
            'kvstore-client=kvstore.cli.client_cli:main',
        ],
    },
    python_requires='>=3.7',
)