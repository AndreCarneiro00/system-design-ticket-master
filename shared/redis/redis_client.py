import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

DECREMENT_IF_AVAILABLE_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '-1')
local requested = tonumber(ARGV[1])

if current < 0 then
    return -2
end

if current < requested then
    return -1
end

return redis.call('DECRBY', KEYS[1], requested)
"""

INCREMENT_STOCK_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local quantity = tonumber(ARGV[1])
return redis.call('INCRBY', KEYS[1], quantity)
"""

decrement_if_available = redis_client.register_script(DECREMENT_IF_AVAILABLE_LUA)
increment_stock = redis_client.register_script(INCREMENT_STOCK_LUA)