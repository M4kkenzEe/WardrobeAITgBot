"""
Описание:
Этот модуль отвечает за векторизацию одежды и семантический поиск по описанию.
Использует LangChain + ChromaDB.

Выбор эмбеддингов:
Используется HuggingFaceEmbedding c моделью `all-MiniLM-L6-v2` как оптимальный баланс качество/скорость/вес. Модель обучена на парах семантических текстов и хорошо подходит для fashion-описаний.
"""
import logging

from chromadb import PersistentClient
from langchain.schema import Document

from typing import List, Dict
import os

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from database.sqlite_init import get_user_clothes

# Инициализация эмбеддингов
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Константы
VECTOR_DB_DIR = "lang_models/chroma_store"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def build_vector_store(user_id: int) -> None:
    """
    Создаёт Chroma-базу с эмбеддингами для гардероба конкретного юзера.
    Данные берутся напрямую из SQLite.
    """
    rows = get_user_clothes(user_id)

    documents = []
    for filename, description, season, sex, _ in rows:
        logging.info(f'Обрабатывается файл: {filename}, сезон: {season}, пол: {sex}')
        doc = Document(
            page_content=description,
            metadata={
                "filename": filename,
                "season": season,
                "sex": sex
            }
        )
        documents.append(doc)

    user_path = os.path.join(VECTOR_DB_DIR, str(user_id))
    os.makedirs(user_path, exist_ok=True)

    Chroma.from_documents(
        documents=documents,
        embedding=embedding_model,
        persist_directory=user_path
    ).persist()


def search_similar_items(user_id: int, prompt: str, top_k: int = 5) -> List[Dict]:
    """
    Ищет схожие вещи по текстовому запросу.
    Возвращает список dict с filename + score
    """
    user_path = os.path.join(VECTOR_DB_DIR, str(user_id))
    if not os.path.exists(user_path):
        raise ValueError("Векторная база не создана ")

    vectorstore = Chroma(
        persist_directory=user_path,
        embedding_function=embedding_model
    )

    results = vectorstore.similarity_search_with_score(prompt, k=top_k)

    return [
        {
            "filename": doc.metadata["filename"],
            "score": score
        }
        for doc, score in results
    ]


def inspect_chroma_db(collection_name: str = "clothes"):
    client = PersistentClient(path=f"storage/chroma_{collection_name}")
    collection = client.get_or_create_collection(name=collection_name)

    print(f"\n📊 Documents in ChromaDB Collection '{collection_name}':")
    items = collection.get()
    for idx, doc_id in enumerate(items.get("ids", [])):
        print(f"\n🔹 ID: {doc_id}")
        print(f"Metadata: {items.get('metadatas', [])[idx]}")
        print(f"Document Text: {items.get('documents', [])[idx]}")
