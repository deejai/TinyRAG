import faiss
from .utils import combine_chunks, RAG_NUM_ADJACENT_CHUNKS
from .vector_storage import FAISS_Container, get_container


def search(collection_names: list[str], query: str, top_n: int):
    assert len(query) < 2000
    assert top_n >= 1 and top_n <= 100
    assert len(collection_names) > 0

    results = []

    for collection_name in collection_names:
        collection_container: FAISS_Container = get_container(collection_name)

        distances, indices = collection_container.search(query, top_n)

        for i in range(min(len(indices), top_n)):
            index_number = indices[i]
            score = distances[i]

            results.append((collection_container.collection_id, index_number, score))

    results.sort(key=lambda x: x[2], reverse=True)

    # TODO: could rerank here

    selected_results = results[:top_n]

    c = collection_container.conn.cursor()
    chunk_objs = []
    for result in selected_results:
        collection_id = result[0]
        collection_slot_id = result[1]
        similarity_score = result[2]
        query = f"""
            SELECT collection_slot_id, plaintext
            FROM Chunk
            WHERE document_id IN (
                SELECT id
                FROM Document
                WHERE collection_id = {collection_id}
            )
            AND collection_slot_id BETWEEN {collection_slot_id - RAG_NUM_ADJACENT_CHUNKS} AND {collection_slot_id + RAG_NUM_ADJACENT_CHUNKS}
        """

        c.execute(
            query
        )

        # with open("test", "w") as f:
        #     f.write()

        rows = c.fetchall()
        print(rows)

        new_chunk_objs = [{"id": row[0], "text": row[1]} for row in rows]
        chunk_objs.extend(new_chunk_objs)

    c.close()

    if len(chunk_objs) == 0:
        print("No chunk objects returned")
        return []

    unique_chunks = {c["id"]: c for c in chunk_objs}
    sorted_unique_chunks = sorted(unique_chunks.values(), key=lambda x: x["id"])

    # print(sorted_unique_chunks)

    chunks_to_be_combined = []
    formatted_results_sections = []
    for i in range(len(sorted_unique_chunks)):
        chunks_to_be_combined.append(sorted_unique_chunks[i]["text"])

        if (
            i == len(sorted_unique_chunks) - 1
            or sorted_unique_chunks[i + 1]["id"] > sorted_unique_chunks[i]["id"] + 1
        ):
            formatted_results_sections.append(combine_chunks(chunks_to_be_combined))
            chunks_to_be_combined = []

    return formatted_results_sections
