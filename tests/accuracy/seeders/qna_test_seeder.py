"""
QnA Test Dataset Seeder
Seeds test data for QnA accuracy testing with ground truth answers
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
from app.models.faq import FAQ
from app.models.dataset import Dataset
from app.models.persona import Persona
from app.services.azure_openai import azure_openai_service


class QnATestSeeder:
    """
    Seeds QnA test data for accuracy testing.
    Creates FAQs with embeddings and corresponding test cases.
    """
    
    def __init__(self):
        """Initialize seeder."""
        self.db = SessionLocal()
        
    def create_test_dataset(
        self,
        dataset_name: str = "QnA Accuracy Test Dataset",
        description: str = "Test dataset for QnA accuracy evaluation"
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
            type="faq",
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
        persona_name: str = "Test Assistant",
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
            persona_prompt = """You are a helpful customer service assistant. 
Answer questions accurately and concisely based on the provided knowledge base. 
If you don't have enough information, say so politely."""
        
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
            description="Test persona for accuracy evaluation",
            created_at=datetime.utcnow()
        )
        
        self.db.add(persona)
        self.db.commit()
        
        print(f"✓ Created test persona: {persona.name} (ID: {persona.id})")
        return str(persona.id)
    
    def seed_faq_data(
        self,
        dataset_id: str,
        faqs: List[Dict[str, str]]
    ) -> List[str]:
        """
        Seed FAQ data with embeddings.
        
        Args:
            dataset_id: Dataset UUID
            faqs: List of FAQ dictionaries with 'question' and 'answer'
            
        Returns:
            List of created FAQ IDs
        """
        faq_ids = []
        
        print(f"\nSeeding {len(faqs)} FAQs with embeddings...")
        
        # Use tqdm for progress bar
        for faq_data in tqdm(faqs, desc="Creating FAQs", unit="faq"):
            question = faq_data["question"]
            answer = faq_data["answer"]
            
            # Generate embedding for question
            embedding = azure_openai_service.generate_embedding(question)
            
            if not embedding:
                tqdm.write(f"    WARNING: Failed to generate embedding for: {question[:50]}...")
                continue
            
            # Create FAQ
            faq = FAQ(
                id=uuid.uuid4(),
                question=question,
                answer=answer,
                dataset_id=dataset_id,
                embedding=embedding,
                created_at=datetime.utcnow()
            )
            
            self.db.add(faq)
            faq_ids.append(str(faq.id))
        
        self.db.commit()
        print(f"✓ Seeded {len(faq_ids)} FAQs successfully")
        
        return faq_ids
    
    def generate_test_cases(
        self,
        faqs: List[Dict[str, Any]],
        faq_ids: List[str],
        include_variations: bool = True,
        easy_count: int = 20,
        medium_count: int = 20,
        hard_count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate test cases from FAQs with controlled distribution.
        
        Args:
            faqs: List of FAQ data
            faq_ids: List of FAQ IDs (corresponding to faqs)
            include_variations: Whether to include paraphrased variations
            easy_count: Number of easy test cases to generate
            medium_count: Number of medium test cases to generate
            hard_count: Number of hard test cases to generate
            
        Returns:
            List of test cases with ground truth
        """
        test_cases = []
        
        # Generate easy cases (1 per FAQ, exact match)
        for i, (faq, faq_id) in enumerate(zip(faqs, faq_ids)):
            if len(test_cases) >= easy_count:
                break
            test_cases.append({
                "question": faq["question"],
                "expected_answer": faq["answer"],
                "expected_faq_id": faq_id,
                "category": faq.get("category", "general"),
                "difficulty": "easy",
                "test_type": "exact_match"
            })
        
        # Generate medium cases (paraphrased variations)
        if include_variations:
            medium_generated = 0
            for faq, faq_id in zip(faqs, faq_ids):
                if medium_generated >= medium_count:
                    break
                
                variations = self._generate_question_variations(faq["question"])
                for variation in variations:
                    if medium_generated >= medium_count:
                        break
                    test_cases.append({
                        "question": variation,
                        "expected_answer": faq["answer"],
                        "expected_faq_id": faq_id,
                        "category": faq.get("category", "general"),
                        "difficulty": "medium",
                        "test_type": "paraphrase"
                    })
                    medium_generated += 1
            
            # Generate hard cases (implicit reasoning)
            hard_generated = 0
            for faq, faq_id in zip(faqs, faq_ids):
                if hard_generated >= hard_count:
                    break
                
                hard_variations = self._generate_hard_variations(faq["question"], faq.get("category", "general"))
                for variation in hard_variations:
                    if hard_generated >= hard_count:
                        break
                    test_cases.append({
                        "question": variation,
                        "expected_answer": faq["answer"],
                        "expected_faq_id": faq_id,
                        "category": faq.get("category", "general"),
                        "difficulty": "hard",
                        "test_type": "implicit_reasoning"
                    })
                    hard_generated += 1
        
        return test_cases
    
    def _generate_question_variations(self, question: str) -> List[str]:
        """
        Generate simple variations of a question.
        
        Args:
            question: Original question
            
        Returns:
            List of variations
        """
        variations = []
        q_lower = question.lower()
        
        # Simple paraphrasing patterns
        if "what are" in q_lower and "business hours" in q_lower:
            variations.extend([
                "When are you open?",
                "What time do you open and close?"
            ])
        elif question.lower().startswith("what is"):
            variations.append(question.replace("What is", "Can you tell me about"))
            variations.append(question.replace("What is", "I need information on"))
        elif question.lower().startswith("how to"):
            variations.append(question.replace("How to", "How do I"))
            variations.append(question.replace("How to", "What is the process for"))
        elif question.lower().startswith("how do i"):
            variations.append(question.replace("How do I", "How can I"))
            variations.append(question.replace("How do I", "What's the way to"))
        elif question.lower().startswith("do you"):
            variations.append(question.replace("Do you", "Are there"))
            variations.append(question.replace("Do you", "Can you"))
        elif question.lower().startswith("can i"):
            variations.append(question.replace("Can I", "Is it possible to"))
            variations.append(question.replace("Can I", "Am I able to"))
        elif question.lower().startswith("what"):
            variations.append(question.replace("What", "Tell me about"))
            variations.append(question.replace("What", "I'd like to know"))
        elif question.lower().startswith("are there"):
            variations.append(question.replace("Are there", "Do you have"))
            variations.append(question.replace("Are there", "Can I get"))
        
        return variations[:2]  # Return up to 2 variations
    
    def _generate_hard_variations(self, question: str, category: str) -> List[str]:
        """
        Generate hard variations requiring implicit reasoning, multi-hop, or edge cases.
        
        Args:
            question: Original question
            category: Question category
            
        Returns:
            List of hard variations
        """
        variations = []
        q_lower = question.lower()
        
        # Pattern 1: Implicit/indirect questions
        if "business hours" in q_lower or "open" in q_lower:
            variations.extend([
                "Can I visit your office on Sunday afternoon?",
                "I need to come by at 7pm on a weekday, is that possible?"
            ])
        elif "reset" in q_lower and "password" in q_lower:
            variations.extend([
                "I can't login and forgot my credentials, what should I do?",
                "My account is locked, how do I get back in?"
            ])
        elif "payment" in q_lower and "method" in q_lower:
            variations.extend([
                "Can I pay with cryptocurrency?",
                "I want to use Apple Pay for a $600 order"
            ])
        elif "return" in q_lower and "policy" in q_lower:
            variations.extend([
                "I opened the package 40 days ago, can I still return it?",
                "The item works fine but I changed my mind after 3 weeks"
            ])
        elif "shipping" in q_lower and "take" in q_lower:
            variations.extend([
                "I need this by next Tuesday, which option should I choose?",
                "What's the fastest way to get my order?"
            ])
        elif "support" in q_lower or "customer service" in q_lower:
            variations.extend([
                "I have an urgent issue on Saturday night, who can help?",
                "How quickly will you respond to my email?"
            ])
        elif "track" in q_lower and "order" in q_lower:
            variations.extend([
                "Where is my package right now?",
                "I haven't received a tracking number yet"
            ])
        elif "international" in q_lower and "ship" in q_lower:
            variations.extend([
                "Do you deliver to Antarctica?",
                "Who pays customs fees for overseas orders?"
            ])
        elif "create" in q_lower and "account" in q_lower:
            variations.extend([
                "Is there a fee to sign up?",
                "What happens after I register on your site?"
            ])
        elif "privacy" in q_lower:
            variations.extend([
                "Will you share my email with other companies?",
                "How is my personal data used?"
            ])
        elif "modify" in q_lower and "order" in q_lower:
            variations.extend([
                "I just placed an order 5 minutes ago but want to change the address",
                "My order shipped yesterday, can I still update it?"
            ])
        elif "gift wrapping" in q_lower or "gift wrap" in q_lower:
            variations.extend([
                "How much extra for gift packaging?",
                "Can you hide the price on the receipt?"
            ])
        elif "discount" in q_lower or "promotion" in q_lower:
            variations.extend([
                "Is there a coupon code I can use?",
                "How do I get rewards points?"
            ])
        elif "damaged" in q_lower:
            variations.extend([
                "The box arrived crushed but I opened it 3 days ago",
                "Will you send a replacement without waiting for the return?"
            ])
        elif "secure" in q_lower or "security" in q_lower:
            variations.extend([
                "Do you save my credit card number?",
                "Is it safe to buy from your website?"
            ])
        elif "warranty" in q_lower:
            variations.extend([
                "What's covered under your warranty?",
                "My item broke after 13 months, can I still get warranty service?"
            ])
        elif "bulk" in q_lower or "volume" in q_lower:
            variations.extend([
                "I need 100 units, what's my price?",
                "Do I get a discount for ordering 15 items?"
            ])
        elif "cancel" in q_lower:
            variations.extend([
                "I placed an order 2 hours ago, can I cancel it?",
                "How do I stop my order from shipping?"
            ])
        elif "price match" in q_lower:
            variations.extend([
                "I found this cheaper on Amazon, will you match it?",
                "Can I get a refund if the price drops after I buy?"
            ])
        elif "mobile app" in q_lower or "app" in q_lower:
            variations.extend([
                "Can I order from my phone?",
                "Are there special deals in your app?"
            ])
        
        # Limit to 1 hard variation per question
        return variations[:1]
    
    def save_test_cases(self, test_cases: List[Dict[str, Any]], output_file: str):
        """
        Save test cases to JSON file.
        
        Args:
            test_cases: List of test cases
            output_file: Output file path
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_cases, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved {len(test_cases)} test cases to: {output_file}")
    
    def seed_sample_data(
        self,
        dataset_name: str = "QnA Accuracy Test Dataset"
    ) -> Dict[str, Any]:
        """
        Seed comprehensive sample data for testing.
        
        Args:
            dataset_name: Name for the test dataset
            
        Returns:
            Dictionary with dataset_id, persona_id, and test case file path
        """
        print("\n" + "="*80)
        print("QnA TEST DATA SEEDER - STARTING")
        print("="*80)
        
        # Create dataset
        dataset_id = self.create_test_dataset(dataset_name)
        
        # Create persona
        persona_id = self.create_test_persona()
        
        # Sample FAQ data (20 FAQs for comprehensive test set)
        sample_faqs = [
            {
                "question": "What are your business hours?",
                "answer": "We are open Monday through Friday from 9:00 AM to 6:00 PM, and Saturday from 10:00 AM to 4:00 PM. We are closed on Sundays and public holidays.",
                "category": "general"
            },
            {
                "question": "How do I reset my password?",
                "answer": "To reset your password, click on 'Forgot Password' on the login page. Enter your email address and you'll receive a password reset link. Follow the instructions in the email to create a new password.",
                "category": "account"
            },
            {
                "question": "What payment methods do you accept?",
                "answer": "We accept all major credit cards (Visa, MasterCard, American Express), debit cards, PayPal, and bank transfers. For orders over $500, we also offer invoice payment options for registered businesses.",
                "category": "payment"
            },
            {
                "question": "What is your return policy?",
                "answer": "You can return any item within 30 days of purchase for a full refund. Items must be unused and in original packaging. Simply contact our customer service team to initiate a return. Return shipping is free for defective items.",
                "category": "policy"
            },
            {
                "question": "How long does shipping take?",
                "answer": "Standard shipping takes 5-7 business days. Express shipping (2-3 business days) and overnight shipping options are also available at checkout. International shipping times vary by destination, typically 10-15 business days.",
                "category": "shipping"
            },
            {
                "question": "Do you offer customer support?",
                "answer": "Yes! Our customer support team is available via email at support@example.com, phone at 1-800-123-4567 (Mon-Fri 9am-6pm EST), and live chat on our website during business hours. We typically respond to emails within 24 hours.",
                "category": "support"
            },
            {
                "question": "Can I track my order?",
                "answer": "Yes, once your order ships, you'll receive a tracking number via email. You can also log into your account and view order status in the 'My Orders' section. Tracking information is updated every 24 hours.",
                "category": "shipping"
            },
            {
                "question": "Do you ship internationally?",
                "answer": "Yes, we ship to over 50 countries worldwide. Shipping costs and delivery times vary by destination. International orders may be subject to customs fees and import duties, which are the responsibility of the customer.",
                "category": "shipping"
            },
            {
                "question": "How do I create an account?",
                "answer": "Click 'Sign Up' in the top right corner of our website. Enter your email, create a password, and fill in your basic information. You'll receive a confirmation email to activate your account. Creating an account is free and gives you access to order tracking and faster checkout.",
                "category": "account"
            },
            {
                "question": "What is your privacy policy?",
                "answer": "We take your privacy seriously. We never sell your personal information to third parties. Your data is used only to process orders and improve your shopping experience. For full details, please review our Privacy Policy page on our website.",
                "category": "policy"
            },
            {
                "question": "Can I modify my order after placing it?",
                "answer": "If your order hasn't shipped yet, you may be able to modify it. Contact our customer service team immediately at support@example.com or call 1-800-123-4567. Once an order has shipped, modifications are not possible, but you can initiate a return after receiving the items.",
                "category": "order"
            },
            {
                "question": "Do you offer gift wrapping?",
                "answer": "Yes, we offer gift wrapping for an additional $5 per item. You can select this option during checkout. We also include a gift message card at no extra charge. Gift receipts (without prices) are automatically included with gift-wrapped items.",
                "category": "service"
            },
            {
                "question": "Are there any discounts available?",
                "answer": "We regularly offer promotions and discounts. Sign up for our email newsletter to receive exclusive offers and be notified of sales. First-time customers get 10% off their first order with code WELCOME10. We also have a loyalty program where you earn points on every purchase.",
                "category": "promotion"
            },
            {
                "question": "What if I receive a damaged item?",
                "answer": "If you receive a damaged item, please contact us within 48 hours with photos of the damage. We'll arrange for a free return and send you a replacement immediately. For urgent cases, we can expedite the replacement at no extra charge.",
                "category": "support"
            },
            {
                "question": "How secure is my payment information?",
                "answer": "Your payment security is our top priority. We use industry-standard SSL encryption for all transactions. We never store your complete credit card information. All payments are processed through PCI-compliant payment processors like Stripe and PayPal.",
                "category": "security"
            },
            {
                "question": "What is your warranty policy?",
                "answer": "All products come with a 1-year manufacturer warranty covering defects in materials and workmanship. Extended warranty plans (2 or 3 years) are available for purchase at checkout. To claim warranty service, contact us with your order number and description of the issue.",
                "category": "policy"
            },
            {
                "question": "Do you offer bulk order discounts?",
                "answer": "Yes, we offer volume discounts for bulk orders. Orders of 10+ units receive 10% off, 25+ units get 15% off, and 50+ units get 20% off. For custom bulk pricing on larger orders, please contact our sales team at sales@example.com.",
                "category": "pricing"
            },
            {
                "question": "How do I cancel my order?",
                "answer": "You can cancel your order within 1 hour of placing it through your account dashboard. After that, please contact customer service immediately. If the order has already shipped, you'll need to wait until delivery and process a return instead.",
                "category": "order"
            },
            {
                "question": "What is your price match policy?",
                "answer": "We offer price matching on identical items from authorized retailers. Submit a price match request within 7 days of purchase with proof of the lower price. We'll refund the difference if approved. Price matching does not apply to marketplace sellers or expired promotions.",
                "category": "pricing"
            },
            {
                "question": "Do you have a mobile app?",
                "answer": "Yes, our mobile app is available for iOS and Android. Download it from the App Store or Google Play. The app offers exclusive app-only deals, push notifications for order updates, and a faster checkout experience with saved payment methods.",
                "category": "technology"
            }
        ]
        
        # Seed FAQs
        faq_ids = self.seed_faq_data(dataset_id, sample_faqs)
        
        # Generate test cases
        print("\nGenerating test cases...")
        print("Target distribution: 20 easy, 20 medium, 10 hard (50 total)")
        test_cases = self.generate_test_cases(
            faqs=sample_faqs,
            faq_ids=faq_ids,
            include_variations=True,
            easy_count=20,
            medium_count=20,
            hard_count=10
        )
        
        # Count by difficulty
        easy_count = sum(1 for tc in test_cases if tc['difficulty'] == 'easy')
        medium_count = sum(1 for tc in test_cases if tc['difficulty'] == 'medium')
        hard_count = sum(1 for tc in test_cases if tc['difficulty'] == 'hard')
        
        print(f"Generated: {easy_count} easy, {medium_count} medium, {hard_count} hard ({len(test_cases)} total)")
        
        # Save test cases
        test_file = "tests/accuracy/test_data/qna_test_cases.json"
        self.save_test_cases(test_cases, test_file)
        
        # Save configuration
        config = {
            "dataset_id": dataset_id,
            "persona_id": persona_id,
            "dataset_name": dataset_name,
            "test_cases_file": test_file,
            "total_faqs": len(faq_ids),
            "total_test_cases": len(test_cases),
            "created_at": datetime.utcnow().isoformat()
        }
        
        config_file = "tests/accuracy/test_data/qna_test_config.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved configuration to: {config_file}")
        
        print("\n" + "="*80)
        print("QnA TEST DATA SEEDER - COMPLETED")
        print("="*80)
        print(f"\nDataset ID: {dataset_id}")
        print(f"Persona ID: {persona_id}")
        print(f"Total FAQs: {len(faq_ids)}")
        print(f"Total Test Cases: {len(test_cases)}")
        print(f"\nTest Cases File: {test_file}")
        print(f"Config File: {config_file}")
        print("\n" + "="*80)
        
        return config
    
    def close(self):
        """Close database connection."""
        self.db.close()


def main():
    """Main function to run QnA test data seeder."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QnA Test Data Seeder")
    parser.add_argument("--dataset-name", default="QnA Accuracy Test Dataset",
                        help="Name for the test dataset")
    
    args = parser.parse_args()
    
    seeder = QnATestSeeder()
    
    try:
        config = seeder.seed_sample_data(dataset_name=args.dataset_name)
        
        print("\n✓ Seeding completed successfully!")
        print("\nTo run accuracy tests, use:")
        print(f"  python tests/accuracy/test_qna_accuracy.py \\")
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
