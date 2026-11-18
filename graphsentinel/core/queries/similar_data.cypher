// Vector search: Data in this session closest in meaning to $q. score = (1 + cosine) / 2.
MATCH (d:Data)
SEARCH d IN (VECTOR INDEX data_vec FOR vector($q, $dims, FLOAT32) WHERE d.session = $session LIMIT 5)
SCORE AS score
RETURN d.id AS id, score
