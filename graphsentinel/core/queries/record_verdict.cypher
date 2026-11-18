// Store the guard's decision on the call.
MATCH (c:Call {id: $callId})
SET c.decision = $decision, c.reason = $reason, c.path = $path
