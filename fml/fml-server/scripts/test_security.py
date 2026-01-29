#!/usr/bin/env python3
"""Test script for security validation module."""

import sys
sys.path.insert(0, "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server")

from src.security import (
    validate_content_for_storage,
    detect_sensitive_content,
    redact_sensitive_content,
    looks_like_api_key
)


def test_api_key_detection():
    """Test detection of various API key formats."""
    print("\n=== Testing API Key Detection ===\n")
    
    test_cases = [
        # (content, should_block, description)
        # NOTE: These are FAKE test patterns using XXXX placeholders - NOT real keys
        ("sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXX", True, "OpenAI API key"),
        ("sk-proj-XXXXXXXXXXXXXXXXXXXXXXXX", True, "OpenAI project key"),
        ("ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", True, "GitHub PAT"),
        ("AKIAXXXXXXXXXXXX0000", True, "AWS Access Key"),
        ("AIzaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", True, "Google API Key"),
        ("sk-ant-XXXXXXXXXXXXXXXXXXXX", True, "Anthropic API Key"),
        ("The API key format is sk-xxxx", False, "Mention of format (no actual key)"),
        ("Use your OpenAI key from the dashboard", False, "Safe reference"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Content: {content[:50]}...")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_password_detection():
    """Test detection of password patterns."""
    print("\n=== Testing Password Detection ===\n")
    
    test_cases = [
        ('password = "mysecretpassword123"', True, "Password assignment"),
        ('PASSWORD: SuperSecret!@#', True, "Password with colon"),
        ("mysql://user:secretpass123@localhost:3306/db", True, "DB connection string"),
        ("The password field should be encrypted", False, "Safe discussion"),
        ("Reset your password via email", False, "Safe instruction"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Content: {content[:60]}...")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_token_detection():
    """Test detection of various token formats."""
    print("\n=== Testing Token Detection ===\n")
    
    test_cases = [
        # NOTE: These are FAKE test patterns using XXXX placeholders - NOT real tokens
        ("Bearer eyXXXXXXXXXXXXXXXXXXXXXXXX.XXXXXXXXXXXXXXXXXXXXXXXX.XXXXXXXXXXXXXXXXXXXXXXXX", 
         True, "Bearer token with JWT"),
        ("Authorization: Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", True, "Auth header"),
        ("xoxb-XXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXX", True, "Slack token"),
        ("Use bearer token authentication", False, "Safe discussion"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Content: {content[:60]}...")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_private_key_detection():
    """Test detection of private keys."""
    print("\n=== Testing Private Key Detection ===\n")
    
    test_cases = [
        ("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...", True, "Private key"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow...", True, "RSA private key"),
        ("Generate a private key using openssl", False, "Safe instruction"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_safe_content():
    """Test that safe content is allowed."""
    print("\n=== Testing Safe Content (should NOT block) ===\n")
    
    test_cases = [
        "The user prefers dark mode for their IDE",
        "Remember to use semantic versioning for releases",
        "The database schema has a users table with id, email, created_at columns",
        "Firebolt Core runs on port 3473",
        "Use environment variables for configuration",
        "The API endpoint is /api/v1/memories",
        "Python 3.14 is recommended for this project",
    ]
    
    passed = 0
    failed = 0
    
    for content in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        
        if is_safe:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL (false positive)"
            failed += 1
        
        print(f"{status}: {content[:60]}...")
        if not is_safe:
            print(f"   Error: {error_msg}")
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_redaction():
    """Test content redaction functionality."""
    print("\n=== Testing Content Redaction ===\n")
    
    # NOTE: These are FAKE test patterns using XXXX placeholders - NOT real keys
    content = "Use API key sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXX and token ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    redacted = redact_sensitive_content(content)
    
    print(f"Original: {content}")
    print(f"Redacted: {redacted}")
    
    # Check that sensitive patterns are removed
    if "sk-XXXX" not in redacted and "ghp_" not in redacted:
        print("✅ PASS: Sensitive content was redacted")
        return 1, 0
    else:
        print("❌ FAIL: Sensitive content was not fully redacted")
        return 0, 1


def main():
    """Run all security tests."""
    print("=" * 60)
    print("FML Security Validation Tests")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    results = [
        test_api_key_detection(),
        test_password_detection(),
        test_token_detection(),
        test_private_key_detection(),
        test_safe_content(),
        test_redaction(),
    ]
    
    for passed, failed in results:
        total_passed += passed
        total_failed += failed
    
    print("=" * 60)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    
    if total_failed > 0:
        print("\n⚠️  Some tests failed - review the security patterns")
        return 1
    else:
        print("\n✅ All security tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
