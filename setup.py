from setuptools import setup

setup(
    name='bjsparser',
    version='1.0',
    install_requires=[
        "requests >= 2.22.0"
    ],
    author="Austin Noto-Moniz",
    author_email="metalnut4@netscape.net",
    packages=['bjsparserlib'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
    ]
)
