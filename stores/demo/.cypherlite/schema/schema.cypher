CREATE RANGE INDEX `call_session` FOR (n:`Call`) ON (n.`session`);
CREATE RANGE INDEX `data_session` FOR (n:`Data`) ON (n.`session`);
CREATE VECTOR INDEX `data_vec` FOR (n:`Data`) ON (n.`embedding`) WITH [n.`session`] OPTIONS {indexConfig: {`vector.default_search_expansion_factor`: 3.0,`vector.hnsw.ef_construction`: 100,`vector.hnsw.m`: 16,`vector.quantization.type`: 'BINARY',`vector.similarity_function`: 'COSINE'}};
CREATE CONSTRAINT `call_id` FOR (n:`Call`) REQUIRE (n.`id`) IS UNIQUE;
CREATE CONSTRAINT `data_id` FOR (n:`Data`) REQUIRE (n.`id`) IS UNIQUE;
CREATE CONSTRAINT `destination_address` FOR (n:`Destination`) REQUIRE (n.`address`) IS UNIQUE;
CREATE CONSTRAINT `server_name` FOR (n:`Server`) REQUIRE (n.`name`) IS UNIQUE;
CREATE CONSTRAINT `session_id` FOR (n:`Session`) REQUIRE (n.`id`) IS UNIQUE;
CREATE CONSTRAINT `tool_name` FOR (n:`Tool`) REQUIRE (n.`name`) IS UNIQUE;
