--- @module pl.stringx
local stringx = {}

--- @class pl.List
local List = {}

function List:new(size) end

--- does s only contain alphabetic characters?
--- @param s string a string
--- @return boolean
function stringx.isalpha(s) end

--- does s only contain digits?
--- @param s string a string
--- @return boolean
function stringx.isdigit(s) end

return stringx
