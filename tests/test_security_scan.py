"""
Security scan for MYRAA.

This script scans the MYRAA codebase for common security vulnerabilities
including:
- Hardcoded secrets (API keys, passwords, tokens)
- Unsafe shell execution
- Debug artifacts
- Sensitive logs
- File permissions issues
"""

import os
import re
import sys
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Severity levels for security findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityFinding:
    """Represents a security finding."""
    file_path: str
    line_number: int
    severity: Severity
    category: str
    description: str
    line_content: str


class MYRAASecurityScanner:
    """Security scanner for MYRAA codebase."""

    def __init__(self):
        self.findings: List[SecurityFinding] = []
        self._setup_logger()
        self._define_patterns()

    def _setup_logger(self):
        """Setup logging for security scanner."""
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def _define_patterns(self):
        """Define patterns to scan for."""
        self.patterns = [
            # Hardcoded secrets
            {
                'name': 'Potential API Key',
                'pattern': r'["\']?(?:api[_-]?key|apikey|gemin[yi]?[_-]?key|tavily[_-]?key)["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{10,}["\']',
                'severity': Severity.HIGH,
                'category': 'Hardcoded Secrets',
                'description': 'Potential hardcoded API key found'
            },
            {
                'name': 'Potential Password',
                'pattern': r'["\']?(?:password|passwd|pwd|secret)["\']?\s*[:=]\s*["\'][^"\']{6,}["\']',
                'severity': Severity.HIGH,
                'category': 'Hardcoded Secrets',
                'description': 'Potential hardcoded password found'
            },
            {
                'name': 'Potential Token',
                'pattern': r'["\']?(?:token|auth[_-]?token|bearer)["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{10,}["\']',
                'severity': Severity.HIGH,
                'category': 'Hardcoded Secrets',
                'description': 'Potential hardcoded authentication token found'
            },
            {
                'name': 'Potential Private Key',
                'pattern': r'-----BEGIN\s+(?:RSA\s)?PRIVATE\s+KEY-----',
                'severity': Severity.CRITICAL,
                'category': 'Hardcoded Secrets',
                'description': 'Potential private key found in source code'
            },
            # Unsafe shell execution
            {
                'name': 'Potential Unsafe Shell Execution',
                'pattern': r'(?:os\.system|subprocess\.call|subprocess\.Popen|subprocess\.run)\s*\([^)]*shell\s*=\s*True\)',
                'severity': Severity.HIGH,
                'category': 'Unsafe Shell Execution',
                'description': 'Potential unsafe shell execution with shell=True'
            },
            {
                'name': 'Potential Command Injection',
                'pattern': r'(?:os\.system|subprocess\.call|subprocess\.Popen|subprocess\.run)\s*\([^)]*\+\s*[^)]*\)',
                'severity': Severity.HIGH,
                'category': 'Unsafe Shell Execution',
                'description': 'Potential command injection via string concatenation'
            },
            # Debug artifacts
            {
                'name': 'Debug Print Statement',
                'pattern': r'^\s*(?:print|console\.log|debug)\s*\(',
                'severity': Severity.LOW,
                'category': 'Debug Artifacts',
                'description': 'Debug print statement found in source code'
            },
            {
                'name': 'TODO/FIXME with Security Implications',
                'pattern': r'#\s*(?:TODO|FIXME|XXX).*?(?:security|auth|password|key|token)',
                'severity': Severity.MEDIUM,
                'category': 'Debug Artifacts',
                'description': 'TODO/FIXME comment with security implications'
            },
            # Sensitive logs
            {
                'name': 'Potential Sensitive Data Logging',
                'pattern': r'(?:logger\.|log\.|print).*?(?:password|passwd|pwd|secret|token|key|auth)',
                'severity': Severity.MEDIUM,
                'category': 'Sensitive Logs',
                'description': 'Potential logging of sensitive data'
            },
            # File operations
            {
                'name': 'Potential Unsafe File Permission',
                'pattern': r'(?:open|file).*?mode\s*=\s*["\']?[^"\']*[rw][^"\']*w',
                'severity': Severity.LOW,
                'category': 'File Operations',
                'description': 'File opened with write permissions - check if appropriate'
            },
            # SQL injection patterns (if any SQL usage)
            {
                'name': 'Potential SQL Injection',
                'pattern': r'(?:execute|query)\s*\([^)]*\+\s*[^)]*\)',
                'severity': Severity.HIGH,
                'category': 'Injection',
                'description': 'Potential SQL injection via string concatenation'
            },
            # Path traversal
            {
                'name': 'Potential Path Traversal',
                'pattern': r'\.\.\/|\.\.\\',
                'severity': Severity.MEDIUM,
                'category': 'Path Traversal',
                'description': 'Potential path traversal sequence found'
            }
        ]

        # Compile regex patterns
        for pattern_info in self.patterns:
            pattern_info['compiled'] = re.compile(pattern_info['pattern'], re.IGNORECASE | re.MULTILINE)

    def scan_file(self, file_path: str) -> List[SecurityFinding]:
        """
        Scan a single file for security issues.

        Args:
            file_path: Path to the file to scan

        Returns:
            List of security findings in the file
        """
        findings = []

        try:
            # Skip binary files and certain extensions
            if self._should_skip_file(file_path):
                return findings

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                line_findings = self._scan_line(line, line_num, file_path)
                findings.extend(line_findings)

        except Exception as e:
            logger.warning(f"Could not scan file {file_path}: {e}")

        return findings

    def _should_skip_file(self, file_path: str) -> bool:
        """Determine if a file should be skipped during scanning."""
        skip_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico',  # Images
            '.exe', '.dll', '.so', '.bin',  # Binaries
            '.pdf', '.zip', '.tar', '.gz',  # Archives
            '.pyc', '.pyo', '.pyd',  # Python compiled
            '.min.js', '.min.css',  # Minified files
            '.lock',  # Lock files
        }

        skip_directories = {
            '__pycache__',
            '.git',
            '.pytest_cache',
            'node_modules',
            'dist',
            'build',
            '.vscode',
            '.idea',
        }

        # Check extension
        _, ext = os.path.splitext(file_path.lower())
        if ext in skip_extensions:
            return True

        # Check if in skip directory
        path_parts = file_path.split(os.sep)
        if any(part in skip_directories for part in path_parts):
            return True

        # Skip very large files (>1MB)
        try:
            if os.path.getsize(file_path) > 1024 * 1024:
                return True
        except OSError:
            return True

        return False

    def _scan_line(self, line: str, line_num: int, file_path: str) -> List[SecurityFinding]:
        """Scan a single line for security issues."""
        findings = []

        for pattern_info in self.patterns:
            matches = pattern_info['compiled'].finditer(line)
            for match in matches:
                finding = SecurityFinding(
                    file_path=file_path,
                    line_number=line_num,
                    severity=pattern_info['severity'],
                    category=pattern_info['category'],
                    description=pattern_info['description'],
                    line_content=line.strip()
                )
                findings.append(finding)

        return findings

    def scan_directory(self, directory: str, file_extensions: List[str] = None) -> List[SecurityFinding]:
        """
        Scan a directory recursively for security issues.

        Args:
            directory: Directory to scan
            file_extensions: List of file extensions to scan (None for all)

        Returns:
            List of all security findings
        """
        if file_extensions is None:
            file_extensions = ['.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yaml', '.yml', '.txt', '.md', '.ini', '.cfg', '.conf']

        all_findings = []

        for root, dirs, files in os.walk(directory):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in {
                '__pycache__', '.git', '.pytest_cache', 'node_modules',
                'dist', 'build', '.vscode', '.idea'
            }]

            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file_path.lower())

                if ext in file_extensions:
                    findings = self.scan_file(file_path)
                    all_findings.extend(findings)

        self.findings.extend(all_findings)
        return all_findings

    def generate_report(self) -> str:
        """Generate a security scan report."""
        if not self.findings:
            return "No security findings detected."

        # Group findings by severity
        findings_by_severity = {}
        for finding in self.findings:
            severity = finding.severity.value
            if severity not in findings_by_severity:
                findings_by_severity[severity] = []
            findings_by_severity[severity].append(finding)

        # Generate report
        report_lines = [
            "MYRAA Security Scan Report",
            "=" * 50,
            f"Total files scanned: {len(set(f.file_path for f in self.findings))}",
            f"Total findings: {len(self.findings)}",
            ""
        ]

        # Add summary by severity
        severity_order = ['critical', 'high', 'medium', 'low']
        for severity in severity_order:
            if severity in findings_by_severity:
                count = len(findings_by_severity[severity])
                report_lines.append(f"{severity.upper()}: {count} findings")

        report_lines.extend([
            "",
            "Detailed Findings:",
            "-" * 30
        ])

        # Add detailed findings
        for severity in severity_order:
            if severity not in findings_by_severity:
                continue

            report_lines.append(f"\n{severity.upper()} SEVERITY:")
            report_lines.append("")

            for finding in findings_by_severity[severity]:
                report_lines.append(f"File: {finding.file_path}")
                report_lines.append(f"Line: {finding.line_number}")
                report_lines.append(f"Category: {finding.category}")
                report_lines.append(f"Description: {finding.description}")
                report_lines.append(f"Content: {finding.line_content}")
                report_lines.append("")

        return "\n".join(report_lines)

    def print_summary(self):
        """Print a summary of the security scan."""
        if not self.findings:
            print("[PASS] No security findings detected.")
            return

        print("MYRAA Security Scan Results")
        print("=" * 40)

        # Count by severity
        severity_counts = {}
        for finding in self.findings:
            severity = finding.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Print counts
        for severity in ['critical', 'high', 'medium', 'low']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                print(f"[{severity.upper()}] {count}")

        print(f"\nTotal: {len(self.findings)} findings in {len(set(f.file_path for f in self.findings))} files")

        # Show top findings if there are many
        if len(self.findings) > 10:
            print(f"\nShowing first 10 of {len(self.findings)} findings:")
            for i, finding in enumerate(self.findings[:10]):
                print(f"{i+1}. [{finding.severity.value.upper()}] {finding.file_path}:{finding.line_number} - {finding.description}")
        else:
            print("\nAll findings:")
            for i, finding in enumerate(self.findings):
                print(f"{i+1}. [{finding.severity.value.upper()}] {finding.file_path}:{finding.line_number} - {finding.description}")


