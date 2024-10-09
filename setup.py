#!/usr/bin/env python
import ast
import os

from setuptools import setup


here = os.path.dirname(__file__)
metadata = {}
with open(os.path.join(here, 'ghcloneall.py')) as f:
    for line in f:
        if line.startswith(('__author__ =',
                            '__licence__ =',
                            '__url__ =',
                            '__version__ =')):
            k, v = line.split('=', 1)
            metadata[k.strip()] = ast.literal_eval(v.strip())
with open(os.path.join(here, 'README.rst')) as f:
    long_description = f.read()
with open(os.path.join(here, 'CHANGES.rst')) as f:
    long_description += '\n\n' + f.read()

setup(
    name='ghcloneall',
    version=metadata['__version__'],
    author='Marius Gedminas',
    author_email='marius@gedmin.as',
    url=metadata['__url__'],
    description='Clone/update all user/organization GitHub repositories',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    keywords='github git clone automation',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    license='MIT',
    py_modules=['ghcloneall'],
    install_requires=[
        'requests',
        'requests_cache',
    ],
    entry_points={
        'console_scripts': [
            'ghcloneall = ghcloneall:main',
        ],
    },
    zip_safe=False,
)
