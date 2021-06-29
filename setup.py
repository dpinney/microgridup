''' Install microgridup.
 usage: `python setup.py develop`
 '''

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install
from subprocess import check_call

def pre_install():
	try:
		import omf
	except:
		check_call("git clone --depth=1 https://github.com/dpinney/omf.git".split())
		check_call("cd omf; python install.py".split())

class PreDevelopCommand(develop):
	def run(self):
		pre_install()
		develop.run(self)

class PreInstallCommand(install):
	def run(self):
		pre_install()
		install.run(self)

setup(
	name='microgridup',
	version='1.0',
	py_modules=['microgridup'],
	cmdclass={
		'develop':PreDevelopCommand,
		'install':PreInstallCommand
	}
)