def run_security_scan(directories: List[str] = None) -> MYRAASecurityScanner:
    """
    Run security scan on MYRAA codebase.

    Args:
        directories: List of directories to scan (None for default directories)

    Returns:
        MYRAASecurityScanner instance with results
    """
    if directories is None:
        directories = [
            'desktop_agent',
            'src',
            'services',
            'backend',
            'tests',
            'electron'
        ]

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("[SECURITY] Starting MYRAA Security Scan...")
    print("-" * 50)

    scanner = MYRAASecurityScanner()
    total_findings = 0

    for directory in directories:
        if os.path.exists(directory):
            print(f"Scanning {directory}...")
            findings = scanner.scan_directory(directory)
            total_findings += len(findings)
            print(f"  Found {len(findings)} potential issues")
        else:
            print(f"Directory {directory} does not exist, skipping")

    print("=" * 50)
    print(f"Security scan complete. Found {total_findings} potential issues.")
    print()

    scanner.print_summary()

    return scanner


if __name__ == "__main__":
    scanner = run_security_scan()

    # Save detailed report automatically in non-interactive environment
    try:
        # Try to save report - if we're in an interactive environment, we could ask
        with open('security_report.txt', 'w') as f:
            f.write(scanner.generate_report())
        print("Detailed report saved to security_report.txt")
    except:
        pass  # If we can't save, just continue

    # Exit with appropriate code
    critical_count = sum(1 for f in scanner.findings if f.severity == Severity.CRITICAL)
    high_count = sum(1 for f in scanner.findings if f.severity == Severity.HIGH)

    if critical_count > 0 or high_count > 0:
        print(f"\n[FAIL] Security scan found {critical_count} critical and {high_count} high severity issues!")
        sys.exit(1)
    else:
        print(f"\n[PASS] Security scan passed - no critical or high severity issues found.")
        sys.exit(0)