
from trag_server.disk_monitor import start_disk_monitor
from trag_server.sql_database import init_db, get_connection, insert_document
from trag_server.utils import create_faiss_index_file
from trag_server.vector_storage import load_faiss_indices_into_memory
from trag_server.utils import load_model_and_tokenizer
from gui import get_app
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))

def run():
    if not os.path.isfile(os.path.join(ROOT_DIR, "vector_store", "main.index")):
        create_faiss_index_file("main")
    load_model_and_tokenizer()
    init_db()
    load_faiss_indices_into_memory()
    app = get_app()
    start_disk_monitor()
    app.mainloop()
    exit()

def main():
    run()

if __name__ == "__main__":
    main()
