import setuptools

with open("description", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='Fugue-generator',
    author="Adam Bradley",
    author_email='adam_bradley@brown.edu',
    description='',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/brown-university-library/fugue',
    version='0.9a1',
    packages=setuptools.find_packages(),
    install_requires=[
        "certifi>=2018.8.24",
        "Click>=7.0",
        "lxml>=4.1.0",
        "markdown2==2.4.0",
        "pytidylib>=0.3.2",
        "PyYAML>=5.1",
        "urllib3>=1.25.3",
    ],
    package_data={
        # Include mimetypes data.
        '': ['mime.types'],
    },
    entry_points='''
        [console_scripts]
        fugue=fugue:fugue
    ''',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Text Processing :: Markup :: XML",
    ],
    python_requires='>=3.6',
)