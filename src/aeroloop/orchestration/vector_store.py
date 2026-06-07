import chromadb
from chromadb.config import Settings
import os

class KnowledgeBase:
    """
    Singleton wrapper for ChromaDB vector store.
    Provides semantic search over requirements and certification clauses.
    """
    _instance = None

    def __new__(cls, persist_directory=".agents/vector_db"):
        if cls._instance is None:
            cls._instance = super(KnowledgeBase, cls).__new__(cls)
            cls._instance._init_db(persist_directory)
        return cls._instance

    def _init_db(self, persist_directory):
        os.makedirs(persist_directory, exist_ok=True)
        # Initialize PersistentClient
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Create or get collections
        self.requirements_collection = self.client.get_or_create_collection("requirements")
        self.certifications_collection = self.client.get_or_create_collection("certifications")

    def add_requirement(self, requirement_id: str, content: str, metadata: dict = None):
        if not metadata:
            metadata = {}
        self.requirements_collection.upsert(
            documents=[content],
            metadatas=[metadata],
            ids=[requirement_id]
        )

    def add_certification_clause(self, clause_id: str, content: str, metadata: dict = None):
        if not metadata:
            metadata = {}
        self.certifications_collection.upsert(
            documents=[content],
            metadatas=[metadata],
            ids=[clause_id]
        )

    def search_similar_requirements(self, query: str, n_results: int = 3):
        results = self.requirements_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def search_similar_certifications(self, query: str, n_results: int = 3):
        results = self.certifications_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results
