from setuptools import setup
import luadoc

setup(
    name='luadoc',
    version=luadoc.__version__,
    description='A lua ldoc tool in Python !',
    url='https://github.com/boolangery/py-lua-doc',
    download_url='https://github.com/boolangery/py-lua-style/archive/' + luadoc.__version__ + '.tar.gz',
    author='Eliott Dumeix',
    author_email='eliott.dumeix@gmail.com',
    license='MIT',
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
    install_requires=[],
    entry_points={
        'console_scripts': [
            'luadoc = luadoc.__main__:main'
        ]
    }
)