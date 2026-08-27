"""
PDF Test Dataset Seeder
Seeds test data for PDF RAG accuracy testing with ground truth answers
"""
import os
import sys
import json
import uuid
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk
from app.models.dataset import Dataset
from app.models.persona import Persona
from app.services.azure_openai import azure_openai_service


class PDFTestSeeder:
    """
    Seeds PDF test data for accuracy testing.
    Creates simulated document chunks with embeddings and test cases.
    """
    
    def __init__(self):
        """Initialize seeder."""
        self.db = SessionLocal()
        
    def create_test_dataset(
        self,
        dataset_name: str = "PDF Accuracy Test Dataset",
        description: str = "Test dataset for PDF RAG accuracy evaluation"
    ) -> str:
        """
        Create a new test dataset.
        
        Args:
            dataset_name: Name of the dataset
            description: Description
            
        Returns:
            Dataset UUID
        """
        from app.models.dataset import Dataset
        
        dataset = Dataset(
            id=uuid.uuid4(),
            name=dataset_name,
            type="pdf",
            description=description,
            status="on progress",
            created_at=datetime.utcnow()
        )
        
        self.db.add(dataset)
        self.db.commit()
        
        print(f"✓ Created test dataset: {dataset.name} (ID: {dataset.id})")
        return str(dataset.id)
    
    def create_test_persona(
        self,
        persona_name: str = "Test Document Assistant",
        persona_prompt: str = None
    ) -> str:
        """
        Create a test persona or use existing one.
        
        Args:
            persona_name: Name of the persona
            persona_prompt: System prompt for the persona
            
        Returns:
            Persona UUID
        """
        if persona_prompt is None:
            persona_prompt = """You are a helpful research assistant that answers questions based on provided documents. 
Always cite the specific page numbers and document names when answering. 
Be precise and accurate. If information is not in the documents, say so clearly."""
        
        # Check if persona exists
        existing = self.db.query(Persona).filter(
            Persona.name == persona_name,
            Persona.deleted_at.is_(None)
        ).first()
        
        if existing:
            print(f"✓ Using existing persona: {existing.name} (ID: {existing.id})")
            return str(existing.id)
        
        # Create new persona
        persona = Persona(
            id=uuid.uuid4(),
            name=persona_name,
            prompt=persona_prompt,
            description="Test persona for PDF accuracy evaluation",
            created_at=datetime.utcnow()
        )
        
        self.db.add(persona)
        self.db.commit()
        
        print(f"✓ Created test persona: {persona.name} (ID: {persona.id})")
        return str(persona.id)
    
    def create_test_document(
        self,
        dataset_id: str,
        title: str,
        file_name: str,
        number_of_pages: int
    ) -> str:
        """
        Create a test document entry.
        
        Args:
            dataset_id: Dataset UUID
            title: Document title
            file_name: File name
            number_of_pages: Number of pages
            
        Returns:
            Document UUID
        """
        document = Document(
            id=uuid.uuid4(),
            title=title,
            file_name=file_name,
            file_url=f"test://documents/{file_name}",
            number_of_pages=number_of_pages,
            dataset_id=dataset_id,
            created_at=datetime.utcnow()
        )
        
        self.db.add(document)
        self.db.commit()
        
        print(f"  ✓ Created document: {title} ({number_of_pages} pages)")
        return str(document.id)
    
    def seed_document_chunks(
        self,
        document_id: str,
        dataset_id: str,
        chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Seed document chunks with embeddings.
        
        Args:
            document_id: Document UUID
            dataset_id: Dataset UUID
            chunks: List of chunk dictionaries with content and metadata
            
        Returns:
            List of created chunk IDs
        """
        chunk_ids = []
        
        print(f"  Creating {len(chunks)} chunks with embeddings...")
        
        # Use tqdm for progress bar
        for idx, chunk_data in tqdm(enumerate(chunks), desc="    Generating embeddings", unit="chunk", total=len(chunks)):
            chunk_text = chunk_data["text"]
            
            # Generate embedding
            embedding = azure_openai_service.generate_embedding(chunk_text)
            
            if not embedding:
                tqdm.write(f"      WARNING: Failed to generate embedding for chunk {idx + 1}, skipping...")
                continue
            
            # Create chunk
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                dataset_id=dataset_id,
                chunk_text=chunk_text,
                chunk_index=idx,
                chunk_size=len(chunk_text),
                page_number=chunk_data.get("page_number"),
                page_range=chunk_data.get("page_range"),
                section_title=chunk_data.get("section_title"),
                embedding=embedding,
                chunking_strategy="manual",
                overlap_size=0,
                created_at=datetime.utcnow()
            )
            
            self.db.add(chunk)
            chunk_ids.append(str(chunk.id))
        
        self.db.commit()
        print(f"  ✓ Created {len(chunk_ids)} chunks with embeddings")
        
        return chunk_ids
    
    def seed_sample_data(
        self,
        dataset_name: str = "PDF Accuracy Test Dataset"
    ) -> Dict[str, Any]:
        """
        Seed comprehensive sample PDF data for testing.
        
        Args:
            dataset_name: Name for the test dataset
            
        Returns:
            Dictionary with dataset_id, persona_id, and test case file path
        """
        print("\n" + "="*80)
        print("PDF TEST DATA SEEDER - STARTING")
        print("="*80)
        
        # Create dataset
        dataset_id = self.create_test_dataset(dataset_name)
        
        # Create persona
        persona_id = self.create_test_persona()
        
        # Sample documents with chunks
        print("\nCreating test documents...")
        
        # Document 1: Company Policy Manual
        doc1_id = self.create_test_document(
            dataset_id=dataset_id,
            title="Company Policy Manual 2024",
            file_name="company_policy_manual_2024.pdf",
            number_of_pages=25
        )
        
        doc1_chunks = [
            {
                "text": "Employee Leave Policy: All full-time employees are entitled to 15 days of paid vacation leave per year. Vacation days accumulate at a rate of 1.25 days per month. Employees must submit leave requests at least 2 weeks in advance through the HR portal. Unused vacation days can be carried over to the next year, up to a maximum of 5 days.",
                "page_number": 5,
                "page_range": "5",
                "section_title": "Leave Policies"
            },
            {
                "text": "Sick Leave: Employees receive 10 days of paid sick leave annually. Sick leave does not carry over to the following year. For absences exceeding 3 consecutive days, a medical certificate is required. Sick leave can also be used for medical appointments and caring for immediate family members.",
                "page_number": 6,
                "page_range": "6",
                "section_title": "Leave Policies"
            },
            {
                "text": "Remote Work Policy: Employees may work remotely up to 2 days per week with manager approval. Remote work arrangements must be documented and approved through the HR system. Employees working remotely are expected to maintain the same working hours and availability as in-office work. Company-provided equipment must be used for remote work.",
                "page_number": 12,
                "page_range": "12",
                "section_title": "Work Arrangements"
            },
            {
                "text": "Performance Review Process: Annual performance reviews are conducted in December. Employees receive feedback on goal achievement, competencies, and professional development. The review process includes self-assessment, manager evaluation, and a formal review meeting. Performance ratings directly impact annual salary adjustments and bonus eligibility.",
                "page_number": 18,
                "page_range": "18",
                "section_title": "Performance Management"
            }
        ]
        
        doc1_chunk_ids = self.seed_document_chunks(doc1_id, dataset_id, doc1_chunks)
        
        # Document 2: Product User Guide
        doc2_id = self.create_test_document(
            dataset_id=dataset_id,
            title="Product X User Guide",
            file_name="product_x_user_guide.pdf",
            number_of_pages=45
        )
        
        doc2_chunks = [
            {
                "text": "Getting Started with Product X: To begin using Product X, first download the application from our website at www.productx.com/download. System requirements include Windows 10 or later, 8GB RAM minimum, and 500MB free disk space. After installation, launch the application and create your account using your email address.",
                "page_number": 3,
                "page_range": "3",
                "section_title": "Getting Started"
            },
            {
                "text": "Creating Your First Project: Click the 'New Project' button in the top left corner. Enter a project name and select a template. Product X offers templates for various use cases including business reports, presentations, and marketing materials. You can also start with a blank project for maximum customization.",
                "page_number": 8,
                "page_range": "8",
                "section_title": "Basic Operations"
            },
            {
                "text": "Advanced Features: Product X includes AI-powered content suggestions, real-time collaboration, and version control. To enable AI suggestions, go to Settings > AI Features and toggle 'Smart Suggestions' on. The AI analyzes your content and provides contextual recommendations for improvement.",
                "page_number": 22,
                "page_range": "22",
                "section_title": "Advanced Features"
            },
            {
                "text": "Troubleshooting: If Product X crashes or becomes unresponsive, first try closing and reopening the application. If problems persist, check for updates in the Help menu. Common issues include insufficient disk space, outdated graphics drivers, or conflicts with antivirus software. For persistent issues, contact our support team at support@productx.com.",
                "page_number": 40,
                "page_range": "40",
                "section_title": "Troubleshooting"
            }
        ]
        
        doc2_chunk_ids = self.seed_document_chunks(doc2_id, dataset_id, doc2_chunks)
        
        # Document 3: Financial Report
        doc3_id = self.create_test_document(
            dataset_id=dataset_id,
            title="Q4 2023 Financial Report",
            file_name="q4_2023_financial_report.pdf",
            number_of_pages=32
        )
        
        doc3_chunks = [
            {
                "text": "Revenue Summary: Total revenue for Q4 2023 reached $45.2 million, representing a 23% increase year-over-year. Subscription revenue accounted for 72% of total revenue at $32.5 million. Professional services contributed $8.7 million, and licensing fees generated $4.0 million. The Americas region led with 58% of total revenue.",
                "page_number": 4,
                "page_range": "4-5",
                "section_title": "Financial Overview"
            },
            {
                "text": "Operating Expenses: Total operating expenses were $31.8 million in Q4 2023, up 15% from the previous year. Research and development expenses were $12.4 million (39% of total opex), sales and marketing $11.2 million (35%), and general administrative costs $8.2 million (26%). The increase was primarily driven by headcount growth and expanded market presence.",
                "page_number": 9,
                "page_range": "9",
                "section_title": "Operating Costs"
            },
            {
                "text": "Customer Growth: We added 1,250 new customers in Q4, bringing our total customer base to 8,400 globally. Enterprise customers (>1000 employees) grew by 18%, now representing 35% of our customer base. Average contract value increased to $24,500, up from $21,200 in Q3. Customer retention rate remained strong at 94%.",
                "page_number": 15,
                "page_range": "15",
                "section_title": "Customer Metrics"
            },
            {
                "text": "Future Outlook: For Q1 2024, we project revenue between $47-49 million, continuing our growth trajectory. We plan to invest heavily in product development with a focus on AI capabilities and mobile platforms. International expansion, particularly in the Asia-Pacific region, remains a strategic priority with expected hiring of 50+ employees in regional offices.",
                "page_number": 28,
                "page_range": "28-29",
                "section_title": "Future Outlook"
            }
        ]
        
        doc3_chunk_ids = self.seed_document_chunks(doc3_id, dataset_id, doc3_chunks)
        
        # Generate test cases
        print("\nGenerating test cases...")
        test_cases = self._generate_test_cases(doc1_id, doc2_id, doc3_id)
        
        # Save test cases
        test_file = "tests/accuracy/test_data/pdf_test_cases.json"
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_cases, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved {len(test_cases)} test cases to: {test_file}")
        
        # Save configuration
        config = {
            "dataset_id": dataset_id,
            "persona_id": persona_id,
            "dataset_name": dataset_name,
            "test_cases_file": test_file,
            "documents": [
                {"id": doc1_id, "title": "Company Policy Manual 2024", "chunks": len(doc1_chunk_ids)},
                {"id": doc2_id, "title": "Product X User Guide", "chunks": len(doc2_chunk_ids)},
                {"id": doc3_id, "title": "Q4 2023 Financial Report", "chunks": len(doc3_chunk_ids)}
            ],
            "total_chunks": len(doc1_chunk_ids) + len(doc2_chunk_ids) + len(doc3_chunk_ids),
            "total_test_cases": len(test_cases),
            "created_at": datetime.utcnow().isoformat()
        }
        
        config_file = "tests/accuracy/test_data/pdf_test_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved configuration to: {config_file}")
        
        print("\n" + "="*80)
        print("PDF TEST DATA SEEDER - COMPLETED")
        print("="*80)
        print(f"\nDataset ID: {dataset_id}")
        print(f"Persona ID: {persona_id}")
        print(f"Total Documents: 3")
        print(f"Total Chunks: {config['total_chunks']}")
        print(f"Total Test Cases: {len(test_cases)}")
        print(f"\nTest Cases File: {test_file}")
        print(f"Config File: {config_file}")
        print("\n" + "="*80)
        
        return config
    
    def _generate_test_cases(
        self,
        doc1_id: str,
        doc2_id: str,
        doc3_id: str
    ) -> List[Dict[str, Any]]:
        """Generate test cases for the seeded documents."""
        
        test_cases = [
            # Company Policy Manual - Easy
            {
                "question": "How many vacation days do full-time employees get per year?",
                "expected_answer": "All full-time employees are entitled to 15 days of paid vacation leave per year, accumulating at a rate of 1.25 days per month. Unused vacation days can be carried over to the next year, up to a maximum of 5 days.",
                "expected_document_ids": [doc1_id],
                "expected_pages": [5],
                "category": "policy",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            {
                "question": "What is the sick leave policy?",
                "expected_answer": "Employees receive 10 days of paid sick leave annually. Sick leave does not carry over to the following year. For absences exceeding 3 consecutive days, a medical certificate is required. Sick leave can also be used for medical appointments and caring for immediate family members.",
                "expected_document_ids": [doc1_id],
                "expected_pages": [6],
                "category": "policy",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            {
                "question": "How many days per week can employees work remotely?",
                "expected_answer": "Employees may work remotely up to 2 days per week with manager approval. Remote work arrangements must be documented and approved through the HR system, and employees are expected to maintain the same working hours and availability as in-office work.",
                "expected_document_ids": [doc1_id],
                "expected_pages": [12],
                "category": "policy",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            # Company Policy Manual - Medium (synthesizing info)
            {
                "question": "What are the differences between vacation leave and sick leave policies?",
                "expected_answer": "Vacation leave provides 15 days per year that can accumulate and carry over up to 5 days, while sick leave provides 10 days per year that does not carry over. Vacation requires 2 weeks advance notice, while sick leave requires a medical certificate only for absences over 3 days.",
                "expected_document_ids": [doc1_id],
                "expected_pages": [5, 6],
                "category": "policy",
                "difficulty": "medium",
                "context_type": "multi_page"
            },
            # Product User Guide - Easy
            {
                "question": "What are the system requirements for Product X?",
                "expected_answer": "Product X requires Windows 10 or later, minimum 8GB RAM, and 500MB free disk space.",
                "expected_document_ids": [doc2_id],
                "expected_pages": [3],
                "category": "technical",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            {
                "question": "How do I create a new project in Product X?",
                "expected_answer": "To create a new project, click the 'New Project' button in the top left corner, enter a project name, and select a template. Product X offers templates for business reports, presentations, and marketing materials, or you can start with a blank project.",
                "expected_document_ids": [doc2_id],
                "expected_pages": [8],
                "category": "technical",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            {
                "question": "What should I do if Product X crashes?",
                "expected_answer": "If Product X crashes, first try closing and reopening the application. If problems persist, check for updates in the Help menu. Common issues include insufficient disk space, outdated graphics drivers, or conflicts with antivirus software. For persistent issues, contact support at support@productx.com.",
                "expected_document_ids": [doc2_id],
                "expected_pages": [40],
                "category": "technical",
                "difficulty": "medium",
                "context_type": "single_page"
            },
            # Financial Report - Easy
            {
                "question": "What was the total revenue for Q4 2023?",
                "expected_answer": "Total revenue for Q4 2023 reached $45.2 million, representing a 23% increase year-over-year. Subscription revenue accounted for 72% at $32.5 million, professional services contributed $8.7 million, and licensing fees generated $4.0 million.",
                "expected_document_ids": [doc3_id],
                "expected_pages": [4],
                "category": "financial",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            {
                "question": "How many new customers were added in Q4 2023?",
                "expected_answer": "We added 1,250 new customers in Q4 2023, bringing the total customer base to 8,400 globally. Enterprise customers grew by 18% and now represent 35% of the customer base. Average contract value increased to $24,500.",
                "expected_document_ids": [doc3_id],
                "expected_pages": [15],
                "category": "financial",
                "difficulty": "easy",
                "context_type": "single_page"
            },
            # Financial Report - Medium
            {
                "question": "What was the operating margin for Q4 2023?",
                "expected_answer": "With total revenue of $45.2 million and operating expenses of $31.8 million, the operating income was approximately $13.4 million, resulting in an operating margin of about 30%.",
                "expected_document_ids": [doc3_id],
                "expected_pages": [4, 9],
                "category": "financial",
                "difficulty": "medium",
                "context_type": "multi_page"
            },
            # Cross-document - Hard
            {
                "question": "Based on the financial report and company policies, what investments is the company making in employees?",
                "expected_answer": "The company is investing in employee growth through competitive leave policies (15 vacation days, 10 sick days), flexible remote work options (up to 2 days per week), and annual performance reviews tied to compensation. Financially, the company plans to hire 50+ employees for international expansion, particularly in Asia-Pacific, as part of Q1 2024 growth strategy.",
                "expected_document_ids": [doc1_id, doc3_id],
                "expected_pages": [5, 6, 12, 18, 28],
                "category": "strategic",
                "difficulty": "hard",
                "context_type": "cross_document"
            }
        ]
        
        return test_cases
    
    def close(self):
        """Close database connection."""
        self.db.close()


def main():
    """Main function to run PDF test data seeder."""
    import argparse
    
    parser = argparse.ArgumentParser(description="PDF Test Data Seeder")
    parser.add_argument("--dataset-name", default="PDF Accuracy Test Dataset",
                        help="Name for the test dataset")
    
    args = parser.parse_args()
    
    seeder = PDFTestSeeder()
    
    try:
        config = seeder.seed_sample_data(dataset_name=args.dataset_name)
        
        print("\n✓ Seeding completed successfully!")
        print("\nTo run accuracy tests, use:")
        print(f"  python tests/accuracy/test_pdf_accuracy.py \\")
        print(f"    --persona-id {config['persona_id']} \\")
        print(f"    --dataset-id {config['dataset_id']} \\")
        print(f"    --test-file {config['test_cases_file']}")
        
    except Exception as e:
        print(f"\n✗ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        seeder.close()


if __name__ == "__main__":
    main()
