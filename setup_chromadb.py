import chromadb

client = chromadb.PersistentClient(path='./db/')
email_collection = client.create_collection(name = 'Emails')