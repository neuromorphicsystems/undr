import setuptools

with open('README.md') as file:
    long_description = file.read()

setuptools.setup(
    name='undr',
    version='0.0.6',
    url='https://github.com/neuromorphicsystems/undr',
    author='Alexandre Marcireau',
    author_email='alexandre.marcireau@gmail.com',
    description='Download and process Neuromorphic datasets',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'lzip>=1.0',
        'numpy>=1.20',
        'toml>=0.10',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
    packages=['undr'],
    package_data={
        '': ['*.json']
    })
