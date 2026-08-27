#!/usr/bin/env python3
"""
Chatbot Accuracy Testing - Master Workflow Script
Runs complete accuracy testing workflow from seeding to report generation
"""
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print styled header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_step(step_num, text):
    """Print step information."""
    print(f"{Colors.OKBLUE}{Colors.BOLD}[STEP {step_num}]{Colors.ENDC} {text}")


def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{Colors.OKCYAN}Running: {description}{Colors.ENDC}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print_success(f"{description} completed")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed")
        print(f"Error: {e.stderr}")
        return False, e.stderr


def check_prerequisites():
    """Check if all prerequisites are met."""
    print_step(0, "Checking Prerequisites")
    
    # Check environment variables
    required_env_vars = [
        'DATABASE_URL',
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_ENDPOINT'
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print_error(f"Missing environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the following environment variables:")
        for var in missing_vars:
            print(f"  export {var}='your-value'")
        return False
    
    print_success("All environment variables are set")
    return True


def seed_test_data(test_type):
    """Seed test data for QnA or PDF."""
    if test_type == "qna":
        print_step(1, "Seeding QnA Test Data")
        cmd = ["python", "tests/accuracy/seeders/qna_test_seeder.py"]
        config_file = "tests/accuracy/test_data/qna_test_config.json"
    else:
        print_step(1, "Seeding PDF Test Data")
        cmd = ["python", "tests/accuracy/seeders/pdf_test_seeder.py"]
        config_file = "tests/accuracy/test_data/pdf_test_config.json"
    
    success, output = run_command(cmd, f"{test_type.upper()} data seeding")
    
    if success and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        print_success(f"Configuration saved to: {config_file}")
        return config
    else:
        print_error(f"Failed to seed {test_type.upper()} test data")
        return None


def run_accuracy_test(test_type, config):
    """Run accuracy tests."""
    if test_type == "qna":
        print_step(2, "Running QnA Accuracy Tests")
        cmd = [
            "python", "tests/accuracy/test_qna_accuracy.py",
            "--persona-id", config['persona_id'],
            "--dataset-id", config['dataset_id'],
            "--test-file", config['test_cases_file'],
            "--output", "tests/accuracy/results/qna_accuracy_report.json"
        ]
    else:
        print_step(2, "Running PDF Accuracy Tests")
        cmd = [
            "python", "tests/accuracy/test_pdf_accuracy.py",
            "--persona-id", config['persona_id'],
            "--dataset-id", config['dataset_id'],
            "--test-file", config['test_cases_file'],
            "--output", "tests/accuracy/results/pdf_accuracy_report.json"
        ]
    
    success, output = run_command(cmd, f"{test_type.upper()} accuracy testing")
    
    if success:
        print_success(f"{test_type.upper()} accuracy test completed")
        return True
    else:
        print_error(f"{test_type.upper()} accuracy test failed")
        return False


def generate_report(qna_report=None, pdf_report=None):
    """Generate comprehensive accuracy report."""
    print_step(3, "Generating Comprehensive Report")
    
    cmd = ["python", "tests/accuracy/generate_report.py"]
    
    if qna_report and os.path.exists(qna_report):
        cmd.extend(["--qna-report", qna_report])
    
    if pdf_report and os.path.exists(pdf_report):
        cmd.extend(["--pdf-report", pdf_report])
    
    cmd.extend(["--output", "docs/CHATBOT_ACCURACY_REPORT.md"])
    
    success, output = run_command(cmd, "Report generation")
    
    if success:
        print_success("Report generated: docs/CHATBOT_ACCURACY_REPORT.md")
        return True
    else:
        print_error("Report generation failed")
        return False


def main():
    """Main workflow execution."""
    parser = argparse.ArgumentParser(
        description="Chatbot Accuracy Testing - Master Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete workflow (both QnA and PDF)
  python tests/accuracy/run_complete_test.py --all

  # Run only QnA tests
  python tests/accuracy/run_complete_test.py --qna

  # Run only PDF tests
  python tests/accuracy/run_complete_test.py --pdf

  # Skip seeding if data already exists
  python tests/accuracy/run_complete_test.py --all --skip-seeding
        """
    )
    
    parser.add_argument("--all", action="store_true", help="Run both QnA and PDF tests")
    parser.add_argument("--qna", action="store_true", help="Run QnA tests only")
    parser.add_argument("--pdf", action="store_true", help="Run PDF tests only")
    parser.add_argument("--skip-seeding", action="store_true", help="Skip data seeding step")
    parser.add_argument("--skip-report", action="store_true", help="Skip report generation")
    
    args = parser.parse_args()
    
    # Determine what to run
    if not (args.all or args.qna or args.pdf):
        print_error("Please specify what to run: --all, --qna, or --pdf")
        parser.print_help()
        sys.exit(1)
    
    run_qna = args.all or args.qna
    run_pdf = args.all or args.pdf
    
    # Start workflow
    print_header("CHATBOT ACCURACY TESTING - COMPLETE WORKFLOW")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Running: {'QnA and PDF' if args.all else 'QnA' if args.qna else 'PDF'} tests")
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    qna_config = None
    pdf_config = None
    
    # Seeding phase
    if not args.skip_seeding:
        if run_qna:
            qna_config = seed_test_data("qna")
            if not qna_config:
                print_error("QnA seeding failed, aborting")
                sys.exit(1)
        
        if run_pdf:
            pdf_config = seed_test_data("pdf")
            if not pdf_config:
                print_error("PDF seeding failed, aborting")
                sys.exit(1)
    else:
        print_warning("Skipping seeding - loading existing configurations")
        
        if run_qna:
            config_file = "tests/accuracy/test_data/qna_test_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    qna_config = json.load(f)
                print_success(f"Loaded QnA config from {config_file}")
            else:
                print_error(f"QnA config not found: {config_file}")
                sys.exit(1)
        
        if run_pdf:
            config_file = "tests/accuracy/test_data/pdf_test_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    pdf_config = json.load(f)
                print_success(f"Loaded PDF config from {config_file}")
            else:
                print_error(f"PDF config not found: {config_file}")
                sys.exit(1)
    
    # Testing phase
    qna_success = False
    pdf_success = False
    
    if run_qna and qna_config:
        qna_success = run_accuracy_test("qna", qna_config)
    
    if run_pdf and pdf_config:
        pdf_success = run_accuracy_test("pdf", pdf_config)
    
    # Report generation
    if not args.skip_report:
        qna_report = "tests/accuracy/results/qna_accuracy_report.json" if qna_success else None
        pdf_report = "tests/accuracy/results/pdf_accuracy_report.json" if pdf_success else None
        
        if qna_report or pdf_report:
            generate_report(qna_report, pdf_report)
            
            # Export to Excel
            print_header("EXPORTING TO EXCEL")
            export_cmd = ["python", "tests/accuracy/export_to_excel.py"]
            
            if qna_report and pdf_report:
                export_cmd.append("--type=both")
            elif qna_report:
                export_cmd.append("--type=qna")
            elif pdf_report:
                export_cmd.append("--type=pdf")
            
            result = subprocess.run(export_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print_success("Excel reports generated successfully")
                print(result.stdout)
            else:
                print_warning("Excel export failed (optional step)")
                if result.stderr:
                    print(f"  Error: {result.stderr}")
        else:
            print_warning("No test results to generate report")
    
    # Summary
    print_header("WORKFLOW COMPLETED")
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("Results:")
    if run_qna:
        status = "✓ SUCCESS" if qna_success else "✗ FAILED"
        print(f"  QnA Tests: {Colors.OKGREEN if qna_success else Colors.FAIL}{status}{Colors.ENDC}")
    
    if run_pdf:
        status = "✓ SUCCESS" if pdf_success else "✗ FAILED"
        print(f"  PDF Tests: {Colors.OKGREEN if pdf_success else Colors.FAIL}{status}{Colors.ENDC}")
    
    if not args.skip_report and (qna_success or pdf_success):
        print(f"\n  Report: {Colors.OKGREEN}docs/CHATBOT_ACCURACY_REPORT.md{Colors.ENDC}")
    
    print("\n" + "="*80)
    
    # Exit code
    if (run_qna and not qna_success) or (run_pdf and not pdf_success):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
