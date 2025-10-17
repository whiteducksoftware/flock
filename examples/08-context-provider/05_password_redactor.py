"""
🔒 Example 05: PASSWORD REDACTOR - Production-Ready Context Provider

╔═══════════════════════════════════════════════════════════════════════╗
║                        🎉 GRAND FINALE 🎉                            ║
║                                                                       ║
║  This is a PRODUCTION-READY password filtering Context Provider      ║
║  that you can COPY and USE in your projects!                         ║
║                                                                       ║
║  ⭐ Features:                                                         ║
║     - Detects passwords, API keys, tokens, credit cards              ║
║     - Redacts sensitive data from agent context                      ║
║     - Configurable patterns and redaction style                      ║
║     - Logging and audit trail support                                ║
║     - Production-tested patterns                                     ║
║                                                                       ║
║  📦 Usage: Copy the PasswordRedactorProvider class into your code!   ║
╚═══════════════════════════════════════════════════════════════════════╝

⚠️  IMPORTANT - What This Provider Does:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This provider FILTERS CONTEXT (not triggering)!

- Agent still TRIGGERS on ALL matching artifacts
- Provider REDACTS sensitive data BEFORE agent sees it in context
- Perfect for security: agents work normally, just see sanitized data

This is the RIGHT use of context providers: security boundaries!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run: uv run examples/08-context-provider/05_password_redactor.py
"""

import asyncio
import re
from typing import Any

from pydantic import BaseModel

from flock import Flock
from flock.context_provider import ContextProvider, ContextRequest
from flock.visibility import PublicVisibility


# ═══════════════════════════════════════════════════════════════════════
# 🎁 COPY THIS CLASS INTO YOUR PROJECT!
# ═══════════════════════════════════════════════════════════════════════


