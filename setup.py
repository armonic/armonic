# (c) 2010-2013 Mandriva, http://www.mandriva.com/
#
# This file is part of Mandriva Server Setup
#
# MSS is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# MSS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MSS; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

from setuptools import setup, find_packages

setup(
    name='mss',
    version='3.0.1',
    description="Mandriva Server Setup",
    author="Antoine Eiche, Jean-Philippe Braun",
    author_email="aeiche@mandriva.com, eon@patapon.info",
    maintainer="Jean-Philippe Braun",
    maintainer_email="jpbraun@mandriva.com",
    url="http://www.mandriva.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=['netifaces', 'lxml']
)
