from setuptools import setup


ver_dic = {}
version_file = open("luadoc/version.py")
try:
    version_file_contents = version_file.read()
finally:
    version_file.close()

exec(compile(version_file_contents, "luadoc/version.py", 'exec'), ver_dic)


setup(
    name='luadoc',
    version=ver_dic["__version__"],
    description='A lua ldoc tool in Python !',
    url='https://github.com/boolangery/py-lua-doc',
    download_url='https://github.com/boolangery/py-lua-doc/archive/' + ver_dic["__version__"] + '.tar.gz',
    author='Eliott Dumeix',
    author_email='eliott.dumeix@gmail.com',
    license='GNU',
    packages=['luadoc', 'luadoc.tests'],
    zip_safe=False,
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
    install_requires=[
        'luaparser>=3.2.1', 'parsimonious'
    ],
    entry_points={
        'console_scripts': [
            'luadoc = luadoc.__main__:main'
        ]
    },
    include_package_data=True
)