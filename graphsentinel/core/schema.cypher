// Constraints and indexes. Idempotent: runs on every GraphStore start.
CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT call_id IF NOT EXISTS FOR (c:Call) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT data_id IF NOT EXISTS FOR (d:Data) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT tool_name IF NOT EXISTS FOR (t:Tool) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT server_name IF NOT EXISTS FOR (s:Server) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT destination_address IF NOT EXISTS FOR (d:Destination) REQUIRE d.address IS UNIQUE;
CREATE INDEX call_session IF NOT EXISTS FOR (c:Call) ON (c.session);
CREATE INDEX data_session IF NOT EXISTS FOR (d:Data) ON (d.session);
// Vector search over Data, filterable by session (paraphrase detection).
CREATE VECTOR INDEX data_vec IF NOT EXISTS FOR (d:Data) ON d.embedding WITH [d.session];
