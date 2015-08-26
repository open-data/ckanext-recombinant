from setuptools import setup, find_packages
import sys, os

version = '1.0.0dev'

setup(
    name='ckanext-recombinant',
    version=version,
    description="Create datastore tables for organizations and "
        "provide combined output",
    long_description="""
    """,
    classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='Government of Canada',
    author_email='Michel.Gendron@statcan.gc.ca',
    url='',
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['ckanext'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # -*- Extra requirements: -*-
    ],
    entry_points=\
    """
    [ckan.plugins]
    recombinant=ckanext.recombinant.plugins:RecombinantPlugin

    [paste.paster_command]
    recombinant=ckanext.recombinant.commands:TableCommand
    """,
)
