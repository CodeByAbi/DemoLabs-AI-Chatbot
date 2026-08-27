"""
Accuracy Report Generator
Generates professional documentation from accuracy test results
"""
import json
import os
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path


class AccuracyReportGenerator:
    """
    Generates comprehensive markdown documentation from accuracy test results.
    Creates professional reports with insights, visualizations, and recommendations.
    """
    
    def __init__(self):
        """Initialize report generator."""
        pass
    
    def generate_comprehensive_report(
        self,
        qna_report_file: str = None,
        pdf_report_file: str = None,
        output_file: str = "docs/CHATBOT_ACCURACY_REPORT.md"
    ):
        """
        Generate comprehensive accuracy report from test results.
        
        Args:
            qna_report_file: Path to QnA accuracy test results JSON
            pdf_report_file: Path to PDF accuracy test results JSON
            output_file: Output markdown file path
        """
        # Load reports
        qna_report = self._load_report(qna_report_file) if qna_report_file else None
        pdf_report = self._load_report(pdf_report_file) if pdf_report_file else None
        
        # Generate markdown sections
        sections = []
        
        # Header
        sections.append(self._generate_header())
        
        # Executive Summary
        sections.append(self._generate_executive_summary(qna_report, pdf_report))
        
        # QnA Accuracy Results
        if qna_report:
            sections.append(self._generate_qna_section(qna_report))
        
        # PDF Accuracy Results
        if pdf_report:
            sections.append(self._generate_pdf_section(pdf_report))
        
        # Comparative Analysis
        if qna_report and pdf_report:
            sections.append(self._generate_comparative_analysis(qna_report, pdf_report))
        
        # Detailed Test Results (Raw Data Recap)
        if qna_report:
            sections.append(self._generate_qna_raw_results(qna_report))
        if pdf_report:
            sections.append(self._generate_pdf_raw_results(pdf_report))
        
        # Insights and Recommendations
        sections.append(self._generate_insights_recommendations(qna_report, pdf_report))
        
        # Methodology
        sections.append(self._generate_methodology())
        
        # Appendix
        sections.append(self._generate_appendix())
        
        # Write to file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(sections))
        
        print(f"✓ Generated comprehensive report: {output_file}")
    
    def _load_report(self, file_path: str) -> Dict[str, Any]:
        """Load report JSON file."""
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _generate_header(self) -> str:
        """Generate report header."""
        return f"""# Chatbot Accuracy Evaluation Report

**Report Generated:** {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}

**Document Version:** 1.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [QnA Accuracy Results](#qna-accuracy-results)
   - Answer Accuracy Metrics
   - Retrieval Accuracy
   - Performance Metrics
   - Quality Distribution
   - Category Performance Analysis
   - Top & Bottom Performers
3. [PDF RAG Accuracy Results](#pdf-rag-accuracy-results)
   - Answer Quality Metrics
   - Retrieval Quality Metrics
   - Performance Metrics
   - Difficulty Analysis
   - Document Accuracy
   - Context Type Performance
4. [Comparative Analysis](#comparative-analysis)
5. [Detailed Test Results](#detailed-test-results)
   - QnA Raw Results with Metrics
   - PDF RAG Raw Results with Retrieval Analysis
6. [Insights & Recommendations](#insights--recommendations)
7. [Methodology](#methodology)
8. [Appendix](#appendix)

---"""
    
    def _generate_executive_summary(
        self,
        qna_report: Dict[str, Any],
        pdf_report: Dict[str, Any]
    ) -> str:
        """Generate executive summary."""
        summary = """## Executive Summary

### Overview

This report provides a comprehensive evaluation of the chatbot's accuracy across two primary use cases:
- **QnA (FAQ-based):** Direct question-answering using FAQ knowledge base
- **PDF RAG:** Document retrieval and answer generation from PDF documents

### Purpose

The objective of this evaluation is to assess the chatbot's ability to provide accurate, relevant, and timely responses across different content types. This analysis helps identify strengths, weaknesses, and areas for improvement in the chatbot system.

### Key Findings"""
        
        findings = []
        
        if qna_report and qna_report.get('aggregate_metrics'):
            agg = qna_report['aggregate_metrics']
            summary_data = qna_report.get('summary', {})
            
            findings.append(f"""
#### QnA Performance
- **Overall Accuracy:** {agg['semantic_similarity']['mean']:.1%}
- **Tests Conducted:** {summary_data.get('total_tests', 0)}
- **Success Rate:** {(summary_data.get('successful_tests', 0) / max(summary_data.get('total_tests', 1), 1)):.1%}
- **Average Response Time:** {agg['performance']['avg_response_time_seconds']:.2f}s
- **Retrieval Accuracy:** {agg.get('retrieval_accuracy', {}).get('accuracy', 0):.1%}""")
        
        if pdf_report and pdf_report.get('aggregate_metrics'):
            agg = pdf_report['aggregate_metrics']
            summary_data = pdf_report.get('summary', {})
            
            findings.append(f"""
#### PDF RAG Performance
- **Answer Quality:** {agg['answer_quality']['semantic_similarity']['mean']:.1%}
- **Tests Conducted:** {summary_data.get('total_tests', 0)}
- **Success Rate:** {(summary_data.get('successful_tests', 0) / max(summary_data.get('total_tests', 1), 1)):.1%}
- **Average Response Time:** {agg['performance']['avg_response_time_seconds']:.2f}s
- **Document Retrieval F1:** {agg['retrieval_quality']['document_f1']:.1%}
- **Page Retrieval F1:** {agg['retrieval_quality']['page_f1']:.1%}""")
        
        if findings:
            summary += '\n'.join(findings)
        else:
            summary += "\n\n*No test results available. Please run accuracy tests first.*"
        
        return summary
    
    def _generate_qna_section(self, qna_report: Dict[str, Any]) -> str:
        """Generate QnA accuracy section."""
        agg = qna_report.get('aggregate_metrics', {})
        summary = qna_report.get('summary', {})
        config = qna_report.get('test_config', {})
        
        section = f"""## QnA Accuracy Results

### Test Configuration

- **Dataset ID:** `{qna_report.get('dataset_id', 'N/A')}`
- **Persona ID:** `{qna_report.get('persona_id', 'N/A')}`
- **Top K Retrieved:** {config.get('top_k', 'N/A')}
- **Similarity Threshold:** {config.get('similarity_threshold', 'N/A')}
- **Total Test Cases:** {summary.get('total_tests', 0)}

### Overall Performance

#### Test Execution Summary

| Metric | Value |
|--------|-------|
| Total Tests | {summary.get('total_tests', 0)} |
| Successful Tests | {summary.get('successful_tests', 0)} |
| Failed Tests | {summary.get('failed_tests', 0)} |
| Success Rate | {(summary.get('successful_tests', 0) / max(summary.get('total_tests', 1), 1)):.1%} |

### Answer Accuracy Metrics

Answer accuracy measures how well the generated responses match expected answers using multiple evaluation techniques.

#### Semantic Similarity

Measures the semantic meaning similarity between generated and expected answers using embeddings.

| Statistic | Value |
|-----------|-------|
| **Mean** | **{agg.get('semantic_similarity', {}).get('mean', 0):.4f} ({agg.get('semantic_similarity', {}).get('mean', 0):.1%})** |
| Minimum | {agg.get('semantic_similarity', {}).get('min', 0):.4f} |
| Maximum | {agg.get('semantic_similarity', {}).get('max', 0):.4f} |
| Median | {agg.get('semantic_similarity', {}).get('median', 0):.4f} |

**Interpretation:** {self._interpret_semantic_similarity(agg.get('semantic_similarity', {}).get('mean', 0))}

#### BLEU Score

Measures n-gram overlap between generated and expected answers (common in machine translation evaluation).

| Statistic | Value |
|-----------|-------|
| **Mean** | **{agg.get('bleu_score', {}).get('mean', 0):.4f}** |
| Minimum | {agg.get('bleu_score', {}).get('min', 0):.4f} |
| Maximum | {agg.get('bleu_score', {}).get('max', 0):.4f} |
| Median | {agg.get('bleu_score', {}).get('median', 0):.4f} |

**Interpretation:** {self._interpret_bleu_score(agg.get('bleu_score', {}).get('mean', 0))}

#### Word Overlap Ratio

Measures word-level overlap between generated and expected answers.

| Statistic | Value |
|-----------|-------|
| **Mean** | **{agg.get('word_overlap_ratio', {}).get('mean', 0):.4f}** |
| Minimum | {agg.get('word_overlap_ratio', {}).get('min', 0):.4f} |
| Maximum | {agg.get('word_overlap_ratio', {}).get('max', 0):.4f} |
| Median | {agg.get('word_overlap_ratio', {}).get('median', 0):.4f} |

### Retrieval Accuracy

Evaluates whether the correct FAQ was retrieved from the knowledge base.

| Metric | Value |
|--------|-------|
| **Retrieval Accuracy** | **{agg.get('retrieval_accuracy', {}).get('accuracy', 0):.1%}** |
| Correct Retrievals | {agg.get('retrieval_accuracy', {}).get('correct_retrievals', 0)} |
| Total with Expected FAQ | {agg.get('retrieval_accuracy', {}).get('total_with_expected_faq', 0)} |
| Average Retrieval Rank | {agg.get('retrieval_rank', {}).get('mean', 0):.2f} |
| Median Retrieval Rank | {agg.get('retrieval_rank', {}).get('median', 0):.0f} |

**Interpretation:** {self._interpret_retrieval_accuracy(agg.get('retrieval_accuracy', {}).get('accuracy', 0))}

### Performance Metrics

#### Response Time Analysis

| Metric | Value |
|--------|-------|
| Average Response Time | {agg.get('performance', {}).get('avg_response_time_seconds', 0):.2f}s |
| Minimum Response Time | {agg.get('performance', {}).get('min_response_time_seconds', 0):.2f}s |
| Maximum Response Time | {agg.get('performance', {}).get('max_response_time_seconds', 0):.2f}s |

**SLA Compliance:** {self._check_sla_compliance(agg.get('performance', {}).get('avg_response_time_seconds', 0))}

#### Token Usage

| Metric | Value |
|--------|-------|
| Average Tokens per Response | {agg.get('performance', {}).get('avg_total_tokens', 0):.0f} |
| Total Tokens Used | {agg.get('performance', {}).get('total_tokens_used', 0):,} |

**Cost Efficiency:** {self._analyze_token_efficiency(agg.get('performance', {}).get('avg_total_tokens', 0))}

### Quality Distribution

Based on semantic similarity scores:

{self._generate_quality_distribution(qna_report.get('test_results', []))}

### Performance Distribution

{self._generate_response_time_distribution(qna_report.get('test_results', []))}

### Category Performance Analysis

{self._generate_category_performance_table(qna_report.get('test_results', []))}

### Top Performing Test Cases

{self._generate_top_test_cases(qna_report.get('test_results', []), 'qna', top_n=5)}

### Lowest Performing Test Cases

{self._generate_bottom_test_cases(qna_report.get('test_results', []), 'qna', bottom_n=5)}

### Metrics Correlation Analysis

{self._generate_metrics_correlation(qna_report.get('test_results', []))}"""
        
        return section
    
    def _generate_pdf_section(self, pdf_report: Dict[str, Any]) -> str:
        """Generate PDF accuracy section."""
        agg = pdf_report.get('aggregate_metrics', {})
        summary = pdf_report.get('summary', {})
        config = pdf_report.get('test_config', {})
        
        section = f"""## PDF RAG Accuracy Results

### Test Configuration

- **Dataset ID:** `{pdf_report.get('dataset_id', 'N/A')}`
- **Persona ID:** `{pdf_report.get('persona_id', 'N/A')}`
- **Top K Retrieved:** {config.get('top_k', 'N/A')}
- **Similarity Threshold:** {config.get('similarity_threshold', 'N/A')}
- **Total Test Cases:** {summary.get('total_tests', 0)}

### Overall Performance

#### Test Execution Summary

| Metric | Value |
|--------|-------|
| Total Tests | {summary.get('total_tests', 0)} |
| Successful Tests | {summary.get('successful_tests', 0)} |
| Failed Tests | {summary.get('failed_tests', 0)} |
| Success Rate | {(summary.get('successful_tests', 0) / max(summary.get('total_tests', 1), 1)):.1%} |

### Answer Quality Metrics

#### Semantic Similarity

| Statistic | Value |
|-----------|-------|
| **Mean** | **{agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0):.4f} ({agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0):.1%})** |
| Minimum | {agg.get('answer_quality', {}).get('semantic_similarity', {}).get('min', 0):.4f} |
| Maximum | {agg.get('answer_quality', {}).get('semantic_similarity', {}).get('max', 0):.4f} |

**Interpretation:** {self._interpret_semantic_similarity(agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0))}

#### BLEU Score

| Statistic | Value |
|-----------|-------|
| **Mean** | **{agg.get('answer_quality', {}).get('bleu_score', {}).get('mean', 0):.4f}** |
| Minimum | {agg.get('answer_quality', {}).get('bleu_score', {}).get('min', 0):.4f} |
| Maximum | {agg.get('answer_quality', {}).get('bleu_score', {}).get('max', 0):.4f} |

#### ROUGE-L F1 Score

Measures longest common subsequence overlap, good for evaluating summarization quality.

| Statistic | Value |
|-----------|-------|
| **Mean** | **{agg.get('answer_quality', {}).get('rouge_l_f1', {}).get('mean', 0):.4f}** |
| Minimum | {agg.get('answer_quality', {}).get('rouge_l_f1', {}).get('min', 0):.4f} |
| Maximum | {agg.get('answer_quality', {}).get('rouge_l_f1', {}).get('max', 0):.4f} |

### Retrieval Quality Metrics

Evaluates how well the system retrieves relevant document chunks and pages.

#### Document Retrieval

| Metric | Value |
|--------|-------|
| **Precision** | **{agg.get('retrieval_quality', {}).get('document_precision', 0):.1%}** |
| **Recall** | **{agg.get('retrieval_quality', {}).get('document_recall', 0):.1%}** |
| **F1 Score** | **{agg.get('retrieval_quality', {}).get('document_f1', 0):.1%}** |

**Interpretation:** {self._interpret_retrieval_f1(agg.get('retrieval_quality', {}).get('document_f1', 0), 'document')}

#### Page Retrieval

| Metric | Value |
|--------|-------|
| **Precision** | **{agg.get('retrieval_quality', {}).get('page_precision', 0):.1%}** |
| **Recall** | **{agg.get('retrieval_quality', {}).get('page_recall', 0):.1%}** |
| **F1 Score** | **{agg.get('retrieval_quality', {}).get('page_f1', 0):.1%}** |

**Interpretation:** {self._interpret_retrieval_f1(agg.get('retrieval_quality', {}).get('page_f1', 0), 'page')}

### Source Quality

#### Citation Quality

| Metric | Value |
|--------|-------|
| Average Source Confidence | {agg.get('source_quality', {}).get('avg_confidence', 0):.4f} |
| Source Diversity Score | {agg.get('source_quality', {}).get('diversity_score', 0):.4f} |

**Interpretation:** {self._interpret_source_quality(agg.get('source_quality', {}))}

### Performance Metrics

#### Response Time Analysis

| Metric | Value |
|--------|-------|
| Average Response Time | {agg.get('performance', {}).get('avg_response_time_seconds', 0):.2f}s |
| Average Retrieval Latency | {agg.get('performance', {}).get('avg_retrieval_latency_ms', 0):.0f}ms |
| Average LLM Latency | {agg.get('performance', {}).get('avg_llm_latency_ms', 0):.0f}ms |

**SLA Compliance:** {self._check_sla_compliance(agg.get('performance', {}).get('avg_response_time_seconds', 0))}

#### Token Usage

| Metric | Value |
|--------|-------|
| Average Tokens per Response | {agg.get('performance', {}).get('avg_total_tokens', 0):.0f} |

**Cost Efficiency:** {self._analyze_token_efficiency(agg.get('performance', {}).get('avg_total_tokens', 0))}

### Quality Distribution by Difficulty

{self._generate_difficulty_analysis(pdf_report.get('test_results', []))}

### Document Retrieval Accuracy by Document

{self._generate_document_accuracy_table(pdf_report.get('test_results', []))}

### Performance Distribution

{self._generate_response_time_distribution(pdf_report.get('test_results', []))}

### Top Performing Test Cases

{self._generate_top_test_cases(pdf_report.get('test_results', []), 'pdf', top_n=5)}

### Lowest Performing Test Cases

{self._generate_bottom_test_cases(pdf_report.get('test_results', []), 'pdf', bottom_n=5)}

### Context Type Performance

{self._generate_context_type_analysis(pdf_report.get('test_results', []))}"""
        
        return section
    
    def _generate_comparative_analysis(
        self,
        qna_report: Dict[str, Any],
        pdf_report: Dict[str, Any]
    ) -> str:
        """Generate comparative analysis section."""
        qna_agg = qna_report.get('aggregate_metrics', {})
        pdf_agg = pdf_report.get('aggregate_metrics', {})
        
        section = f"""## Comparative Analysis

### QnA vs PDF RAG Performance

#### Answer Accuracy Comparison

| Metric | QnA | PDF RAG | Difference |
|--------|-----|---------|------------|
| Semantic Similarity | {qna_agg.get('semantic_similarity', {}).get('mean', 0):.1%} | {pdf_agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0):.1%} | {self._calculate_difference(qna_agg.get('semantic_similarity', {}).get('mean', 0), pdf_agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0))} |
| BLEU Score | {qna_agg.get('bleu_score', {}).get('mean', 0):.4f} | {pdf_agg.get('answer_quality', {}).get('bleu_score', {}).get('mean', 0):.4f} | {self._calculate_difference(qna_agg.get('bleu_score', {}).get('mean', 0), pdf_agg.get('answer_quality', {}).get('bleu_score', {}).get('mean', 0))} |

#### Performance Comparison

| Metric | QnA | PDF RAG | Difference |
|--------|-----|---------|------------|
| Avg Response Time | {qna_agg.get('performance', {}).get('avg_response_time_seconds', 0):.2f}s | {pdf_agg.get('performance', {}).get('avg_response_time_seconds', 0):.2f}s | {self._calculate_difference(qna_agg.get('performance', {}).get('avg_response_time_seconds', 0), pdf_agg.get('performance', {}).get('avg_response_time_seconds', 0))} |
| Avg Tokens | {qna_agg.get('performance', {}).get('avg_total_tokens', 0):.0f} | {pdf_agg.get('performance', {}).get('avg_total_tokens', 0):.0f} | {self._calculate_difference(qna_agg.get('performance', {}).get('avg_total_tokens', 0), pdf_agg.get('performance', {}).get('avg_total_tokens', 0))} |

### Key Observations

{self._generate_comparative_observations(qna_agg, pdf_agg)}

### Strengths and Weaknesses

#### QnA Strengths
- Direct FAQ matching provides high precision for known questions
- Faster response times due to simpler retrieval
- Lower token usage and computational cost

#### QnA Weaknesses
- Limited to pre-defined FAQ knowledge
- Cannot handle complex multi-part questions
- Struggles with paraphrased questions

#### PDF RAG Strengths
- Can answer questions from any part of documents
- Handles complex, multi-faceted questions
- Provides source citations with page numbers

#### PDF RAG Weaknesses
- Higher latency due to document chunking retrieval
- More token usage for longer context
- Requires careful tuning of retrieval parameters"""
        
        return section
    
    def _generate_insights_recommendations(
        self,
        qna_report: Dict[str, Any],
        pdf_report: Dict[str, Any]
    ) -> str:
        """Generate insights and recommendations section."""
        insights = []
        recommendations = []
        
        # Analyze QnA results
        if qna_report and qna_report.get('aggregate_metrics'):
            agg = qna_report['aggregate_metrics']
            
            # Semantic similarity insights
            sem_sim = agg.get('semantic_similarity', {}).get('mean', 0)
            if sem_sim < 0.7:
                insights.append("⚠️ QnA semantic similarity is below target threshold (70%)")
                recommendations.append("**Improve FAQ Quality:** Review and enhance FAQ answers with more detailed, accurate information")
                recommendations.append("**Expand Knowledge Base:** Add more FAQ variations and synonyms to improve matching")
            elif sem_sim >= 0.85:
                insights.append("✅ QnA semantic similarity is excellent (>85%)")
            
            # Retrieval accuracy insights
            ret_acc = agg.get('retrieval_accuracy', {}).get('accuracy', 0)
            if ret_acc < 0.8:
                insights.append(f"⚠️ QnA retrieval accuracy is {ret_acc:.1%}, below 80% target")
                recommendations.append("**Optimize Embeddings:** Consider fine-tuning embeddings for domain-specific language")
                recommendations.append("**Adjust Similarity Threshold:** Current threshold may be too strict, consider lowering from 0.7 to 0.65")
            
            # Response time insights
            resp_time = agg.get('performance', {}).get('avg_response_time_seconds', 0)
            if resp_time > 3.0:
                insights.append(f"⚠️ QnA average response time is {resp_time:.2f}s, exceeds 3s target")
                recommendations.append("**Optimize Database Queries:** Add indexes on embedding columns and dataset_id")
                recommendations.append("**Implement Caching:** Cache frequently asked questions to reduce computation")
        
        # Analyze PDF results
        if pdf_report and pdf_report.get('aggregate_metrics'):
            agg = pdf_report['aggregate_metrics']
            
            # Answer quality insights
            sem_sim = agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0)
            if sem_sim < 0.7:
                insights.append("⚠️ PDF RAG answer quality is below target (70%)")
                recommendations.append("**Improve Chunking Strategy:** Optimize chunk size and overlap for better context preservation")
                recommendations.append("**Enhance Prompts:** Refine system prompts to guide more accurate answer generation")
            
            # Retrieval quality insights
            doc_f1 = agg.get('retrieval_quality', {}).get('document_f1', 0)
            page_f1 = agg.get('retrieval_quality', {}).get('page_f1', 0)
            
            if doc_f1 < 0.7:
                insights.append(f"⚠️ Document retrieval F1 is {doc_f1:.1%}, needs improvement")
                recommendations.append("**Implement Hybrid Search:** Combine dense embeddings with BM25 keyword search for better retrieval")
                recommendations.append("**Add Metadata Filtering:** Use document type and category metadata to narrow search space")
            
            if page_f1 < 0.6:
                insights.append(f"⚠️ Page retrieval F1 is {page_f1:.1%}, indicating imprecise citations")
                recommendations.append("**Improve Page Attribution:** Enhance chunking to maintain accurate page number tracking")
                recommendations.append("**Implement Reranking:** Use cross-encoder models to rerank retrieved chunks for better precision")
            
            # Performance insights
            resp_time = agg.get('performance', {}).get('avg_response_time_seconds', 0)
            if resp_time > 5.0:
                insights.append(f"⚠️ PDF RAG response time is {resp_time:.2f}s, exceeds 5s target")
                recommendations.append("**Optimize Vector Search:** Implement approximate nearest neighbor search (FAISS, Pinecone)")
                recommendations.append("**Reduce Context Size:** Limit number of retrieved chunks to balance quality and speed")
        
        # Generate section
        section = """## Insights & Recommendations

### Key Insights

"""
        
        if insights:
            for insight in insights:
                section += f"\n{insight}\n"
        else:
            section += "\n*Analysis complete. All metrics are within acceptable ranges.*\n"
        
        section += "\n### Recommendations\n"
        
        if recommendations:
            for idx, rec in enumerate(recommendations, 1):
                section += f"\n{idx}. {rec}\n"
        else:
            section += "\n*Continue current approach and monitor metrics over time.*\n"
        
        section += """
### Action Items

#### Immediate Actions (1-2 weeks)
- [ ] Review test results with development team
- [ ] Identify and fix critical failures in test cases
- [ ] Implement quick wins (caching, query optimization)

#### Short-term Actions (1 month)
- [ ] Enhance FAQ knowledge base based on low-scoring queries
- [ ] Optimize PDF chunking strategy and parameters
- [ ] Implement monitoring dashboard for production metrics

#### Long-term Actions (3+ months)
- [ ] Evaluate advanced RAG techniques (hybrid search, reranking)
- [ ] Consider fine-tuning embeddings for domain-specific use
- [ ] Implement continuous evaluation pipeline with real user queries

### Success Criteria

**Target Metrics for Production:**

| Metric | QnA Target | PDF RAG Target |
|--------|-----------|----------------|
| Semantic Similarity | ≥ 85% | ≥ 80% |
| Retrieval Accuracy/F1 | ≥ 90% | ≥ 75% |
| Response Time | < 2s | < 4s |
| User Satisfaction | ≥ 4.0/5.0 | ≥ 4.0/5.0 |"""
        
        return section
    
    def _generate_methodology(self) -> str:
        """Generate methodology section."""
        return """## Methodology

### Testing Framework

This accuracy evaluation uses a comprehensive testing framework designed to measure chatbot performance across multiple dimensions.

#### Test Data Preparation

1. **QnA Test Data**
   - Seeded FAQ knowledge base with 15+ diverse question-answer pairs
   - Generated test cases including exact matches and paraphrased variations
   - Categories: general, account, payment, policy, shipping, support

2. **PDF Test Data**
   - Created 3 test documents: company policy, product guide, financial report
   - Generated document chunks with embeddings (12 chunks total)
   - Test cases span single-page, multi-page, and cross-document questions

#### Metrics Explained

##### Answer Accuracy Metrics

1. **Semantic Similarity (Primary Metric)**
   - Measures meaning similarity using embeddings
   - Range: 0-1 (higher is better)
   - Formula: Cosine similarity between answer embeddings
   - **Interpretation:**
     - 0.85-1.0: Excellent (semantically identical)
     - 0.70-0.84: Good (same meaning, different wording)
     - 0.50-0.69: Fair (partially correct)
     - 0.00-0.49: Poor (incorrect or unrelated)

2. **BLEU Score**
   - Measures n-gram overlap (borrowed from machine translation)
   - Range: 0-1 (higher is better)
   - Good for evaluating factual accuracy and word choice

3. **ROUGE Scores**
   - ROUGE-N: N-gram overlap (recall-oriented)
   - ROUGE-L: Longest common subsequence
   - Used primarily for PDF RAG evaluation

4. **Word Overlap Ratio**
   - Simple word-level Jaccard similarity
   - Quick measure of vocabulary overlap

##### Retrieval Metrics

1. **Retrieval Accuracy (QnA)**
   - Percentage of queries where correct FAQ was retrieved
   - Binary metric: either correct or incorrect

2. **Precision, Recall, F1 (PDF RAG)**
   - **Precision:** % of retrieved items that are relevant
   - **Recall:** % of relevant items that were retrieved
   - **F1:** Harmonic mean of precision and recall

##### Performance Metrics

1. **Response Time**
   - End-to-end latency from question to answer
   - Includes retrieval, LLM generation, and processing

2. **Token Usage**
   - Total tokens consumed (prompt + completion)
   - Important for cost optimization

### Test Execution Process

1. **Seeding Phase**
   - Run seeder scripts to populate database with test data
   - Generate embeddings for all FAQs and document chunks

2. **Testing Phase**
   - Execute test cases sequentially
   - Collect metrics for each test
   - Handle errors gracefully

3. **Analysis Phase**
   - Aggregate metrics across all tests
   - Calculate statistical measures (mean, min, max, median)
   - Generate insights and recommendations

4. **Reporting Phase**
   - Compile results into comprehensive report
   - Provide actionable insights for improvement

### Limitations

- **Test data size:** Limited to seeded test cases (may not cover all edge cases)
- **Ground truth:** Expected answers are manually created (subjective)
- **Semantic similarity:** Relies on embedding quality (may not capture all nuances)
- **Static evaluation:** Does not capture real user behavior and preferences"""
    
    def _generate_appendix(self) -> str:
        """Generate appendix section."""
        return """## Appendix

### Running the Tests

#### Prerequisites

```bash
# Ensure environment is set up
pip install -r requirements.txt

# Configure environment variables
export DATABASE_URL="postgresql://..."
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="..."
```

#### Seed Test Data

```bash
# Seed QnA test data
python tests/accuracy/seeders/qna_test_seeder.py

# Seed PDF test data
python tests/accuracy/seeders/pdf_test_seeder.py
```

#### Run Accuracy Tests

```bash
# Run QnA accuracy test
python tests/accuracy/test_qna_accuracy.py \
  --persona-id <PERSONA_ID> \
  --dataset-id <DATASET_ID> \
  --test-file tests/accuracy/test_data/qna_test_cases.json \
  --output tests/accuracy/results/qna_accuracy_report.json

# Run PDF accuracy test
python tests/accuracy/test_pdf_accuracy.py \
  --persona-id <PERSONA_ID> \
  --dataset-id <DATASET_ID> \
  --test-file tests/accuracy/test_data/pdf_test_cases.json \
  --output tests/accuracy/results/pdf_accuracy_report.json
```

#### Generate Report

```bash
python tests/accuracy/generate_report.py \
  --qna-report tests/accuracy/results/qna_accuracy_report.json \
  --pdf-report tests/accuracy/results/pdf_accuracy_report.json \
  --output docs/CHATBOT_ACCURACY_REPORT.md
```

### Test Data Structure

#### QnA Test Case Format

```json
{
  "question": "User question text",
  "expected_answer": "Expected answer text",
  "expected_faq_id": "UUID of the FAQ that should be retrieved",
  "category": "Category for grouping (e.g., 'policy', 'technical')",
  "difficulty": "easy|medium|hard",
  "test_type": "exact_match|paraphrase"
}
```

#### PDF Test Case Format

```json
{
  "question": "User question text",
  "expected_answer": "Expected answer text",
  "expected_document_ids": ["doc_uuid1", "doc_uuid2"],
  "expected_pages": [1, 5, 10],
  "category": "Category for grouping",
  "difficulty": "easy|medium|hard",
  "context_type": "single_page|multi_page|cross_document"
}
```

### References

- **BLEU Score:** Papineni et al. (2002) - "BLEU: a Method for Automatic Evaluation of Machine Translation"
- **ROUGE Score:** Lin (2004) - "ROUGE: A Package for Automatic Evaluation of Summaries"
- **RAG (Retrieval-Augmented Generation):** Lewis et al. (2020) - "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
- **Cosine Similarity:** Standard metric for measuring vector similarity in NLP

---

**Report End**

*For questions or issues, please contact the development team.*"""
    
    # Helper methods for interpretation
    
    def _interpret_semantic_similarity(self, score: float) -> str:
        """Interpret semantic similarity score."""
        if score >= 0.85:
            return "✅ Excellent - Responses are semantically very similar to expected answers"
        elif score >= 0.70:
            return "✓ Good - Responses capture the correct meaning with different wording"
        elif score >= 0.50:
            return "⚠️ Fair - Responses are partially correct but may miss key information"
        else:
            return "❌ Poor - Responses are largely incorrect or unrelated to expected answers"
    
    def _interpret_bleu_score(self, score: float) -> str:
        """Interpret BLEU score."""
        if score >= 0.40:
            return "Excellent - High n-gram overlap with expected answers"
        elif score >= 0.25:
            return "Good - Moderate overlap, acceptable word choice"
        elif score >= 0.10:
            return "Fair - Some overlap, but significant differences in wording"
        else:
            return "Poor - Very low n-gram overlap with expected answers"
    
    def _interpret_retrieval_accuracy(self, score: float) -> str:
        """Interpret retrieval accuracy."""
        if score >= 0.90:
            return "✅ Excellent - System reliably retrieves correct FAQs"
        elif score >= 0.75:
            return "✓ Good - Majority of queries retrieve correct FAQs"
        elif score >= 0.60:
            return "⚠️ Fair - Room for improvement in retrieval precision"
        else:
            return "❌ Poor - System struggles to retrieve correct FAQs"
    
    def _interpret_retrieval_f1(self, score: float, item_type: str) -> str:
        """Interpret retrieval F1 score."""
        if score >= 0.80:
            return f"✅ Excellent - System accurately retrieves relevant {item_type}s"
        elif score >= 0.60:
            return f"✓ Good - Acceptable {item_type} retrieval with room for improvement"
        elif score >= 0.40:
            return f"⚠️ Fair - {item_type.capitalize()} retrieval needs optimization"
        else:
            return f"❌ Poor - System struggles with {item_type} retrieval"
    
    def _interpret_source_quality(self, source_quality: Dict[str, float]) -> str:
        """Interpret source quality metrics."""
        confidence = source_quality.get('avg_confidence', 0)
        diversity = source_quality.get('diversity_score', 0)
        
        interpretations = []
        
        if confidence >= 0.80:
            interpretations.append("High confidence in retrieved sources")
        elif confidence >= 0.70:
            interpretations.append("Good confidence in retrieved sources")
        else:
            interpretations.append("Lower confidence suggests retrieval optimization needed")
        
        if diversity >= 0.70:
            interpretations.append("Good diversity across multiple documents")
        elif diversity >= 0.50:
            interpretations.append("Moderate diversity in sources")
        else:
            interpretations.append("Low diversity - may over-rely on single documents")
        
        return " | ".join(interpretations)
    
    def _check_sla_compliance(self, response_time: float) -> str:
        """Check SLA compliance for response time."""
        if response_time <= 2.0:
            return "✅ Excellent - Well within target (<2s)"
        elif response_time <= 3.0:
            return "✓ Good - Within acceptable range (2-3s)"
        elif response_time <= 5.0:
            return "⚠️ Acceptable - Approaching limit (3-5s)"
        else:
            return "❌ Needs Improvement - Exceeds 5s target"
    
    def _analyze_token_efficiency(self, avg_tokens: float) -> str:
        """Analyze token usage efficiency."""
        if avg_tokens <= 300:
            return "✅ Efficient - Low token usage, good cost optimization"
        elif avg_tokens <= 500:
            return "✓ Acceptable - Moderate token usage"
        elif avg_tokens <= 800:
            return "⚠️ High - Consider optimizing prompt length"
        else:
            return "❌ Very High - Significant cost impact, needs optimization"
    
    def _generate_quality_distribution(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate quality distribution analysis."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Categorize by semantic similarity
        excellent = sum(1 for r in successful if r.get('metrics', {}).get('semantic_similarity', 0) >= 0.85)
        good = sum(1 for r in successful if 0.70 <= r.get('metrics', {}).get('semantic_similarity', 0) < 0.85)
        fair = sum(1 for r in successful if 0.50 <= r.get('metrics', {}).get('semantic_similarity', 0) < 0.70)
        poor = sum(1 for r in successful if r.get('metrics', {}).get('semantic_similarity', 0) < 0.50)
        
        total = len(successful)
        
        return f"""
| Quality Level | Count | Percentage |
|--------------|-------|------------|
| Excellent (≥0.85) | {excellent} | {(excellent/total*100):.1f}% |
| Good (0.70-0.84) | {good} | {(good/total*100):.1f}% |
| Fair (0.50-0.69) | {fair} | {(fair/total*100):.1f}% |
| Poor (<0.50) | {poor} | {(poor/total*100):.1f}% |
| **Total** | **{total}** | **100%** |"""
    
    def _generate_difficulty_analysis(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate analysis by difficulty level."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Group by difficulty
        difficulties = {}
        for r in successful:
            diff = r.get('test_case', {}).get('difficulty', 'unknown')
            if diff not in difficulties:
                difficulties[diff] = []
            difficulties[diff].append(r.get('metrics', {}).get('semantic_similarity', 0))
        
        if not difficulties:
            return "*No difficulty data available*"
        
        output = "\n| Difficulty | Tests | Avg Semantic Similarity |\n"
        output += "|------------|-------|------------------------|\n"
        
        for diff in ['easy', 'medium', 'hard']:
            if diff in difficulties:
                scores = difficulties[diff]
                avg = sum(scores) / len(scores)
                output += f"| {diff.capitalize()} | {len(scores)} | {avg:.1%} |\n"
        
        return output
    
    def _calculate_difference(self, val1: float, val2: float) -> str:
        """Calculate and format difference between two values."""
        if val1 == 0 and val2 == 0:
            return "0.0%"
        
        diff = val2 - val1
        if abs(val1) > 0:
            pct_diff = (diff / abs(val1)) * 100
            sign = "+" if diff > 0 else ""
            return f"{sign}{pct_diff:.1f}%"
        else:
            return "N/A"
    
    def _generate_comparative_observations(
        self,
        qna_agg: Dict[str, Any],
        pdf_agg: Dict[str, Any]
    ) -> str:
        """Generate observations from comparative analysis."""
        observations = []
        
        # Compare semantic similarity
        qna_sem = qna_agg.get('semantic_similarity', {}).get('mean', 0)
        pdf_sem = pdf_agg.get('answer_quality', {}).get('semantic_similarity', {}).get('mean', 0)
        
        if qna_sem > pdf_sem:
            diff = qna_sem - pdf_sem
            observations.append(f"- QnA shows {diff:.1%} higher semantic similarity than PDF RAG, likely due to exact FAQ matching")
        else:
            diff = pdf_sem - qna_sem
            observations.append(f"- PDF RAG achieves {diff:.1%} higher semantic similarity despite more complex retrieval")
        
        # Compare response times
        qna_time = qna_agg.get('performance', {}).get('avg_response_time_seconds', 0)
        pdf_time = pdf_agg.get('performance', {}).get('avg_response_time_seconds', 0)
        
        if pdf_time > qna_time:
            time_diff = pdf_time - qna_time
            observations.append(f"- PDF RAG takes {time_diff:.2f}s longer on average due to document chunking retrieval")
        
        # Compare token usage
        qna_tokens = qna_agg.get('performance', {}).get('avg_total_tokens', 0)
        pdf_tokens = pdf_agg.get('performance', {}).get('avg_total_tokens', 0)
        
        if pdf_tokens > qna_tokens:
            token_diff = pdf_tokens - qna_tokens
            observations.append(f"- PDF RAG uses {token_diff:.0f} more tokens per response due to larger context windows")
        
        if not observations:
            observations.append("- Both systems show comparable performance across key metrics")
        
        return '\n'.join(observations)
    
    def _generate_response_time_distribution(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate response time distribution table."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Get response times
        times = [r.get('metrics', {}).get('response_time_seconds', 0) for r in successful]
        if not times:
            return "*No response time data*"
        
        # Categorize
        fast = sum(1 for t in times if t <= 2.0)
        medium = sum(1 for t in times if 2.0 < t <= 4.0)
        slow = sum(1 for t in times if t > 4.0)
        total = len(times)
        
        avg_time = sum(times) / total
        min_time = min(times)
        max_time = max(times)
        
        return f"""
**Response Time Statistics:**
- Average: {avg_time:.2f}s
- Minimum: {min_time:.2f}s
- Maximum: {max_time:.2f}s

**Distribution:**

| Speed Category | Time Range | Count | Percentage | Visual |
|---------------|------------|-------|------------|--------|
| Fast | ≤ 2.0s | {fast} | {(fast/total*100):.1f}% | {'█' * int(fast/total*20)} |
| Medium | 2.0s - 4.0s | {medium} | {(medium/total*100):.1f}% | {'█' * int(medium/total*20)} |
| Slow | > 4.0s | {slow} | {(slow/total*100):.1f}% | {'█' * int(slow/total*20)} |
| **Total** | | **{total}** | **100%** | |"""
    
    def _generate_category_performance_table(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate detailed category performance analysis."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Group by category
        categories = {}
        for r in successful:
            cat = r.get('test_case', {}).get('category', 'unknown')
            if cat not in categories:
                categories[cat] = {
                    'semantic': [],
                    'bleu': [],
                    'retrieval': [],
                    'time': []
                }
            
            metrics = r.get('metrics', {})
            categories[cat]['semantic'].append(metrics.get('semantic_similarity', 0))
            categories[cat]['bleu'].append(metrics.get('bleu_score', 0))
            categories[cat]['retrieval'].append(1 if metrics.get('retrieval_correct') else 0)
            categories[cat]['time'].append(metrics.get('response_time_seconds', 0))
        
        if not categories:
            return "*No category data available*"
        
        output = "\n| Category | Tests | Avg Semantic | Avg BLEU | Retrieval Acc | Avg Time | Grade |\n"
        output += "|----------|-------|--------------|----------|---------------|----------|-------|\n"
        
        for cat in sorted(categories.keys()):
            data = categories[cat]
            count = len(data['semantic'])
            avg_sem = sum(data['semantic']) / count
            avg_bleu = sum(data['bleu']) / count
            ret_acc = sum(data['retrieval']) / count
            avg_time = sum(data['time']) / count
            grade = self._calculate_grade(avg_sem)
            
            output += f"| {cat.capitalize():<12} | {count:>5} | {avg_sem:>12.1%} | {avg_bleu:>8.4f} | {ret_acc:>13.1%} | {avg_time:>8.2f}s | {grade:>5} |\n"
        
        return output
    
    def _generate_top_test_cases(self, test_results: List[Dict[str, Any]], test_type: str, top_n: int = 5) -> str:
        """Generate table of top performing test cases."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Sort by semantic similarity
        sorted_results = sorted(
            successful,
            key=lambda x: x.get('metrics', {}).get('semantic_similarity', 0),
            reverse=True
        )[:top_n]
        
        output = "\n| # | Question | Semantic | BLEU | Response Time |\n"
        output += "|---|----------|----------|------|---------------|\n"
        
        for idx, r in enumerate(sorted_results, 1):
            tc = r.get('test_case', {})
            metrics = r.get('metrics', {})
            question = tc.get('question', '')[:60] + '...' if len(tc.get('question', '')) > 60 else tc.get('question', '')
            
            output += f"| {idx} | {question} | {metrics.get('semantic_similarity', 0):.4f} | {metrics.get('bleu_score', 0):.4f} | {metrics.get('response_time_seconds', 0):.2f}s |\n"
        
        return output
    
    def _generate_bottom_test_cases(self, test_results: List[Dict[str, Any]], test_type: str, bottom_n: int = 5) -> str:
        """Generate table of lowest performing test cases with details."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Sort by semantic similarity (ascending)
        sorted_results = sorted(
            successful,
            key=lambda x: x.get('metrics', {}).get('semantic_similarity', 0)
        )[:bottom_n]
        
        output = "\n| # | Question | Semantic | BLEU | Issue |\n"
        output += "|---|----------|----------|------|-------|\n"
        
        for idx, r in enumerate(sorted_results, 1):
            tc = r.get('test_case', {})
            metrics = r.get('metrics', {})
            question = tc.get('question', '')[:50] + '...' if len(tc.get('question', '')) > 50 else tc.get('question', '')
            
            # Identify issue
            issue = self._identify_issue(metrics)
            
            output += f"| {idx} | {question} | {metrics.get('semantic_similarity', 0):.4f} | {metrics.get('bleu_score', 0):.4f} | {issue} |\n"
        
        return output
    
    def _generate_metrics_correlation(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate metrics correlation analysis."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful or len(successful) < 3:
            return "*Insufficient data for correlation analysis*"
        
        # Extract metrics
        semantic_scores = [r.get('metrics', {}).get('semantic_similarity', 0) for r in successful]
        bleu_scores = [r.get('metrics', {}).get('bleu_score', 0) for r in successful]
        response_times = [r.get('metrics', {}).get('response_time_seconds', 0) for r in successful]
        
        # Calculate simple correlation (Pearson-like)
        corr_sem_bleu = self._calculate_correlation(semantic_scores, bleu_scores)
        corr_sem_time = self._calculate_correlation(semantic_scores, response_times)
        
        return f"""
**Correlation Analysis:**

| Metric Pair | Correlation | Interpretation |
|-------------|-------------|----------------|
| Semantic vs BLEU | {corr_sem_bleu:+.3f} | {self._interpret_correlation(corr_sem_bleu, 'Semantic and BLEU scores')} |
| Semantic vs Response Time | {corr_sem_time:+.3f} | {self._interpret_correlation(corr_sem_time, 'Quality and response time')} |

*Note: Correlation ranges from -1 (negative) to +1 (positive). Values near 0 indicate weak correlation.*"""
    
    def _generate_document_accuracy_table(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate per-document accuracy analysis for PDF tests."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Group by expected documents
        doc_performance = {}
        for r in successful:
            tc = r.get('test_case', {})
            expected_docs = tc.get('expected_documents', [])
            
            for doc in expected_docs:
                if doc not in doc_performance:
                    doc_performance[doc] = {
                        'semantic': [],
                        'doc_precision': [],
                        'doc_recall': [],
                        'count': 0
                    }
                
                metrics = r.get('metrics', {})
                doc_performance[doc]['semantic'].append(metrics.get('semantic_similarity', 0))
                doc_performance[doc]['doc_precision'].append(metrics.get('document_precision', 0))
                doc_performance[doc]['doc_recall'].append(metrics.get('document_recall', 0))
                doc_performance[doc]['count'] += 1
        
        if not doc_performance:
            return "*No document data available*"
        
        output = "\n| Document | Tests | Avg Semantic | Doc Precision | Doc Recall | Performance |\n"
        output += "|----------|-------|--------------|---------------|------------|-------------|\n"
        
        for doc in sorted(doc_performance.keys()):
            data = doc_performance[doc]
            count = data['count']
            avg_sem = sum(data['semantic']) / count if count > 0 else 0
            avg_prec = sum(data['doc_precision']) / count if count > 0 else 0
            avg_rec = sum(data['doc_recall']) / count if count > 0 else 0
            perf = self._calculate_performance_emoji(avg_sem)
            
            doc_short = doc[:25] + '...' if len(doc) > 25 else doc
            output += f"| {doc_short:<28} | {count:>5} | {avg_sem:>12.1%} | {avg_prec:>13.1%} | {avg_rec:>10.1%} | {perf:>11} |\n"
        
        return output
    
    def _generate_context_type_analysis(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate analysis by context type (single-page, multi-page, cross-document)."""
        if not test_results:
            return "*No data available*"
        
        successful = [r for r in test_results if r.get('status') == 'success']
        if not successful:
            return "*No successful tests*"
        
        # Group by context type
        context_types = {}
        for r in successful:
            tc = r.get('test_case', {})
            ctx_type = tc.get('context_type', 'unknown')
            
            if ctx_type not in context_types:
                context_types[ctx_type] = {
                    'semantic': [],
                    'doc_f1': [],
                    'page_f1': [],
                    'time': []
                }
            
            metrics = r.get('metrics', {})
            context_types[ctx_type]['semantic'].append(metrics.get('semantic_similarity', 0))
            context_types[ctx_type]['doc_f1'].append(metrics.get('document_f1', 0))
            context_types[ctx_type]['page_f1'].append(metrics.get('page_f1', 0))
            context_types[ctx_type]['time'].append(metrics.get('response_time_seconds', 0))
        
        if not context_types:
            return "*No context type data available*"
        
        output = "\n| Context Type | Tests | Avg Semantic | Doc F1 | Page F1 | Avg Time | Complexity |\n"
        output += "|--------------|-------|--------------|--------|---------|----------|------------|\n"
        
        complexity_order = {'single_page': 1, 'multi_page': 2, 'cross_document': 3}
        
        for ctx_type in sorted(context_types.keys(), key=lambda x: complexity_order.get(x, 99)):
            data = context_types[ctx_type]
            count = len(data['semantic'])
            avg_sem = sum(data['semantic']) / count
            avg_doc_f1 = sum(data['doc_f1']) / count
            avg_page_f1 = sum(data['page_f1']) / count
            avg_time = sum(data['time']) / count
            complexity = self._get_complexity_indicator(ctx_type)
            
            output += f"| {ctx_type.replace('_', ' ').title():<16} | {count:>5} | {avg_sem:>12.1%} | {avg_doc_f1:>6.1%} | {avg_page_f1:>7.1%} | {avg_time:>8.2f}s | {complexity:>10} |\n"
        
        return output
    
    def _generate_qna_raw_results(self, qna_report: Dict[str, Any]) -> str:
        """Generate detailed raw results section for QnA tests."""
        test_results = qna_report.get('test_results', [])
        
        if not test_results:
            return "*No test results available*"
        
        section = """## QnA Detailed Test Results

### Complete Test Case Results

This section provides a comprehensive view of all test cases with their questions, expected answers, generated answers, and metrics.

"""
        
        for idx, result in enumerate(test_results, 1):
            tc = result.get('test_case', {})
            response = result.get('response', {})
            metrics = result.get('metrics', {})
            
            grade = self._calculate_grade(metrics.get('semantic_similarity', 0))
            
            section += f"""#### Test Case #{idx}: {tc.get('category', 'general').upper()}

**Question:**
> {tc.get('question', 'N/A')}

**Expected Answer:**
> {tc.get('expected_answer', 'N/A')}

**Generated Answer:**
> {response.get('generated_answer', 'N/A')}

**Metrics:**

| Metric | Value | Status |
|--------|-------|--------|
| Semantic Similarity | {metrics.get('semantic_similarity', 0):.4f} ({metrics.get('semantic_similarity', 0):.1%}) | {self._get_status_emoji(metrics.get('semantic_similarity', 0))} |
| BLEU Score | {metrics.get('bleu_score', 0):.4f} | {self._get_status_emoji(metrics.get('bleu_score', 0), threshold=0.4)} |
| Exact Match Ratio | {metrics.get('exact_match_ratio', 0):.4f} | - |
| Word Overlap | {metrics.get('word_overlap_ratio', 0):.4f} | - |
| Retrieval Correct | {'✓ Yes' if metrics.get('retrieval_correct') else '✗ No'} | {'✅' if metrics.get('retrieval_correct') else '❌'} |
| Retrieval Rank | {metrics.get('retrieval_rank', 'N/A')} | - |
| Response Time | {metrics.get('response_time_seconds', 0):.2f}s | {self._get_time_emoji(metrics.get('response_time_seconds', 0))} |
| Total Tokens | {metrics.get('total_tokens', 0)} | - |
| **Overall Grade** | **{grade}** | |

**Source Information:**
- Sources Retrieved: {response.get('sources_count', 0)}
- Retrieved FAQ IDs: {', '.join(response.get('retrieved_faq_ids', [])[:3])}

---

"""
        
        return section
    
    def _generate_pdf_raw_results(self, pdf_report: Dict[str, Any]) -> str:
        """Generate detailed raw results section for PDF tests."""
        test_results = pdf_report.get('test_results', [])
        
        if not test_results:
            return "*No test results available*"
        
        section = """## PDF RAG Detailed Test Results

### Complete Test Case Results

This section provides a comprehensive view of all PDF RAG test cases with retrieval analysis and source citations.

"""
        
        for idx, result in enumerate(test_results, 1):
            tc = result.get('test_case', {})
            response = result.get('response', {})
            metrics = result.get('metrics', {})
            retrieval = result.get('retrieval_analysis', {})
            
            grade = self._calculate_grade(metrics.get('semantic_similarity', 0))
            
            section += f"""#### Test Case #{idx}: {tc.get('difficulty', 'medium').upper()} - {tc.get('context_type', 'unknown').upper()}

**Question:**
> {tc.get('question', 'N/A')}

**Expected Answer:**
> {tc.get('expected_answer', 'N/A')}

**Generated Answer:**
> {response.get('generated_answer', 'N/A')}

**Answer Quality Metrics:**

| Metric | Value | Status |
|--------|-------|--------|
| Semantic Similarity | {metrics.get('semantic_similarity', 0):.4f} ({metrics.get('semantic_similarity', 0):.1%}) | {self._get_status_emoji(metrics.get('semantic_similarity', 0))} |
| BLEU Score | {metrics.get('bleu_score', 0):.4f} | {self._get_status_emoji(metrics.get('bleu_score', 0), threshold=0.4)} |
| ROUGE-1 | {metrics.get('rouge1', 0):.4f} | - |
| ROUGE-2 | {metrics.get('rouge2', 0):.4f} | - |
| ROUGE-L | {metrics.get('rougeL', 0):.4f} | - |
| **Overall Grade** | **{grade}** | |

**Retrieval Quality Metrics:**

| Metric | Value | Status |
|--------|-------|--------|
| Document Precision | {metrics.get('document_precision', 0):.4f} | {self._get_status_emoji(metrics.get('document_precision', 0), threshold=0.7)} |
| Document Recall | {metrics.get('document_recall', 0):.4f} | {self._get_status_emoji(metrics.get('document_recall', 0), threshold=0.7)} |
| Document F1 | {metrics.get('document_f1', 0):.4f} | {self._get_status_emoji(metrics.get('document_f1', 0), threshold=0.7)} |
| Page Precision | {metrics.get('page_precision', 0):.4f} | {self._get_status_emoji(metrics.get('page_precision', 0), threshold=0.6)} |
| Page Recall | {metrics.get('page_recall', 0):.4f} | {self._get_status_emoji(metrics.get('page_recall', 0), threshold=0.6)} |
| Page F1 | {metrics.get('page_f1', 0):.4f} | {self._get_status_emoji(metrics.get('page_f1', 0), threshold=0.6)} |

**Document Retrieval Analysis:**

| Aspect | Details |
|--------|---------|
| Expected Documents | {', '.join(tc.get('expected_documents', []))} |
| Expected Pages | {tc.get('expected_pages', [])} |
| Retrieved Documents | {', '.join(retrieval.get('retrieved_documents', [])[:3])} |
| Retrieved Pages | {retrieval.get('retrieved_pages', [])} |
| Correct Documents | {', '.join(retrieval.get('correct_documents', []))} |
| Missing Documents | {', '.join(retrieval.get('missing_documents', [])) if retrieval.get('missing_documents') else 'None'} |
| Incorrect Documents | {', '.join(retrieval.get('incorrect_documents', [])) if retrieval.get('incorrect_documents') else 'None'} |

**Performance Metrics:**

| Metric | Value |
|--------|-------|
| Response Time | {metrics.get('response_time_seconds', 0):.2f}s {self._get_time_emoji(metrics.get('response_time_seconds', 0))} |
| Processing Time | {metrics.get('processing_time_ms', 0):.0f}ms |
| Retrieval Latency | {metrics.get('retrieval_latency_ms', 0):.0f}ms |
| LLM Latency | {metrics.get('llm_latency_ms', 0):.0f}ms |
| Total Tokens | {metrics.get('total_tokens', 0)} |
| Chunks Retrieved | {response.get('chunks_retrieved', 0)} |

---

"""
        
        return section
    
    def _calculate_grade(self, semantic_score: float) -> str:
        """Calculate letter grade from semantic similarity score."""
        if semantic_score >= 0.90:
            return "A+"
        elif semantic_score >= 0.85:
            return "A"
        elif semantic_score >= 0.80:
            return "A-"
        elif semantic_score >= 0.75:
            return "B+"
        elif semantic_score >= 0.70:
            return "B"
        elif semantic_score >= 0.65:
            return "B-"
        elif semantic_score >= 0.60:
            return "C+"
        elif semantic_score >= 0.50:
            return "C"
        else:
            return "F"
    
    def _get_status_emoji(self, score: float, threshold: float = 0.7) -> str:
        """Get status emoji based on score."""
        if score >= threshold:
            return "✅"
        elif score >= threshold * 0.85:
            return "✓"
        elif score >= threshold * 0.7:
            return "⚠️"
        else:
            return "❌"
    
    def _get_time_emoji(self, time: float, threshold: float = 3.0) -> str:
        """Get time status emoji."""
        if time <= threshold * 0.7:
            return "🚀"
        elif time <= threshold:
            return "✓"
        elif time <= threshold * 1.5:
            return "⚠️"
        else:
            return "🐌"
    
    def _identify_issue(self, metrics: Dict[str, Any]) -> str:
        """Identify primary issue with test case."""
        sem_sim = metrics.get('semantic_similarity', 0)
        retrieval = metrics.get('retrieval_correct', True)
        
        if not retrieval:
            return "Wrong FAQ retrieved"
        elif sem_sim < 0.5:
            return "Poor answer quality"
        elif sem_sim < 0.7:
            return "Incomplete answer"
        else:
            return "Minor wording difference"
    
    def _calculate_correlation(self, list1: List[float], list2: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(list1) != len(list2) or len(list1) == 0:
            return 0.0
        
        n = len(list1)
        mean1 = sum(list1) / n
        mean2 = sum(list2) / n
        
        num = sum((list1[i] - mean1) * (list2[i] - mean2) for i in range(n))
        den1 = sum((x - mean1) ** 2 for x in list1) ** 0.5
        den2 = sum((x - mean2) ** 2 for x in list2) ** 0.5
        
        if den1 == 0 or den2 == 0:
            return 0.0
        
        return num / (den1 * den2)
    
    def _interpret_correlation(self, corr: float, context: str) -> str:
        """Interpret correlation coefficient."""
        abs_corr = abs(corr)
        
        if abs_corr >= 0.7:
            strength = "Strong"
        elif abs_corr >= 0.4:
            strength = "Moderate"
        elif abs_corr >= 0.2:
            strength = "Weak"
        else:
            strength = "Very weak"
        
        direction = "positive" if corr > 0 else "negative" if corr < 0 else "no"
        
        return f"{strength} {direction} correlation"
    
    def _calculate_performance_emoji(self, score: float) -> str:
        """Get performance emoji."""
        if score >= 0.85:
            return "🌟 Excellent"
        elif score >= 0.70:
            return "✓ Good"
        elif score >= 0.50:
            return "⚠️ Fair"
        else:
            return "❌ Poor"
    
    def _get_complexity_indicator(self, context_type: str) -> str:
        """Get complexity indicator for context type."""
        if context_type == 'single_page':
            return "⭐ Easy"
        elif context_type == 'multi_page':
            return "⭐⭐ Medium"
        elif context_type == 'cross_document':
            return "⭐⭐⭐ Hard"
        else:
            return "Unknown"


def main():
    """Main function to generate accuracy report."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Chatbot Accuracy Report")
    parser.add_argument("--qna-report", help="Path to QnA accuracy report JSON")
    parser.add_argument("--pdf-report", help="Path to PDF accuracy report JSON")
    parser.add_argument("--output", default="docs/CHATBOT_ACCURACY_REPORT.md",
                        help="Output markdown file path")
    
    args = parser.parse_args()
    
    if not args.qna_report and not args.pdf_report:
        print("ERROR: At least one report file (--qna-report or --pdf-report) must be provided")
        return
    
    generator = AccuracyReportGenerator()
    
    try:
        generator.generate_comprehensive_report(
            qna_report_file=args.qna_report,
            pdf_report_file=args.pdf_report,
            output_file=args.output
        )
        
        print("\n" + "="*80)
        print("REPORT GENERATION COMPLETED")
        print("="*80)
        print(f"\nReport saved to: {args.output}")
        print("\nYou can now review the comprehensive accuracy report.")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Error generating report: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
