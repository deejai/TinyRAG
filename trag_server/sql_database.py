import sqlite3
import os
from .utils import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, ROOT_DIR

STATUS_STRING_NOT_STARTED = "not started"
STATUS_STRING_PROCESSING = "processing"
STATUS_STRING_DONE = "done"

def get_connection():
    conn = sqlite3.connect(os.path.join(ROOT_DIR, "trag.sqlite3"))
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS Collection (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS Document (
            id INTEGER PRIMARY KEY,
            name TEXT,
            checksum TEXT,
            collection_id INTEGER,
            start_index INTEGER NOT NULL,
            end_index INTEGER NOT NULL,
            chunk_size INTEGER NOT NULL,
            chunk_overlap INTEGER NOT NULL,
            status TEXT,
            FOREIGN KEY(collection_id) REFERENCES Collection(id)
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS Chunk (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            collection_slot_id INTEGER NOT NULL,
            plaintext TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES Document(id)
        )
    """
    )

    c.execute(
        '''
        INSERT INTO Collection (id, name, description)
        SELECT 1, "main", "the main faiss index"
        WHERE NOT EXISTS(SELECT 1 FROM Collection WHERE name = "main")
        '''
    )

    c.execute("update Document set status='not started' where status='in progress'")

    conn.commit()
    c.close()
    conn.close()

def insert_document(conn, collection_id, document_name, checksum):
    c = conn.cursor()
    c.execute("INSERT INTO Document (name, checksum, collection_id, start_index, end_index, chunk_size, chunk_overlap, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
          (document_name, checksum, collection_id, -1, -1, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP, STATUS_STRING_NOT_STARTED))
    conn.commit()
    c.close()
