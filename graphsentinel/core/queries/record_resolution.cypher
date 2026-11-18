// How an Ask (or a Block override) was resolved: approved | denied | timeout | overridden.
MATCH (c:Call {id: $callId})
SET c.resolution = $resolution
