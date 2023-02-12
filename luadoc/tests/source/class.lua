----------------------
--- a module containing some classes.
--- @module classes

local _M = {}

---- a useful class.
--- a long desc on
--- several lines
--- @class Bonzo
---@field public some_public_field string This field is private
---@field private _some_private_field string This field is private

_M.Bonzo = class()

--- a method.
--- function one; reference to @{one.md.classes|documentation}
function Bonzo:one()

end

--- a metamethod
--- function __tostring
function Bonzo:__tostring()

end

---Append the private field with `private`
function Bonzo:_more_private()
    self._some_private_field = self._some_private_field .. "private"
end

return M