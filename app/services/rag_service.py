"""
RAG (Retrieval-Augmented Generation) Service
Handles vector similarity search and knowledge retrieval
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import numpy as np

from app.db.session import SessionLocal
from app.models.faq import FAQ
from app.models.persona import Persona
from app.models.document import Document, DocumentChunk
from app.services.azure_openai import azure_openai_service

logger = logging.getLogger(__name__)


class RAGService:
    """
    Service for Retrieval-Augmented Generation using vector similarity search.
    """
    
    def __init__(self):
        """Initialize RAG service."""
        self.embedding_service = azure_openai_service
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0
            
            similarity = dot_product / (norm_v1 * norm_v2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def get_persona_prompt(self, persona_id: str, db: Session) -> Optional[str]:
        """
        Retrieve persona prompt by ID.
        
        Args:
            persona_id: UUID of the persona
            db: Database session
            
        Returns:
            Persona prompt text or None
        """
        try:
            persona = db.query(Persona).filter(
                and_(
                    Persona.id == persona_id,
                    Persona.deleted_at.is_(None)
                )
            ).first()
            
            if persona:
                logger.info(f"Retrieved persona: {persona.name}")
                return persona.prompt
            else:
                logger.warning(f"Persona not found: {persona_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving persona: {e}", exc_info=True)
            return None
    
    def search_similar_qna(
        self,
        question: str,
        dataset_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar QnA pairs using vector similarity.
        
        Args:
            question: User's question
            dataset_id: Dataset ID to filter knowledge base
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)
            db: Database session (optional, will create if None)
            
        Returns:
            List of similar QnA pairs with scores
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # Step 1: Generate embedding for user's question
            logger.info(f"Generating embedding for question: {question[:100]}...")
            question_embedding = self.embedding_service.generate_embedding(question)
            
            if not question_embedding:
                logger.error("Failed to generate question embedding")
                return []
            
            # Step 2: Retrieve all FAQs for the dataset with embeddings
            faqs = db.query(FAQ).filter(
                and_(
                    FAQ.dataset_id == dataset_id,
                    FAQ.embedding.isnot(None),
                    FAQ.deleted_at.is_(None)
                )
            ).all()
            
            if not faqs:
                logger.warning(f"No FAQs found for dataset: {dataset_id}")
                return []
            
            logger.info(f"Found {len(faqs)} FAQs in dataset {dataset_id}")
            
            # Step 3: Calculate similarity scores
            results = []
            for faq in faqs:
                if faq.embedding is not None:
                    # Convert pgvector Vector to list for compatibility
                    faq_embedding = list(faq.embedding) if not isinstance(faq.embedding, list) else faq.embedding
                    similarity = self.cosine_similarity(question_embedding, faq_embedding)
                    
                    if similarity >= similarity_threshold:
                        results.append({
                            "faq_id": str(faq.id),
                            "question": faq.question,
                            "answer": faq.answer,
                            "similarity_score": float(similarity),
                            "dataset_id": str(faq.dataset_id)
                        })
            
            # Step 4: Sort by similarity and get top_k
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            top_results = results[:top_k]
            
            logger.info(
                f"Found {len(top_results)} relevant FAQs "
                f"(threshold: {similarity_threshold}, top_k: {top_k})"
            )
            
            return top_results
            
        except Exception as e:
            logger.error(f"Error in similarity search: {e}", exc_info=True)
            return []
        finally:
            if close_db:
                db.close()
    
    def build_rag_context(
        self,
        question: str,
        dataset_id: str,
        top_k: int = 3,
        similarity_threshold: float = 0.7
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Build context for RAG from similar QnA pairs.
        
        Args:
            question: User's question
            dataset_id: Dataset ID for knowledge base
            top_k: Number of similar QnAs to include
            similarity_threshold: Minimum similarity score
            
        Returns:
            Tuple of (context_text, sources)
        """
        try:
            # Search for similar QnA
            similar_qnas = self.search_similar_qna(
                question=question,
                dataset_id=dataset_id,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            
            if not similar_qnas:
                logger.info("No similar QnAs found, returning empty context")
                return "", []
            
            # Build context from similar QnAs
            context_parts = ["Referensi dari Knowledge Base:"]
            sources = []
            
            for idx, qna in enumerate(similar_qnas, 1):
                context_parts.append(
                    f"\n{idx}. Q: {qna['question']}\n   A: {qna['answer']}"
                )
                
                sources.append({
                    "sourceId": qna["faq_id"],
                    "title": f"FAQ: {qna['question'][:50]}...",
                    "url": f"#/faq/{qna['faq_id']}",
                    "confidence": qna["similarity_score"],
                    "snippet": qna["answer"][:200] + "..." if len(qna["answer"]) > 200 else qna["answer"]
                })
            
            context_text = "\n".join(context_parts)
            
            logger.info(f"Built RAG context with {len(similar_qnas)} sources")
            return context_text, sources
            
        except Exception as e:
            logger.error(f"Error building RAG context: {e}", exc_info=True)
            return "", []
    
    def search_similar_document_chunks(
        self,
        question: str,
        dataset_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks using vector similarity.
        Advanced RAG technique for PDF documents.
        
        Args:
            question: User's question
            dataset_id: Dataset ID to filter knowledge base
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)
            db: Database session (optional, will create if None)
            
        Returns:
            List of similar document chunks with scores
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # Step 1: Generate embedding for user's question
            logger.info(f"Generating embedding for question (PDF search): {question[:100]}...")
            question_embedding = self.embedding_service.generate_embedding(question)
            
            if not question_embedding:
                logger.error("Failed to generate question embedding")
                return []
            
            # Step 2: Retrieve all document chunks for the dataset with embeddings
            chunks = db.query(DocumentChunk).filter(
                and_(
                    DocumentChunk.dataset_id == dataset_id,
                    DocumentChunk.embedding.isnot(None),
                    DocumentChunk.deleted_at.is_(None)
                )
            ).all()
            
            if not chunks:
                logger.warning(f"No document chunks found for dataset: {dataset_id}")
                return []
            
            logger.info(f"Found {len(chunks)} document chunks in dataset {dataset_id}")
            
            # Step 3: Calculate similarity scores
            results = []
            for chunk in chunks:
                if chunk.embedding is not None:
                    # Convert pgvector Vector to list for compatibility
                    chunk_embedding = list(chunk.embedding) if not isinstance(chunk.embedding, list) else chunk.embedding
                    similarity = self.cosine_similarity(question_embedding, chunk_embedding)
                    
                    if similarity >= similarity_threshold:
                        # Get document info
                        document = db.query(Document).filter(
                            Document.id == chunk.document_id
                        ).first()
                        
                        results.append({
                            "chunk_id": str(chunk.id),
                            "document_id": str(chunk.document_id),
                            "document_title": document.title if document else "Unknown",
                            "chunk_text": chunk.chunk_text,
                            "chunk_index": chunk.chunk_index,
                            "page_number": chunk.page_number,
                            "page_range": chunk.page_range,
                            "section_title": chunk.section_title,
                            "similarity_score": float(similarity),
                            "dataset_id": str(chunk.dataset_id),
                            "file_url": document.file_url if document else None
                        })
            
            # Step 4: Sort by similarity and get top_k
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            top_results = results[:top_k]
            
            logger.info(
                f"Found {len(top_results)} relevant document chunks "
                f"(threshold: {similarity_threshold}, top_k: {top_k})"
            )
            
            return top_results
            
        except Exception as e:
            logger.error(f"Error in document chunk similarity search: {e}", exc_info=True)
            return []
        finally:
            if close_db:
                db.close()
    
    def build_pdf_rag_context(
        self,
        question: str,
        dataset_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        use_reranking: bool = True
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Build context for RAG from similar document chunks using advanced techniques.
        
        Advanced RAG Techniques:
        1. Semantic Search: Vector similarity on document chunks
        2. Context Window: Include surrounding chunks for better context
        3. Reranking: Diversify sources from different documents
        4. Metadata Enrichment: Include page numbers, sections, document titles
        
        Args:
            question: User's question
            dataset_id: Dataset ID for knowledge base
            top_k: Number of similar chunks to include
            similarity_threshold: Minimum similarity score
            use_reranking: Whether to rerank results for diversity
            
        Returns:
            Tuple of (context_text, sources)
        """
        try:
            # Search for similar document chunks
            similar_chunks = self.search_similar_document_chunks(
                question=question,
                dataset_id=dataset_id,
                top_k=top_k * 2 if use_reranking else top_k,  # Get more for reranking
                similarity_threshold=similarity_threshold
            )
            
            if not similar_chunks:
                logger.info("No similar document chunks found, returning empty context")
                return "", []
            
            # Advanced Technique: Reranking for diversity
            if use_reranking and len(similar_chunks) > top_k:
                similar_chunks = self._rerank_for_diversity(similar_chunks, top_k)
            
            # Build context from similar chunks
            context_parts = ["Referensi dari Dokumen:"]
            sources = []
            
            for idx, chunk in enumerate(similar_chunks, 1):
                # Format with metadata
                page_info = f"Halaman {chunk['page_number']}" if chunk['page_number'] else "Halaman tidak diketahui"
                section_info = f" - {chunk['section_title']}" if chunk['section_title'] else ""
                
                context_parts.append(
                    f"\n{idx}. [{chunk['document_title']}] {page_info}{section_info}\n"
                    f"   {chunk['chunk_text'][:500]}..." if len(chunk['chunk_text']) > 500 else chunk['chunk_text']
                )
                
                sources.append({
                    "sourceId": chunk["chunk_id"],
                    "documentId": chunk["document_id"],
                    "title": chunk["document_title"],
                    "url": chunk["file_url"] or f"#/document/{chunk['document_id']}",
                    "page": chunk["page_number"],
                    "pageRange": chunk["page_range"],
                    "section": chunk["section_title"],
                    "confidence": chunk["similarity_score"],
                    "snippet": chunk["chunk_text"][:300] + "..." if len(chunk["chunk_text"]) > 300 else chunk["chunk_text"],
                    "type": "pdf_chunk"
                })
            
            context_text = "\n".join(context_parts)
            
            logger.info(f"Built PDF RAG context with {len(similar_chunks)} chunks from documents")
            return context_text, sources
            
        except Exception as e:
            logger.error(f"Error building PDF RAG context: {e}", exc_info=True)
            return "", []
    
    def _rerank_for_diversity(
        self,
        chunks: List[Dict[str, Any]],
        target_count: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank chunks to ensure diversity across different documents.
        Advanced RAG technique: Maximal Marginal Relevance (MMR)-like approach.
        
        Args:
            chunks: List of chunks sorted by similarity
            target_count: Target number of chunks to return
            
        Returns:
            Reranked list of chunks with diversity
        """
        if len(chunks) <= target_count:
            return chunks
        
        try:
            selected = []
            remaining = chunks.copy()
            document_counts = {}
            
            # First, always take the top result
            if remaining:
                top_chunk = remaining.pop(0)
                selected.append(top_chunk)
                document_counts[top_chunk["document_id"]] = 1
            
            # Select remaining chunks with diversity
            while len(selected) < target_count and remaining:
                # Score each remaining chunk
                best_idx = 0
                best_score = -1
                
                for idx, chunk in enumerate(remaining):
                    doc_id = chunk["document_id"]
                    doc_count = document_counts.get(doc_id, 0)
                    
                    # Diversity penalty: reduce score for documents already selected
                    diversity_penalty = 0.1 * doc_count
                    adjusted_score = chunk["similarity_score"] - diversity_penalty
                    
                    if adjusted_score > best_score:
                        best_score = adjusted_score
                        best_idx = idx
                
                # Add best diverse chunk
                selected_chunk = remaining.pop(best_idx)
                selected.append(selected_chunk)
                document_counts[selected_chunk["document_id"]] = \
                    document_counts.get(selected_chunk["document_id"], 0) + 1
            
            logger.info(
                f"Reranked {len(chunks)} chunks to {len(selected)} with diversity "
                f"from {len(document_counts)} documents"
            )
            return selected
            
        except Exception as e:
            logger.error(f"Error in reranking: {e}", exc_info=True)
            return chunks[:target_count]
    
    def detect_dataset_type(self, dataset_id: str, db: Session = None) -> str:
        """
        Detect dataset type by checking what content exists.
        
        Args:
            dataset_id: Dataset ID to check
            db: Database session (optional)
            
        Returns:
            "pdf", "qna", or "mixed"
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        
        try:
            # Check for document chunks
            has_pdf = db.query(DocumentChunk).filter(
                and_(
                    DocumentChunk.dataset_id == dataset_id,
                    DocumentChunk.deleted_at.is_(None)
                )
            ).first() is not None
            
            # Check for QnA pairs
            has_qna = db.query(FAQ).filter(
                and_(
                    FAQ.dataset_id == dataset_id,
                    FAQ.deleted_at.is_(None)
                )
            ).first() is not None
            
            if has_pdf and has_qna:
                return "mixed"
            elif has_pdf:
                return "pdf"
            elif has_qna:
                return "qna"
            else:
                return "empty"
                
        except Exception as e:
            logger.error(f"Error detecting dataset type: {e}", exc_info=True)
            return "qna"  # Default to QnA
        finally:
            if close_db:
                db.close()
    
    def generate_hybrid_rag_response(
        self,
        question: str,
        persona_id: str,
        dataset_id: str,
        dataset_type: str = "auto",
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        temperature: float = 0.7,
        max_tokens: int = 800
    ) -> Dict[str, Any]:
        """
        Generate RAG response with automatic dataset type detection and routing.
        Supports QnA, PDF, and mixed datasets with advanced RAG techniques.
        
        Advanced RAG Techniques Applied:
        - Semantic Search with Vector Similarity
        - Context Window Management
        - Source Diversity (Reranking)
        - Metadata Enrichment
        - Hybrid Retrieval (for mixed datasets)
        
        Args:
            question: User's question
            persona_id: Persona ID for system prompt
            dataset_id: Dataset ID for knowledge base
            dataset_type: "qna", "pdf", "mixed", or "auto" (auto-detect)
            top_k: Number of similar items to retrieve
            similarity_threshold: Minimum similarity score
            temperature: LLM temperature
            max_tokens: Maximum response tokens
            
        Returns:
            Dictionary with response, sources, and metrics
        """
        db = SessionLocal()
        start_time_ms = self._get_current_time_ms()
        
        try:
            # Step 1: Detect dataset type if auto
            if dataset_type == "auto":
                dataset_type = self.detect_dataset_type(dataset_id, db)
                logger.info(f"Auto-detected dataset type: {dataset_type}")
            
            # Step 2: Get persona prompt
            persona_prompt = self.get_persona_prompt(persona_id, db)
            
            if not persona_prompt:
                logger.warning(f"Persona not found, using default prompt")
                persona_prompt = "You are a helpful assistant. Answer questions based on the provided context."
            
            # Step 3: Build RAG context based on dataset type
            retrieval_start = self._get_current_time_ms()
            
            if dataset_type == "pdf":
                # Use advanced PDF RAG
                context_text, sources = self.build_pdf_rag_context(
                    question=question,
                    dataset_id=dataset_id,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                    use_reranking=True
                )
            elif dataset_type == "mixed":
                # Hybrid approach: combine both QnA and PDF
                qna_context, qna_sources = self.build_rag_context(
                    question=question,
                    dataset_id=dataset_id,
                    top_k=top_k // 2,
                    similarity_threshold=similarity_threshold
                )
                
                pdf_context, pdf_sources = self.build_pdf_rag_context(
                    question=question,
                    dataset_id=dataset_id,
                    top_k=top_k // 2,
                    similarity_threshold=similarity_threshold,
                    use_reranking=True
                )
                
                # Combine contexts
                if qna_context and pdf_context:
                    context_text = f"{qna_context}\n\n{pdf_context}"
                    sources = qna_sources + pdf_sources
                elif qna_context:
                    context_text = qna_context
                    sources = qna_sources
                else:
                    context_text = pdf_context
                    sources = pdf_sources
            else:
                # Use standard QnA RAG
                context_text, sources = self.build_rag_context(
                    question=question,
                    dataset_id=dataset_id,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold
                )
            
            retrieval_time = self._get_current_time_ms() - retrieval_start
            
            # Step 4: Build prompt with context
            if context_text:
                system_prompt = f"""{persona_prompt}

Gunakan referensi berikut untuk menjawab pertanyaan user:

{context_text}

Instruksi:
- Jawab pertanyaan berdasarkan referensi di atas
- Jika jawaban ada di referensi, gunakan informasi tersebut
- Jika tidak ada informasi yang relevan, sampaikan dengan sopan
- Untuk referensi dari dokumen PDF, sebutkan halaman jika tersedia
- Jaga konsistensi dengan persona Anda"""
            else:
                system_prompt = f"""{persona_prompt}

Tidak ada referensi spesifik yang ditemukan untuk pertanyaan ini. 
Jawab pertanyaan dengan pengetahuan umum Anda, sesuai dengan persona."""
            
            # Step 5: Generate response using chat service with token tracking
            from app.services.azure_openai_chat import azure_openai_chat_service
            
            llm_start = self._get_current_time_ms()
            response_text, token_usage = azure_openai_chat_service.generate_chat_response(
                system_prompt=system_prompt,
                user_message=question,
                temperature=temperature,
                max_tokens=max_tokens
            )
            llm_time = self._get_current_time_ms() - llm_start
            
            if not response_text:
                logger.error("Failed to generate LLM response")
                return {
                    "status": "error",
                    "error": "Failed to generate response"
                }
            
            # Step 6: Calculate metrics
            total_time = self._get_current_time_ms() - start_time_ms
            
            # Calculate confidence scores - RAGAS schema (relevance only)
            avg_source_confidence = (
                sum(s["confidence"] for s in sources) / len(sources)
                if sources else 0.0
            )
            
            return {
                "status": "success",
                "response": response_text,
                "sources": sources,
                "dataset_type": dataset_type,
                "metrics": {
                    "processingTimeMs": total_time,
                    "retrievalLatencyMs": retrieval_time,
                    "llmLatencyMs": llm_time,
                    "totalTokens": token_usage.get("total_tokens", 0),
                    "promptTokens": token_usage.get("prompt_tokens", 0),
                    "completionTokens": token_usage.get("completion_tokens", 0)
                },
                "confidence": {
                    "relevance": avg_source_confidence  # RAGAS: only relevance score
                },
                "context_used": bool(context_text),
                "num_sources": len(sources)
            }
            
        except Exception as e:
            logger.error(f"Error generating hybrid RAG response: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
        finally:
            db.close()
    
    def generate_rag_response(
        self,
        question: str,
        persona_id: str,
        dataset_id: str,
        top_k: int = 3,
        similarity_threshold: float = 0.7,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Generate RAG-based response using persona and similar QnAs.
        
        Args:
            question: User's question
            persona_id: Persona ID for system prompt
            dataset_id: Dataset ID for knowledge base
            top_k: Number of similar QnAs to use
            similarity_threshold: Minimum similarity score
            temperature: LLM temperature
            max_tokens: Maximum response tokens
            
        Returns:
            Dictionary with response, sources, and metrics
        """
        db = SessionLocal()
        start_time_ms = self._get_current_time_ms()
        
        try:
            # Step 1: Get persona prompt
            persona_prompt = self.get_persona_prompt(persona_id, db)
            
            if not persona_prompt:
                logger.warning(f"Persona not found, using default prompt")
                persona_prompt = "You are a helpful assistant. Answer questions based on the provided context."
            
            # Step 2: Build RAG context
            retrieval_start = self._get_current_time_ms()
            context_text, sources = self.build_rag_context(
                question=question,
                dataset_id=dataset_id,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            retrieval_time = self._get_current_time_ms() - retrieval_start
            
            # Step 3: Build prompt with context
            if context_text:
                system_prompt = f"""{persona_prompt}

Gunakan referensi berikut untuk menjawab pertanyaan user:

{context_text}

Instruksi:
- Jawab pertanyaan berdasarkan referensi di atas
- Jika jawaban ada di referensi, gunakan informasi tersebut
- Jika tidak ada informasi yang relevan, sampaikan dengan sopan
- Jaga konsistensi dengan persona Anda"""
            else:
                system_prompt = f"""{persona_prompt}

Tidak ada referensi spesifik yang ditemukan untuk pertanyaan ini. 
Jawab pertanyaan dengan pengetahuan umum Anda, sesuai dengan persona."""
            
            # Step 4: Generate response using chat service with token tracking
            from app.services.azure_openai_chat import azure_openai_chat_service
            
            llm_start = self._get_current_time_ms()
            response_text, token_usage = azure_openai_chat_service.generate_chat_response(
                system_prompt=system_prompt,
                user_message=question,
                temperature=temperature,
                max_tokens=max_tokens
            )
            llm_time = self._get_current_time_ms() - llm_start
            
            if not response_text:
                logger.error("Failed to generate LLM response")
                return {
                    "status": "error",
                    "error": "Failed to generate response"
                }
            
            # Step 5: Calculate metrics
            total_time = self._get_current_time_ms() - start_time_ms
            
            # Calculate confidence scores - RAGAS schema (relevance only)
            avg_source_confidence = (
                sum(s["confidence"] for s in sources) / len(sources)
                if sources else 0.0
            )
            
            return {
                "status": "success",
                "response": response_text,
                "sources": sources,
                "metrics": {
                    "processingTimeMs": total_time,
                    "retrievalLatencyMs": retrieval_time,
                    "llmLatencyMs": llm_time,
                    "totalTokens": token_usage.get("total_tokens", 0),
                    "promptTokens": token_usage.get("prompt_tokens", 0),
                    "completionTokens": token_usage.get("completion_tokens", 0)
                },
                "confidence": {
                    "relevance": avg_source_confidence  # RAGAS: only relevance score
                },
                "context_used": bool(context_text),
                "num_sources": len(sources)
            }
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
        finally:
            db.close()
    
    def _get_current_time_ms(self) -> int:
        """Get current timestamp in milliseconds."""
        from datetime import datetime
        return int(datetime.utcnow().timestamp() * 1000)


# Global instance
rag_service = RAGService()
