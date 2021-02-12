#!/usr/bin/env python3
from setuptools import setup, find_packages
import re
import os

version = re.search("__version__ = '([^']+)'", open(
    os.path.join(os.path.dirname(__file__), 'ansible_chroot/__init__.py')
).read().strip()).group(1)

setup(
    name='ansible-chroot',
    version=version,

    description="ansible-chroot",
    author="Tatsuo Nakajyo",
    author_email="tnak@nekonaq.com",
    license='BSD',
    packages=find_packages(),
    python_requires='~=3.6.9',
    entry_points={
        'console_scripts': [
            'ansible-chroot = ansible_chroot.cli.chroot:Command.main',
            'ansible-debootstrap = ansible_chroot.cli.debootstrap:Command.main',
        ]
    },
    scripts=[
        'ansible-chroot-manifest',
    ],
    install_requires=['ansible~=2.8.18'],
)

# Local Variables:
# compile-command: "python3 ./setup.py sdist"
# End:
