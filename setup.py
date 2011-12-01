#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name="jiracrawler",
    version="0.1",
    packages=find_packages(),
    namespace_packages=['jiracrawler'],
    install_requires=[
	'jirareports',
        'MySQL-python==1.2.2',
        'lockfile==0.8',
        'python-daemon==1.5.5',
        'sqlalchemy==0.7.3',
        'SOAPpy==0.12.5'
    ],
    dependency_links=[
        "https://github.com/aklochkovgd/jirareports/tarball/master#egg=jirareports"
    ],
    entry_points={
        'console_scripts': [
            'jiracrawler=jiracrawler.crawler:main'
        ]
    }
)
