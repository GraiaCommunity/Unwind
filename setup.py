import setuptools

with open("README.rst", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name="graiax-mod-unwind",
    version="0.2.2",
    author="RF-Tar-Railt",
    author_email="rf_tar_railt@qq.com",
    description="A simple solution to analysis and extract information from traceback.",
    license='MIT',
    long_description=long_description,
    long_description_content_type="text/rst",
    url="https://github.com/GraiaCommunity/Unwind",
    packages=["graiax.mod.unwind"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    keywords=['traceback', 'exception', 'crash-report'],
    python_requires='>=3.8',
    project_urls={
        'Bug Reports': 'https://github.com/GraiaCommunity/Unwind/issues',
        'Source': 'https://github.com/GraiaCommunity/Unwind',
    },
)
