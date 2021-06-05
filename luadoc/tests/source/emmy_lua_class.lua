---@class Request
---@field body string The contents of the request
---@field private headers string Request headers
Account = {}
Account.__index = Account

function Account:create(balance)
end

return Account
