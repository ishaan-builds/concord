import chromadb

client = chromadb.PersistentClient(path='./db/')
# collection = client.get_collection('51dca7bc')
# collection = client.get_collection('87c01d43')
# collection = client.get_collection('e2da0210')
collection = client.get_collection('b0a1b470')

def print_documents():
    for document in collection.get()['documents']:
        print(document + "\n-----")

def add_document():
    collection.add(ids=['0'], documents=["document 0"], metadatas={'metadata0': "md0"})

def clear_collection():
    collection.delete(collection.get()['ids'])

def clear_db():
    client.reset()

def main():
    # clear_collection()
    # clear_collection()
    print_documents()

if __name__ == "__main__":
    main()