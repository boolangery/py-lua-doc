py-lua-doc
----------

A Lua documentation extraction tool written in Python that support emmy-lua and 
ldoc doc-comment.


Installation
------------

The package can be installed through `pip`:

.. code-block::

    $ pip3 install luadoc

It will install the shell command 'luadoc'.


Usage
-----

Given:

```lua
--- @class foo.Base
local Base = {}


--- @class foo.List: foo.Base
local List = {}

--- Apply a function to all elements.
--- Any extra arguments will be passed to the function.
--- @param fun fun(a:any):any a function of at least one argument
--- @vararg any @arbitrary extra arguments.
--- @return foo.List a new list: {f(x) for x in self}
function List:map(fun, ...) end

--- Split a string using a delim.
--- @param delim string the delim (default " ")
--- @overload fun()
function List:split(delim) end


return List
```

```bash
$ luadoc source.lua
```

The following output will be produced:

```json
[
    {
        "classes": [
            {
                "name": "foo.Base",
                "name_in_source": "Base",
                "methods": [],
                "desc": "",
                "usage": "",
                "inherits_from": [],
                "fields": []
            },
            {
                "name": "foo.List",
                "name_in_source": "List",
                "methods": [
                    {
                        "name": "map",
                        "short_desc": "Apply a function to all elements.",
                        "desc": "Any extra arguments will be passed to the function.",
                        "params": [
                            {
                                "name": "fun",
                                "desc": "a function of at least one argument",
                                "type": {
                                    "id": "callable",
                                    "arg_types": [
                                        {
                                            "id": "any"
                                        }
                                    ],
                                    "return_types": [
                                        {
                                            "id": "any"
                                        }
                                    ]
                                },
                                "is_opt": false
                            },
                            {
                                "name": "...",
                                "desc": "arbitrary extra arguments.",
                                "type": {
                                    "id": "any"
                                },
                                "is_opt": false
                            }
                        ],
                        "returns": [
                            {
                                "desc": "a new list: {f(x) for x in self}",
                                "type": {
                                    "id": "custom",
                                    "name": "foo.List"
                                }
                            }
                        ],
                        "usage": "",
                        "is_virtual": false,
                        "is_abstract": false,
                        "is_deprecated": false,
                        "is_static": false,
                        "visibility": "public"
                    },
                    {
                        "name": "split",
                        "short_desc": "Split a string using a delim.",
                        "desc": "",
                        "params": [
                            {
                                "name": "delim",
                                "desc": "the delim (default \" \")",
                                "type": {
                                    "id": "string"
                                },
                                "is_opt": false
                            }
                        ],
                        "returns": [],
                        "usage": "",
                        "is_virtual": false,
                        "is_abstract": false,
                        "is_deprecated": false,
                        "is_static": false,
                        "visibility": "public"
                    },
                    {
                        "name": "split",
                        "short_desc": "Split a string using a delim.",
                        "desc": "",
                        "params": [],
                        "returns": [],
                        "usage": "",
                        "is_virtual": false,
                        "is_abstract": false,
                        "is_deprecated": false,
                        "is_static": false,
                        "visibility": "public"
                    }
                ],
                "desc": "",
                "usage": "",
                "inherits_from": [
                    "foo.Base"
                ],
                "fields": []
            }
        ],
        "functions": [],
        "name": "unknown",
        "isClassMod": false,
        "desc": "",
        "usage": ""
    }
]
```