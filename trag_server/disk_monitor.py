import os
import sqlite3
import hashlib
import threading
import time
import logging
from .sql_database import insert_document, get_connection
from .vector_storage import get_container
from .utils import DOCUMENTS_DIR, create_embeddings, split_text_into_chunks
from dataclasses import dataclass, field
from pdfminer.high_level import extract_text
import io
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ingest_document_running = False

main_faiss_container = None

from bs4 import BeautifulSoup  # Import BeautifulSoup

def extract_text_from_html(path):
    with open(path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text()

def extract_text_by_file_type(doc_path):
    if doc_path.endswith('.pdf'):
        return extract_text(doc_path)  # Assuming extract_text is for PDFs
    elif doc_path.endswith('.html'):
        return extract_text_from_html(doc_path)
    elif doc_path.endswith('.md') or doc_path.endswith('.txt'):
        with open(doc_path, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        return None

def ingest_document(doc_id, doc_name):
    global ingest_document_running
    ingest_document_running = True
    conn = get_connection()
    c = conn.cursor()
    c.execute("update Document set status='in progress' where id=?", (doc_id,))
    conn.commit()
    doc_path = os.path.join(DOCUMENTS_DIR, doc_name)
    
    # Use the new function to extract text based on file type
    doc_text = extract_text_by_file_type(doc_path)
    
    if not doc_text or len(doc_text) < 10:
        ingest_document_running = False
        logger.info("Document does not contain enough text")
        return
    
    doc_chunks = split_text_into_chunks(doc_text)
    doc_embeddings = create_embeddings(doc_chunks)
    prev_highest_index = main_faiss_container.size()
    main_faiss_container.add_embeddings(doc_embeddings)
    inserts = []
    for i in range(len(doc_chunks)):
        doc_chunk = doc_chunks[i].replace("\"", "\"\"")
        inserts.append((doc_id, prev_highest_index + i, doc_chunk))
    c.executemany("INSERT INTO Chunk (document_id, collection_slot_id, plaintext) VALUES (?, ?, ?)", inserts)
    conn.commit()
    c.execute("update Document set status='done' where id=?", (doc_id,))
    conn.commit()
    c.close()
    conn.close()
    ingest_document_running = False
    logger.info(f'Finished ingesting document: {doc_name}')

def calculate_md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as afile:
        buf = afile.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_document_names(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM Document")
    rows = c.fetchall()
    c.close()
    return [row[0] for row in rows]

def check_new_docs():
    conn = get_connection()
    while True:
        db_docs = set(get_document_names(conn))

        dir_docs = set([d for d in os.listdir(DOCUMENTS_DIR) if d[-(len(d)-d.rfind(".")):] in [".txt",".md",".html",".pdf"]])

        new_docs = dir_docs - db_docs

        if new_docs:
            logger.info(f'Un-vectorized docs: {new_docs}.')

        for doc_name in new_docs:
            checksum = calculate_md5(os.path.join(DOCUMENTS_DIR, doc_name))

            c = conn.cursor()
            c.execute("SELECT 1 FROM Document WHERE checksum = ?", (checksum,))
            if c.fetchone() is None:
                logger.info(f'New doc to add: {doc_name}.')
                insert_document(conn, 1, doc_name, checksum)
            c.close()
        time.sleep(5)

def run_ingest_document():
    global ingest_document_running
    conn = get_connection()
    while True:
        if not ingest_document_running:
            c = conn.cursor()
            c.execute("SELECT id, name FROM Document WHERE status='not started' LIMIT 1")
            row = c.fetchone()
            c.close()
            if row is not None:
                doc_id = row[0]
                doc_name = row[1]
                ingest_document_running = True
                threading.Thread(target=ingest_document, args=(doc_id, doc_name,)).start()
                logger.info(f'Ingesting new document: {doc_name}')
        time.sleep(5)

def start_disk_monitor():
    global main_faiss_container
    main_faiss_container = get_container("main")

    t1 = threading.Thread(target=check_new_docs)
    t1.daemon = True
    t1.start()

    t2 = threading.Thread(target=run_ingest_document)
    t2.daemon = True
    t2.start()
