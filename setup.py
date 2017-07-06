from setuptools import setup, find_packages
import sys, os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()


version = '0.3'

install_requires = [
    'boto3',
    'click'
]

setup(name='auroraex',
    scripts=['bin/auroraex'],
    version=version,
    description="Command Line utility for Amazon Aurora.",
    long_description=README + '\n\n' + NEWS,
    classifiers=[
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    keywords='amazon aurora aws mysql',
    author='Hiroshi Toyama',
    author_email='toyama0919@gmail.com',
    url='https://github.com/toyama0919/auroraex',
    license='MIT',
    packages=find_packages('src'),
    package_dir = {'': 'src'},include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    entry_points={
        'console_scripts':
            ['auroraex=auroraex.commands:main']
    }
)
