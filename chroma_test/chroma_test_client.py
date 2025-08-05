import chromadb

chroma_client = chromadb.Client()

collection = chroma_client.create_collection(name="my_collection")

collection.add(
    ids=["id1", "id2", "id3", "id4", "id5", "id6", "id7", "id8"
         ],
    documents=[
        "This is a document about pineapple",
        "This is a document about oranges",
        "This is a document about roads",
        "This is a document about space",
        "This is a document about cars",
        "This is a document about ship",
        "This is a document about dishes",
        "This is a document about countries"
    ]
)

results = collection.query(
    query_texts=["This is a query document about Turkey"],  # Chroma will embed this for you
    n_results=8
)
print(results)
