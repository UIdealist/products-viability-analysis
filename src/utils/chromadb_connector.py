# try:
#     import google.protobuf.message_factory as message_factory_module
#     if hasattr(message_factory_module, 'GetMessageClass'):
#         GetMessageClass = message_factory_module.GetMessageClass
#         MessageFactory = message_factory_module.MessageFactory
#         if not hasattr(MessageFactory, 'GetPrototype'):
#             def GetPrototype(self, descriptor):
#                 return GetMessageClass(descriptor)
#             MessageFactory.GetPrototype = GetPrototype
# except Exception:
#     pass

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Union
import numpy as np
from pathlib import Path
import os

class ChromaDBConnector:
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "default",
        host: Optional[str] = None,
        port: Optional[int] = None
    ):
        if persist_directory is None:
            if os.name == 'nt':
                persist_directory = "D:\\Maestría\\Amazon Reviews Code\\data\\chromadb"
            else:
                persist_directory = "/mnt/d/Maestría/Amazon Reviews Code/data/chromadb"
        
        os.makedirs(persist_directory, exist_ok=True)
        
        if host and port:
            self.client = chromadb.HttpClient(host=host, port=port)
        else:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
        
        self.collection_name = collection_name
        self.collection = None
        self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except:
            self.collection = self.client.create_collection(name=self.collection_name)
    
    def add_vectors(
        self,
        ids: List[str],
        embeddings: Union[List[List[float]], np.ndarray],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None
    ):
        if isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        
        if metadatas is None:
            metadatas = [{}] * len(ids)
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
    
    def add_vectors_batch(
        self,
        ids: List[str],
        embeddings: Union[List[List[float]], np.ndarray],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
        batch_size: int = 1000
    ):
        if isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        
        if metadatas is None:
            metadatas = [{}] * len(ids)
        
        total = len(ids)
        for i in range(0, total, batch_size):
            end_idx = min(i + batch_size, total)
            batch_ids = ids[i:end_idx]
            batch_embeddings = embeddings[i:end_idx]
            batch_metadatas = metadatas[i:end_idx] if metadatas else None
            batch_documents = documents[i:end_idx] if documents else None
            
            self.collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                documents=batch_documents
            )
    
    def similarity_search(
        self,
        query_embeddings: Union[List[List[float]], np.ndarray, List[float]],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ):
        if isinstance(query_embeddings, np.ndarray):
            if query_embeddings.ndim == 1:
                query_embeddings = [query_embeddings.tolist()]
            else:
                query_embeddings = query_embeddings.tolist()
        elif isinstance(query_embeddings[0], (int, float)):
            query_embeddings = [query_embeddings]
        
        results = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document
        )
        
        return results
    
    def similarity_search_batch(
        self,
        query_embeddings: Union[List[List[float]], np.ndarray],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        batch_size: int = 100
    ):
        if isinstance(query_embeddings, np.ndarray):
            query_embeddings = query_embeddings.tolist()
        
        all_results = {
            'ids': [],
            'distances': [],
            'metadatas': [],
            'documents': []
        }
        
        total = len(query_embeddings)
        for i in range(0, total, batch_size):
            end_idx = min(i + batch_size, total)
            batch_queries = query_embeddings[i:end_idx]
            
            results = self.collection.query(
                query_embeddings=batch_queries,
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            for key in all_results.keys():
                if key in results and len(results[key]) > 0:
                    if isinstance(results[key][0], list):
                        all_results[key].extend(results[key])
                    else:
                        all_results[key].append(results[key])
        
        return all_results
    
    def get_by_ids(self, ids: List[str]):
        return self.collection.get(ids=ids)
    
    def delete_by_ids(self, ids: List[str]):
        self.collection.delete(ids=ids)
    
    def update_vectors(
        self,
        ids: List[str],
        embeddings: Optional[Union[List[List[float]], np.ndarray]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None
    ):
        if embeddings is not None and isinstance(embeddings, np.ndarray):
            embeddings = embeddings.tolist()
        
        self.collection.update(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
    
    def count(self) -> int:
        return self.collection.count()
    
    def reset_collection(self):
        try:
            self.client.delete_collection(name=self.collection_name)
        except:
            pass
        self._get_or_create_collection()
    
    def get_collection_info(self) -> Dict[str, Any]:
        count = self.collection.count()
        return {
            'name': self.collection_name,
            'count': count
        }

