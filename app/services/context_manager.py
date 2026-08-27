"""
Context Management Service for Chat History

This service manages conversation context using Redis to store and retrieve
chat history, enabling multi-turn conversations with context awareness.

Features:
- Store chat history per session
- Retrieve recent conversation context
- Build enhanced context for RAG
- Handle context window management
- Auto-expire old sessions
"""
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manages conversation context and chat history using Redis.
    """
    
    def __init__(self):
        """Initialize context manager with Redis connection."""
        try:
            # Parse Redis URL to get connection details
            redis_url = settings.get_redis_url()
            
            # Connect to Redis
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis for context management")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            self.redis_client = None
    
    def _get_session_key(self, session_id: str, user_id: str) -> str:
        """
        Generate Redis key for session history.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            Redis key string
        """
        return f"chat_history:{user_id}:{session_id}"
    
    def _get_context_summary_key(self, session_id: str, user_id: str) -> str:
        """
        Generate Redis key for context summary.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            Redis key string
        """
        return f"context_summary:{user_id}:{session_id}"
    
    def add_message_to_history(
        self,
        session_id: str,
        user_id: str,
        role: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_hours: int = 24
    ) -> bool:
        """
        Add a message to chat history in Redis.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            role: Message role ("user" or "assistant")
            message: Message text
            metadata: Additional metadata (sources, intent, etc.)
            ttl_hours: Time to live in hours (default: 24 hours)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping history storage")
            return False
        
        try:
            key = self._get_session_key(session_id, user_id)
            
            # Create message entry
            message_entry = {
                "role": role,
                "content": message,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            # Add to Redis list (RPUSH adds to end of list)
            self.redis_client.rpush(key, json.dumps(message_entry))
            
            # Set expiration (convert hours to seconds)
            self.redis_client.expire(key, ttl_hours * 3600)
            
            logger.info(
                f"Added {role} message to history: session={session_id}, "
                f"user={user_id}, length={len(message)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding message to history: {e}", exc_info=True)
            return False
    
    def get_chat_history(
        self,
        session_id: str,
        user_id: str,
        max_messages: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chat history for a session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            max_messages: Maximum number of recent messages to retrieve
            
        Returns:
            List of message dictionaries (most recent last)
        """
        if not self.redis_client:
            logger.warning("Redis client not available, returning empty history")
            return []
        
        try:
            key = self._get_session_key(session_id, user_id)
            
            # Get recent messages (negative index for last N items)
            if max_messages > 0:
                messages = self.redis_client.lrange(key, -max_messages, -1)
            else:
                messages = self.redis_client.lrange(key, 0, -1)
            
            # Parse JSON messages
            history = []
            for msg in messages:
                try:
                    history.append(json.loads(msg))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message: {msg}")
                    continue
            
            logger.info(
                f"Retrieved {len(history)} messages from history: "
                f"session={session_id}, user={user_id}"
            )
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}", exc_info=True)
            return []
    
    def build_conversation_context(
        self,
        session_id: str,
        user_id: str,
        current_question: str,
        max_history: int = 5,
        include_metadata: bool = False
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Build conversation context from chat history.
        
        This creates a formatted context string that includes recent conversation
        history to provide continuity for multi-turn conversations.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            current_question: Current user question
            max_history: Maximum history messages to include
            include_metadata: Whether to include metadata in context
            
        Returns:
            Tuple of (context_string, history_list)
        """
        try:
            # Get recent chat history
            history = self.get_chat_history(session_id, user_id, max_history)
            
            if not history:
                logger.info("No chat history found, using standalone question")
                return current_question, []
            
            # Build context string
            context_parts = []
            
            # Add conversation history
            if len(history) > 0:
                context_parts.append("Konteks percakapan sebelumnya:")
                
                for msg in history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        context_parts.append(f"User: {content}")
                    elif role == "assistant":
                        # Truncate long assistant responses
                        truncated_content = content[:200] + "..." if len(content) > 200 else content
                        context_parts.append(f"Assistant: {truncated_content}")
                    
                    # Add metadata if requested
                    if include_metadata and msg.get("metadata"):
                        metadata = msg["metadata"]
                        if metadata.get("intent"):
                            context_parts.append(f"  (Intent: {metadata['intent']})")
                
                context_parts.append("")  # Empty line separator
            
            # Add current question
            context_parts.append(f"Pertanyaan saat ini: {current_question}")
            
            context_string = "\n".join(context_parts)
            
            logger.info(
                f"Built conversation context: {len(history)} history messages, "
                f"{len(context_string)} chars"
            )
            
            return context_string, history
            
        except Exception as e:
            logger.error(f"Error building conversation context: {e}", exc_info=True)
            return current_question, []
    
    def build_enhanced_question(
        self,
        session_id: str,
        user_id: str,
        current_question: str,
        max_history: int = 3
    ) -> str:
        """
        Build enhanced question with conversation context for better RAG retrieval.
        
        This method creates a contextualized version of the current question by
        incorporating relevant information from previous turns, improving
        retrieval accuracy for follow-up questions.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            current_question: Current user question
            max_history: Maximum history messages to consider
            
        Returns:
            Enhanced question string with context
        """
        try:
            # Get recent history
            history = self.get_chat_history(session_id, user_id, max_history * 2)
            
            if not history:
                return current_question
            
            # Extract relevant context from recent user questions
            recent_user_questions = []
            recent_topics = []
            
            for msg in history[-max_history*2:]:
                if msg.get("role") == "user":
                    recent_user_questions.append(msg.get("content", ""))
                
                # Extract topics from metadata
                if msg.get("metadata", {}).get("entities"):
                    entities = msg["metadata"]["entities"]
                    if entities.get("dataset_type"):
                        recent_topics.append(entities["dataset_type"])
            
            # Check if current question is a follow-up (contains pronouns or short)
            is_followup = any(
                word in current_question.lower()
                for word in ["ini", "itu", "tersebut", "dia", "apa", "bagaimana", "kenapa", "it", "that", "this", "what", "how", "why"]
            ) and len(current_question.split()) < 10
            
            if is_followup and recent_user_questions:
                # Enhance question with previous context
                prev_question = recent_user_questions[-1] if recent_user_questions else ""
                
                enhanced = f"{current_question} (konteks sebelumnya: {prev_question[:100]})"
                
                logger.info(
                    f"Enhanced follow-up question: '{current_question}' -> "
                    f"'{enhanced[:100]}...'"
                )
                
                return enhanced
            
            return current_question
            
        except Exception as e:
            logger.error(f"Error building enhanced question: {e}", exc_info=True)
            return current_question
    
    def store_context_summary(
        self,
        session_id: str,
        user_id: str,
        summary: Dict[str, Any],
        ttl_hours: int = 24
    ) -> bool:
        """
        Store context summary for quick access.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            summary: Summary dictionary (topics, entities, etc.)
            ttl_hours: Time to live in hours
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            key = self._get_context_summary_key(session_id, user_id)
            
            self.redis_client.setex(
                key,
                ttl_hours * 3600,
                json.dumps(summary)
            )
            
            logger.info(f"Stored context summary: session={session_id}, user={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing context summary: {e}", exc_info=True)
            return False
    
    def get_context_summary(
        self,
        session_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve context summary.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            Summary dictionary or None
        """
        if not self.redis_client:
            return None
        
        try:
            key = self._get_context_summary_key(session_id, user_id)
            data = self.redis_client.get(key)
            
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving context summary: {e}", exc_info=True)
            return None
    
    def clear_session_history(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """
        Clear chat history for a session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            key = self._get_session_key(session_id, user_id)
            summary_key = self._get_context_summary_key(session_id, user_id)
            
            self.redis_client.delete(key, summary_key)
            
            logger.info(f"Cleared session history: session={session_id}, user={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing session history: {e}", exc_info=True)
            return False
    
    def get_session_stats(
        self,
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get statistics about a session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            
        Returns:
            Dictionary with session statistics
        """
        if not self.redis_client:
            return {"message_count": 0, "exists": False}
        
        try:
            key = self._get_session_key(session_id, user_id)
            
            message_count = self.redis_client.llen(key)
            ttl = self.redis_client.ttl(key)
            
            return {
                "message_count": message_count,
                "ttl_seconds": ttl,
                "exists": message_count > 0
            }
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}", exc_info=True)
            return {"message_count": 0, "exists": False, "error": str(e)}


# Global instance
context_manager = ContextManager()
