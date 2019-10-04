--- @module our_module
local e = {}

--- Report a script error
--- <more info>
--- @function report_error
local report_error = function ()
end

e = {
  report_error = report_error,
}

return e