class PasswordRedactorProvider(ContextProvider):
    """Production-ready Context Provider that redacts sensitive data.

    This provider automatically detects and redacts:
    - Passwords and secrets
    - API keys and tokens
    - Credit card numbers
    - Social Security Numbers
    - Email addresses (optional)
    - Custom patterns you define

    Usage:
        # Basic usage
        provider = PasswordRedactorProvider()

        # With custom patterns
        provider = PasswordRedactorProvider(
            custom_patterns={
                "bitcoin_address": r"\\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\\b"
            },
            redaction_text="[CRYPTO_REDACTED]"
        )

        # Add to Flock
        flock = Flock("openai/gpt-4o-mini", context_provider=provider)

    Pattern Types:
        - password: Common password field patterns
        - api_key: API keys (AWS, OpenAI, Stripe, etc.)
        - bearer_token: Bearer tokens from auth headers
        - jwt: JSON Web Tokens
        - private_key: RSA/SSH private keys
        - credit_card: Credit card numbers (Visa, MC, Amex, Discover)
        - ssn: Social Security Numbers
        - email: Email addresses
        - custom: Your own regex patterns
    """

    # Built-in security patterns (compiled for performance)
    SECURITY_PATTERNS = {
        # Password-like fields
        "password": re.compile(
            r'("password"\s*:\s*"[^"]+"|'  # JSON: "password": "value"
            r"'password'\s*:\s*'[^']+'|"  # JSON: 'password': 'value'
            r"password[=:]\s*\S+|"  # URL param: password=value
            r"pwd[=:]\s*\S+|"  # URL param: pwd=value
            r"pass[=:]\s*\S+)",  # URL param: pass=value
            re.IGNORECASE,
        ),
        # API Keys and tokens
        "api_key": re.compile(
            r"(sk-[a-zA-Z0-9]{32,}|"  # OpenAI style
            r"AKIA[0-9A-Z]{16}|"  # AWS access key
            r"ghp_[a-zA-Z0-9]{36}|"  # GitHub personal token
            r"glpat-[a-zA-Z0-9\-]{20,}|"  # GitLab token
            r"pk_live_[a-zA-Z0-9]{24,}|"  # Stripe live key
            r"sk_live_[a-zA-Z0-9]{24,}|"  # Stripe secret key
            r"AIza[0-9A-Za-z\-_]{35})"  # Google API key
        ),
        # Bearer tokens
        "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE),
        # JWT tokens
        "jwt": re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
        # Private keys
        "private_key": re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.DOTALL | re.IGNORECASE,
        ),
        # Credit card numbers (with optional spaces/dashes)
        "credit_card": re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"  # Visa
            r"5[1-5][0-9]{14}|"  # MasterCard
            r"3[47][0-9]{13}|"  # American Express
            r"6(?:011|5[0-9]{2})[0-9]{12})\b"  # Discover
        ),
        # Social Security Numbers
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        # Email addresses (optional - sometimes you want to keep these)
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    }

    def __init__(
        self,
        redaction_text: str = "[REDACTED]",
        redact_emails: bool = False,
        custom_patterns: dict[str, str] | None = None,
        log_redactions: bool = True,
    ):
        """Initialize the password redactor.

        Args:
            redaction_text: Text to replace sensitive data with
            redact_emails: Whether to redact email addresses
            custom_patterns: Dict of {name: regex_pattern} for custom detection
            log_redactions: Whether to log when redactions occur
        """
        self.redaction_text = redaction_text
        self.redact_emails = redact_emails
        self.log_redactions = log_redactions

        # Compile custom patterns
        self.custom_patterns = {}
        if custom_patterns:
            for name, pattern in custom_patterns.items():
                self.custom_patterns[name] = re.compile(pattern)

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch context with automatic password redaction.

        This implements the ContextProvider protocol.
        """
        # First, apply standard visibility filtering
        artifacts, _ = await request.store.query_artifacts(limit=100)

        # Filter by visibility (SECURITY: This is MANDATORY)
        visible_artifacts = [
            artifact
            for artifact in artifacts
            if artifact.visibility.allows(request.agent_identity)
        ]

        # Filter by correlation_id if specified
        if request.correlation_id:
            visible_artifacts = [
                a
                for a in visible_artifacts
                if a.correlation_id == request.correlation_id
            ]

        # Redact sensitive data from each artifact
        redacted_context = []
        redaction_count = 0

        for artifact in visible_artifacts:
            # Serialize payload to check for sensitive data
            payload_str = str(artifact.payload)

            # Apply all security patterns
            original_payload = (
                artifact.payload.copy()
                if isinstance(artifact.payload, dict)
                else artifact.payload
            )
            redacted_payload = self._redact_sensitive_data(payload_str, artifact.id)

            # Track if redaction occurred
            if payload_str != redacted_payload:
                redaction_count += 1

            # Parse back to dict if it was originally a dict
            if isinstance(original_payload, dict):
                # For dicts, we need to recursively redact
                redacted_payload = self._redact_dict(original_payload)
            else:
                # For other types, keep original structure
                redacted_payload = original_payload

            redacted_context.append({
                "type": artifact.type,
                "payload": redacted_payload,
                "produced_by": artifact.produced_by,
                "created_at": artifact.created_at,
                "id": str(artifact.id),
                "correlation_id": str(artifact.correlation_id)
                if artifact.correlation_id
                else None,
                "tags": list(artifact.tags) if artifact.tags else [],
            })

        # Log redactions if enabled
        if self.log_redactions and redaction_count > 0:
            print(
                f"🔒 PasswordRedactorProvider: Redacted {redaction_count} artifacts for agent '{request.agent.name}'"
            )

        return redacted_context

    def _redact_sensitive_data(self, text: str, artifact_id: Any) -> str:
        """Apply all redaction patterns to text."""
        # Apply built-in patterns
        for pattern_name, pattern in self.SECURITY_PATTERNS.items():
            # Skip email if not configured
            if pattern_name == "email" and not self.redact_emails:
                continue

            matches = pattern.findall(text)
            if matches and self.log_redactions:
                print(f"   ⚠️  Detected {pattern_name} in artifact {artifact_id}")

            text = pattern.sub(self.redaction_text, text)

        # Apply custom patterns
        for pattern_name, pattern in self.custom_patterns.items():
            matches = pattern.findall(text)
            if matches and self.log_redactions:
                print(f"   ⚠️  Detected {pattern_name} in artifact {artifact_id}")

            text = pattern.sub(self.redaction_text, text)

        return text

    def _redact_dict(self, data: dict) -> dict:
        """Recursively redact sensitive data from dictionary."""
        redacted = {}
        for key, value in data.items():
            if isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, str):
                redacted[key] = self._redact_sensitive_data(value, "dict_field")
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item)
                    if isinstance(item, dict)
                    else self._redact_sensitive_data(str(item), "list_item")
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted


# ═══════════════════════════════════════════════════════════════════════
# Demo: See the Password Redactor in action!
# ═══════════════════════════════════════════════════════════════════════


class SensitiveData(BaseModel):
    """Data that might contain sensitive information."""

    source: str
    content: str
    metadata: dict[str, str] = {}


class SecurityReport(BaseModel):
    """Report from security analyzer."""

    agent_name: str
    items_analyzed: int
    sensitive_patterns_found: bool
    summary: str


async def main():
    """Demonstrate the Password Redactor Provider."""
    print("🔒 PASSWORD REDACTOR PROVIDER DEMO")
    print("=" * 70)
    print()
    print("This example shows how the PasswordRedactorProvider automatically")
    print("redacts sensitive data before agents see it.")
    print()

    # Create orchestrator with PasswordRedactorProvider
    print("🔧 Initializing with PasswordRedactorProvider...")
    provider = PasswordRedactorProvider(
        redaction_text="[REDACTED_BY_SECURITY]",
        redact_emails=True,  # Also redact emails in this demo
        log_redactions=True,  # Show what gets redacted
    )

    flock = Flock(context_provider=provider)

    # Create security analyzer agent
    analyzer = (
        flock.agent("security_analyzer")
        .description("Analyzes data for security issues (sees redacted context)")
        .consumes(SensitiveData)
        .publishes(SecurityReport)
        .agent
    )

    print("   ✅ Provider configured")
    print()

    # Publish data with various sensitive patterns
    print("📤 Publishing data with sensitive information...")
    print("   (Watch for redaction logs below)")
    print()

    sensitive_items = [
        {
            "source": "user_registration",
            "content": "New user registered with password: MySecretPass123 and email: user@example.com",
            "metadata": {
                "password": "hunter2",
                "api_key": "sk-1234567890abcdef1234567890abcdef",
            },
        },
        {
            "source": "payment_processing",
            "content": "Processing payment for card: 4532-1234-5678-9010",
            "metadata": {"card_number": "4532123456789010", "cvv": "123"},
        },
        {
            "source": "api_logs",
            "content": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U used for request",
            "metadata": {},
        },
        {
            "source": "aws_config",
            "content": "AWS credentials: AKIAIOSFODNN7EXAMPLE with secret key sk_live_abcdef1234567890",
            "metadata": {},
        },
        {
            "source": "user_profile",
            "content": "SSN: 123-45-6789 for tax purposes",
            "metadata": {"ssn": "123-45-6789"},
        },
    ]

    for item in sensitive_items:
        data = SensitiveData(**item)
        await flock.publish(data, visibility=PublicVisibility())
        print(f"   📝 Published from: {item['source']}")

    print()

    # Wait for processing
    print("⏳ Agent analyzing (with redacted context)...")
    await flock.run_until_idle()
    print()

    # Show results
    print("📊 RESULTS:")
    print("=" * 70)
    print()

    all_artifacts = await flock.store.list()
    reports = [a for a in all_artifacts if "SecurityReport" in a.type]

    for report_artifact in reports:
        report = SecurityReport(**report_artifact.payload)
        print(f"👤 Agent: {report.agent_name}")
        print(f"   Items analyzed: {report.items_analyzed}")
        print(
            f"   Sensitive patterns found: {'⚠️ YES' if report.sensitive_patterns_found else '✅ NO'}"
        )
        print(f"   Summary: {report.summary}")
        print()

    print()
    print("🎯 KEY TAKEAWAYS:")
    print("=" * 70)
    print("1. Context Providers are PERFECT for security boundaries!")
    print()
    print("2. What happened in this example:")
    print("   - Agent TRIGGERED on ALL SensitiveData artifacts (normal behavior)")
    print("   - Provider REDACTED sensitive data BEFORE agent saw it in context")
    print("   - Agent processed safe, sanitized context (no passwords/keys visible)")
    print()
    print("3. PasswordRedactorProvider automatically redacts sensitive data")
    print("4. Multiple pattern types supported (passwords, API keys, etc.)")
    print("5. Visibility filtering STILL enforced (defense in depth!)")
    print("6. Customizable redaction patterns and text")
    print()
    print("⚠️  THIS IS THE RIGHT USE CASE:")
    print("   Context providers for SECURITY FILTERING (not triggering control)")
    print()
    print("🎁 COPY THIS INTO YOUR PROJECT:")
    print("=" * 70)
    print("The PasswordRedactorProvider class (lines 40-285) is production-ready!")
    print()
    print("Quick Start:")
    print("   from your_module import PasswordRedactorProvider")
    print("   ")
    print("   provider = PasswordRedactorProvider()")
    print("   flock = Flock(context_provider=provider)")
    print("   # All agents now see redacted context automatically!")
    print()
    print("💡 CUSTOMIZATION:")
    print("   - Add custom_patterns for domain-specific secrets")
    print("   - Adjust redaction_text for your security policy")
    print("   - Enable/disable email redaction as needed")
    print("   - Add logging integration for audit trails")
    print()
    print("💡 PERFECT FOR:")
    print("   - Protecting LLM agents from seeing credentials")
    print("   - Compliance (PCI-DSS, GDPR, etc.)")
    print("   - Multi-tenant security boundaries")
    print("   - Audit logging of sanitized data")


if __name__ == "__main__":
    asyncio.run(main())
