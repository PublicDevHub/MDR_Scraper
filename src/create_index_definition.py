import json

INDEX_SCHEMA = {
  "name": "mdr-legal-index-v1",
  "fields": [
    { "name": "id", "type": "Edm.String", "key": True, "searchable": False },
    { "name": "title", "type": "Edm.String", "searchable": True, "analyzer": "de.microsoft" },
    { "name": "content", "type": "Edm.String", "searchable": True, "analyzer": "de.microsoft" },
    {
      "name": "contentVector",
      "type": "Collection(Edm.Single)",
      "searchable": True,
      "dimensions": 3072,
      "vectorSearchProfile": "my-vector-profile"
    },
    { "name": "source_type", "type": "Edm.String", "filterable": True, "facetable": True },
    { "name": "url", "type": "Edm.String", "retrievable": True },
    { "name": "chapter", "type": "Edm.String", "searchable": True, "filterable": True, "facetable": True, "analyzer": "de.microsoft" },
    { "name": "valid_from", "type": "Edm.DateTimeOffset", "filterable": True, "sortable": True }
  ],
  "semantic": {
    "configurations": [
      {
        "name": "my-semantic-config",
        "prioritizedFields": {
          "titleField": { "fieldName": "title" },
          "contentFields": [{ "fieldName": "content" }],
          "keywordsFields": [{ "fieldName": "chapter" }]
        }
      }
    ]
  },
  "vectorSearch": {
    "algorithms": [{ "name": "hnsw-config", "kind": "hnsw", "hnswParameters": { "m": 4, "efConstruction": 400, "efSearch": 500, "metric": "cosine" }}],
    "profiles": [{ "name": "my-vector-profile", "algorithm": "hnsw-config" }]
  }
}

def get_index_schema():
    return INDEX_SCHEMA

if __name__ == "__main__":
    print(json.dumps(INDEX_SCHEMA, indent=2))
