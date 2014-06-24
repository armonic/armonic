import os.path
from setuptools import setup, find_packages

install_requires = [
    'netifaces',
    'lxml',
    'IPy',
    'MySQL-python',
    'argcomplete',
    'prettytable',
    'nose',
    'termcolor',
    'sleekxmpp'
]

setup(
    name='armonic',
    version='0.1a',
    description="Armonic",
    author="Antoine Eiche, Jean-Philippe Braun",
    author_email="aeiche@mandriva.com, eon@patapon.info",
    maintainer="Jean-Philippe Braun",
    maintainer_email="eon@patapon.info",
    url="http://www.github.com/armonic",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    scripts=[
        os.path.join('bin', 'armonic-agent-socket'),
        os.path.join('bin', 'armonic-cli'),
        os.path.join('bin', 'smartonic'),
        os.path.join('bin', 'armonic-xmpp-master'),
    ],
    license="GPLv2",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Clustering',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Software Distribution'
    ],
    test_suite='nose.collector'
)
