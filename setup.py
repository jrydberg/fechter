from setuptools import setup, find_packages
setup(name='fechter',
      version='0.0.4',
      description='a simple high-availability manager',
      author='Johan Rydberg',
      author_email='johan.rydberg@gmail.com',
      url='http://github.com/jrydberg/fechter',
      packages=find_packages() + ['twisted.plugins'],
      scripts=['bin/fechter']
)
