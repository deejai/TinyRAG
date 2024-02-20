import faiss
import shutil
import numpy as np
import os
from .sql_database import get_connection
from .utils import create_embeddings, VECTOR_DB_DIR
from sqlite3 import Connection
from threading import Lock

faiss_dict = {}

class FAISS_Container():
    index: faiss.Index
    modification_lock: Lock
    conn: Connection

    def __init__(self, index: faiss.Index, collection_id: int):
        self.index = index
        self.collection_id = collection_id
        self.modification_lock = Lock()
        self.conn = get_connection()
        c = self.conn.cursor()
        c.execute(f"SELECT name FROM collection where id={collection_id} limit 1")
        self.collection_name = c.fetchone()[0]
        c.close()
        super().__init__()

    def search(self, query: str, top_n: int) -> (list[float], list[int]):
        if self.index.ntotal == 0:
            print(f"Index is empty. Collection id: {self.collection_id}, name: {self.collection_name}")
            return [], []
 
        query_embeddings = np.vstack(create_embeddings([query]))
        # print(query_embeddings)
        with self.modification_lock:
            D, I = self.index.search(query_embeddings, top_n*2)
        print(f"Searched {self.index.ntotal} embeddings and returned {len(I[0])} results.")
        return D[0], I[0]

    def add_embeddings(self, embeddings: list[np.ndarray]):
        # TODO: Get more granular for better scaling? Copying the whole index could take a lot of time
        with self.modification_lock:
            embeddings = np.vstack(embeddings)
            self.index.add(embeddings)
            temp_save_location = os.path.join(VECTOR_DB_DIR, f"{self.collection_name}.index.tmp")
            perm_save_location = os.path.join(VECTOR_DB_DIR, f"{self.collection_name}.index")
            faiss.write_index(self.index, temp_save_location)
            shutil.copyfile(temp_save_location, perm_save_location)
            os.remove(temp_save_location)

    def size(self) -> int:
        return self.index.ntotal

def load_faiss_indices_into_memory():
    print("Loading faiss files into memory...")
    global faiss_dict

    conn = get_connection()
    c = conn.cursor()
    c.execute(f"SELECT id, name FROM Collection")
    collection_rows = c.fetchall()

    for collection_row in collection_rows:
        collection_id = collection_row[0]
        collection_name = collection_row[1]
        index_path = os.path.join(VECTOR_DB_DIR, f'{collection_name}.index')
        index = faiss.read_index(index_path)
        faiss_dict[collection_name] = FAISS_Container(index=index, collection_id=collection_id)
        print("\tDone.")

    print("Faiss indices loaded.")
    print(faiss_dict)
    c.close()
    conn.close()

def get_container(collection_name) -> FAISS_Container:
    return faiss_dict[collection_name]
