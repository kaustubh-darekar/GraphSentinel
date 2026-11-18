// Store a Data item's embedding as a vector property (indexed by data_vec).
MATCH (d:Data {id: $id})
SET d.embedding = vector($embedding, $dims, FLOAT32), d.embedder = $embedder
