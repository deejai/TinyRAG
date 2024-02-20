import os
import faiss
import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch
import re
import inspect

TRAG_SERVER_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
ROOT_DIR = os.path.dirname(TRAG_SERVER_DIR)
VECTOR_DB_DIR = os.path.join(ROOT_DIR, "vector_store")
DOCUMENTS_DIR = os.path.join(ROOT_DIR, "docs")

RAG_CHUNK_SIZE = 25
RAG_CHUNK_OVERLAP = 6
RAG_MAX_CHUNK_LENGTH = RAG_CHUNK_SIZE * 100
RAG_NUM_ADJACENT_CHUNKS = 2

model_identifier = os.path.join(ROOT_DIR, "models", "all-MiniLM-L6-v2")
MODEL_VECTOR_SIZE = 384

tokenizer = None
model = None

# SPLIT_REGEX_STR = r"[^\S\n]"
SPLIT_REGEX_STR = r"\s"

def split_text_into_chunks(text, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP):
    # words = text.split()
    words = re.findall(r'\S+\s{0,10}', text)

    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = words[i:i+chunk_size]
        if len(chunk) > RAG_MAX_CHUNK_LENGTH:
            raise Exception(f"Chunk size too big. Total length: {len(chunk)}")
        chunks.append(''.join(chunk))
        # print(f"{i}, {i+chunk_size}")
    return chunks

def combine_chunks(chunks, overlap=RAG_CHUNK_OVERLAP):
    text = chunks[0]
    for chunk in chunks[1:]:
        match = re.search(r"\S+\s+"*(overlap), chunk)
        if match is None:
            continue
        nth_word_index = match.end()
        text += chunk[nth_word_index:]
    return text

def create_faiss_index_file(collection_name):
    file_path = os.path.join(VECTOR_DB_DIR, f"{collection_name}.index")

    if os.path.exists(file_path):
        raise Exception(f"File {file_path} already exists. Aborting FAISS index creation.")

    index = faiss.IndexFlatL2(MODEL_VECTOR_SIZE)
    faiss.write_index(index, file_path)

def load_model_and_tokenizer():
    global model
    global tokenizer

    if tokenizer is None:
        tokenizer = AutoTokenizer.from_pretrained(model_identifier)

    if model is None:
        model = AutoModel.from_pretrained(model_identifier)

def create_embeddings(chunks: list[str]) -> list[np.ndarray]:
    load_model_and_tokenizer()
    embeddings = []
    for chunk in chunks:
        inputs = tokenizer(chunk, return_tensors='pt', padding=True, truncation=True, max_length=RAG_MAX_CHUNK_LENGTH)
        with torch.no_grad():
            outputs = model(**inputs)
        embeddings.append(outputs.last_hidden_state[:, 0, :].numpy())

    return embeddings
