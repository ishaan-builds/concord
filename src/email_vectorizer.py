from .agentmail_client import Message
from chromadb import Collection
from dataclasses import asdict

def get_metadata(msg: Message) -> dict:
    metadata = asdict(msg)
    del metadata['body']
    del metadata['id']
    return metadata

def store_msg(collection: Collection, msg: Message):
    collection.add(
        ids=msg['id'],
        documents=[msg['body']],
        metadatas=[get_metadata(msg)]
    )
