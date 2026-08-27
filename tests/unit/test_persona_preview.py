"""
Test script for persona preview endpoint
"""
import sys
import os
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.persona import Persona
from app.services.azure_openai_chat import azure_openai_chat_service


def create_sample_persona() -> str:
    """Create a sample persona for testing."""
    db = SessionLocal()
    
    try:
        # Check if sample persona already exists
        existing = db.query(Persona).filter(Persona.name == "Technical Data Analyst").first()
        
        if existing and existing.deleted_at is None:
            print(f"✓ Sample persona already exists with ID: {existing.id}")
            return str(existing.id)
        
        # Create new persona
        persona = Persona(
            id=uuid.uuid4(),
            name="Technical Data Analyst",
            prompt="You function as a Technical Data Analyst. Your tone must be formal, neutral, and fact-focused. Always provide precise, data-driven responses with technical accuracy. Avoid casual language or emotional expressions.",
            description="A formal technical analyst persona for data analysis and reporting",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(persona)
        db.commit()
        db.refresh(persona)
        
        print(f"✓ Created sample persona with ID: {persona.id}")
        return str(persona.id)
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error creating persona: {e}")
        raise
    finally:
        db.close()


def test_persona_preview_direct(persona_id: str):
    """Test persona preview using the service directly."""
    print("\n" + "="*60)
    print("TEST 1: Direct Service Call")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Fetch persona
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        
        if not persona:
            print(f"✗ Persona {persona_id} not found")
            return
        
        print(f"\nPersona Details:")
        print(f"  ID: {persona.id}")
        print(f"  Name: {persona.name}")
        print(f"  Description: {persona.description}")
        print(f"\nPrompt:")
        print(f"  {persona.prompt}")
        
        # Generate preview
        print(f"\n🤖 Generating preview response...")
        
        result = azure_openai_chat_service.generate_persona_preview(
            persona_name=persona.name,
            persona_prompt=persona.prompt,
            preview_question="Hi, who are you?"
        )
        
        if result:
            print(f"\n✓ Preview generated successfully!")
            print(f"\nQuestion: {result['question']}")
            print(f"\nAnswer:\n{result['answer']}")
        else:
            print(f"\n✗ Failed to generate preview")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def test_custom_question(persona_id: str, custom_question: str):
    """Test persona preview with custom question."""
    print("\n" + "="*60)
    print("TEST 2: Custom Question")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        
        if not persona:
            print(f"✗ Persona {persona_id} not found")
            return
        
        print(f"\nPersona: {persona.name}")
        print(f"Custom Question: {custom_question}")
        
        print(f"\n🤖 Generating response...")
        
        result = azure_openai_chat_service.generate_persona_preview(
            persona_name=persona.name,
            persona_prompt=persona.prompt,
            preview_question=custom_question
        )
        
        if result:
            print(f"\n✓ Response generated successfully!")
            print(f"\nAnswer:\n{result['answer']}")
        else:
            print(f"\n✗ Failed to generate response")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """Run all tests."""
    print("="*60)
    print("PERSONA PREVIEW TEST SUITE")
    print("="*60)
    
    try:
        # Step 1: Create or get sample persona
        print("\nStep 1: Setup Sample Persona")
        persona_id = create_sample_persona()
        
        # Step 2: Test default preview
        test_persona_preview_direct(persona_id)
        
        # Step 3: Test custom question
        test_custom_question(
            persona_id,
            "Can you explain what is data normalization?"
        )
        
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"✓ Persona ID: {persona_id}")
        print(f"✓ All tests completed")
        print(f"\nYou can now test the API endpoint:")
        print(f"  GET http://localhost:8000/api/v1/persona/preview/{persona_id}")
        print(f"  GET http://localhost:8000/api/v1/persona/{persona_id}")
        print(f"  POST http://localhost:8000/api/v1/persona/preview/{persona_id}/custom")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
