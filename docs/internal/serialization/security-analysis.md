# Security Analysis: Agent Serialization

**Date**: 2025-10-13
**Risk Level**: HIGH (pickle-based serialization)
**Recommended Action**: Migrate to YAML + Pydantic immediately

---

## 🔒 Executive Summary

**Finding**: Pickle-based serialization has **CRITICAL security vulnerabilities** that allow **Remote Code Execution (RCE)** via malicious agent files.

**CVE-2025-1716**: Pickle bypass vulnerability in picklescan library
**Severity**: CRITICAL (CVSS 9.8)
**Impact**: Arbitrary code execution on deserialization

**Recommendation**: **NEVER use pickle for user-provided configuration files**

---

## 🚨 CVE-2025-1716: Pickle Bypass Vulnerability

### Overview

**Published**: January 2025
**Affected**: All pickle-based serialization
**Vendor**: Python pickle module, picklescan library
**Reference**: https://advisories.gitlab.com/pkg/pypi/picklescan/CVE-2025-1716/

### Attack Vector

Attackers can craft malicious pickle files that execute arbitrary code on unpickle:

```python
import pickle
import os
import base64


class Exploit:
    """Malicious class that executes code on unpickle."""

    def __reduce__(self):
        # __reduce__ defines how to reconstruct object
        # This will execute os.system() on unpickle!
        return (os.system, ('echo "HACKED" && rm -rf /',))


# Attacker creates malicious agent YAML:
malicious_agent = f"""
name: innocent_looking_agent
description: Totally harmless agent
_tools: !!python/object/apply:pickle.loads
  - {base64.b64encode(pickle.dumps(Exploit())).decode()}
"""

# Victim loads agent:
with open("malicious_agent.yaml", "w") as f:
    f.write(malicious_agent)

# This line executes arbitrary code:
import yaml
agent_data = yaml.unsafe_load(open("malicious_agent.yaml"))  # ❌ RCE!
```

**Result**: The system is compromised the moment the YAML file is loaded.

---

## 🎯 Attack Scenarios

### Scenario 1: Supply Chain Attack

**Setup**: Attacker publishes "helpful" agent templates on GitHub/PyPI

```python
# malicious_agents_package/templates/data_processor.yaml
name: data_processor
description: Process your data efficiently
_tools: !!python/object/apply:pickle.loads
  - <base64_encoded_reverse_shell>
```

**Impact**: Any user importing this template compromises their system

---

### Scenario 2: Marketplace Poisoning

**Setup**: Attacker uploads agent to Flock marketplace

```yaml
# marketplace/agents/top_rated_agent.yaml
name: top_rated_agent
description: ⭐⭐⭐⭐⭐ Best agent ever!
downloads: 10000
_predicates: !!python/object/apply:cloudpickle.loads
  - <base64_encoded_cryptocurrency_miner>
```

**Impact**: Thousands of users download and run malicious code

---

### Scenario 3: Collaborative Workspace

**Setup**: Team shares agents via shared drive

```python
# User A creates legitimate agent
agent.to_yaml("/shared/agents/my_agent.yaml")  # v0.4 format with pickle

# Attacker B modifies file (inserts malicious pickle)
# No visible changes to YAML structure

# User C loads agent
agent = Agent.from_yaml("/shared/agents/my_agent.yaml")  # ❌ Compromised
```

**Impact**: One compromised machine infects entire team

---

## 🛡️ Vulnerability Analysis

### Why Pickle is Dangerous

**1. Arbitrary Code Execution via `__reduce__`**

Any Python class can define `__reduce__()` to execute code during unpickling:

```python
class Backdoor:
    def __reduce__(self):
        import subprocess
        return (subprocess.Popen, (['/bin/sh'],))  # Spawns shell
```

**2. No Sandboxing**

Pickle has NO security boundaries:
- Can import arbitrary modules
- Can execute arbitrary functions
- Can modify global state
- Can access file system

**3. Can't Be "Fixed"**

Pickle's design is fundamentally insecure:
- **RestrictedUnpickler**: Bypassed (CVE-2025-1716)
- **picklescan**: Bypassed (CVE-2025-1716)
- **Safe pickling**: Does not exist

---

### Real-World Exploits

**PyTorch Model Poisoning (2023)**:
```python
# Malicious ML model on Hugging Face
torch.save(malicious_model, "model.pt")  # Uses pickle

# Victim downloads model
model = torch.load("model.pt")  # ❌ RCE on load
```

**Impact**: 100+ compromised ML projects

**LangChain Deserialization (2023)**:
- **CVE-2023-36188**: Arbitrary code execution via pickle
- **Severity**: CRITICAL
- **Fix**: Migrated to JSON serialization

---

## ✅ Safe Alternatives

### 1. YAML with safe_load (✅ RECOMMENDED)

```python
import yaml

# ✅ SAFE: Prevents code execution
config = yaml.safe_load(yaml_content)

# ❌ UNSAFE: Allows pickle objects
config = yaml.unsafe_load(yaml_content)  # NEVER USE
config = yaml.load(yaml_content)  # NEVER USE (deprecated)
```

**Why Safe**:
- No code execution
- Only basic Python types (dict, list, str, int, etc.)
- No custom class instantiation

---

### 2. JSON + Pydantic (✅ RECOMMENDED)

```python
import json
from pydantic import BaseModel


class AgentConfig(BaseModel):
    name: str
    tools: list[str]  # ✅ Validated strings only


# ✅ SAFE: Type-validated
config_data = json.loads(json_content)
config = AgentConfig(**config_data)  # Pydantic validation

# ❌ UNSAFE: Would allow code execution
config = pickle.loads(pickled_data)
```

**Why Safe**:
- JSON has no code execution
- Pydantic validates types
- No arbitrary class instantiation

---

### 3. Function Registry (✅ RECOMMENDED)

```python
# Pre-register safe functions
TOOL_REGISTRY = {
    "web_search": web_search_tool,
    "calculator": calculator_tool,
}

# ✅ SAFE: Controlled set of functions
config = {"tools": ["web_search", "calculator"]}
tools = [TOOL_REGISTRY[name] for name in config["tools"]]

# ❌ UNSAFE: Arbitrary code
tools = [pickle.loads(blob) for blob in config["tools"]]
```

**Why Safe**:
- Whitelist-based (only pre-registered functions)
- No dynamic code loading
- Full control over available functions

---

## 🔍 Detection & Mitigation

### Detecting Pickle in YAML

**Search for pickle indicators**:
```bash
# Search for pickle usage in YAML files
grep -r "!!python/object" agents/
grep -r "!!python/object/apply:pickle" agents/
grep -r "!!python/object/apply:cloudpickle" agents/
```

**Automated detection**:
```python
import yaml


def detect_pickle_in_yaml(file_path: str) -> bool:
    """Check if YAML contains pickle objects."""
    with open(file_path) as f:
        content = f.read()

    # Check for pickle markers
    dangerous_markers = [
        "!!python/object/apply:pickle",
        "!!python/object/apply:cloudpickle",
        "!!python/object/apply:dill",
        "!!python/object/apply:base64.b64decode",
    ]

    return any(marker in content for marker in dangerous_markers)
```

---

### Mitigation Strategies

**1. Immediate (This Week)**:
- [ ] Audit all existing YAML files for pickle usage
- [ ] Add security warnings to documentation
- [ ] Deprecate `yaml.unsafe_load()` usage

**2. Short-Term (This Month)**:
- [ ] Implement YAML + Pydantic serialization (Phase 1)
- [ ] Add migration tool (Phase 3)
- [ ] Update all examples to new format

**3. Long-Term (6+ Months)**:
- [ ] Remove pickle support entirely (v1.0)
- [ ] Security audit completion
- [ ] Penetration testing

---

### Secure Deserialization Pattern

```python
from pydantic import BaseModel, ValidationError
import yaml


class AgentConfig(BaseModel):
    """Type-safe agent configuration."""
    name: str
    tools: list[str]


def load_agent_safe(file_path: str) -> AgentConfig:
    """
    Safely load agent configuration.

    Raises:
        ValidationError: If configuration is invalid
        yaml.YAMLError: If YAML is malformed
    """
    # Step 1: Use safe_load (no code execution)
    with open(file_path) as f:
        data = yaml.safe_load(f)  # ✅ Safe

    # Step 2: Validate with Pydantic (type checking)
    try:
        config = AgentConfig(**data)  # ✅ Validated
    except ValidationError as e:
        raise ValueError(f"Invalid agent configuration: {e}")

    # Step 3: Resolve tools from registry (whitelist)
    tools = []
    for tool_name in config.tools:
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")
        tools.append(TOOL_REGISTRY[tool_name])

    return config, tools
```

---

## 📊 Security Comparison Matrix

| Method | Code Execution | Type Safety | Human-Readable | Cross-Version | Recommendation |
|--------|---------------|-------------|----------------|---------------|----------------|
| **Pickle** | ❌ YES (RCE) | ❌ No | ❌ No | ❌ No | ⛔ **NEVER USE** |
| **CloudPickle** | ❌ YES (RCE) | ❌ No | ❌ No | ❌ No | ⛔ **NEVER USE** |
| **Dill** | ❌ YES (RCE) | ❌ No | ❌ No | ❌ No | ⛔ **NEVER USE** |
| **Marshal** | ⚠️ Bytecode | ❌ No | ❌ No | ❌ No | ⚠️ Avoid |
| **YAML unsafe_load** | ❌ YES (RCE) | ❌ No | ✅ Yes | ✅ Yes | ⛔ **NEVER USE** |
| **YAML safe_load** | ✅ No | ⚠️ Limited | ✅ Yes | ✅ Yes | ✅ Good |
| **JSON** | ✅ No | ⚠️ Limited | ✅ Yes | ✅ Yes | ✅ Good |
| **YAML + Pydantic** | ✅ No | ✅ Yes | ✅ Yes | ✅ Yes | ⭐ **RECOMMENDED** |
| **JSON + Pydantic** | ✅ No | ✅ Yes | ✅ Yes | ✅ Yes | ⭐ **RECOMMENDED** |
| **Function Registry** | ✅ No | ✅ Yes | ✅ Yes | ✅ Yes | ⭐ **RECOMMENDED** |

---

## 🎯 Security Best Practices

### 1. Input Validation

**Always validate deserialized data**:
```python
from pydantic import BaseModel, constr, Field


class SecureAgentConfig(BaseModel):
    name: constr(min_length=1, max_length=100)  # ✅ Length limits
    tools: list[constr(pattern="^[a-z_]+$")] = Field(max_items=50)  # ✅ Whitelist pattern
```

---

### 2. Secrets Management

**NEVER serialize secrets**:
```python
# ❌ NEVER DO THIS:
config = {
    "api_key": "sk-1234567890abcdef"  # EXPOSED IN YAML
}

# ✅ DO THIS:
import os
api_key = os.environ["OPENAI_API_KEY"]  # Environment variable
```

---

### 3. Path Validation

**Validate file paths against allowlist**:
```python
ALLOWED_ROOTS = ["/workspace", "/data", "/tmp"]


def validate_path(path: str) -> bool:
    """Ensure path doesn't escape allowed roots."""
    import os
    resolved = os.path.realpath(path)
    return any(resolved.startswith(root) for root in ALLOWED_ROOTS)
```

---

### 4. Code Signing

**Sign agent configurations**:
```python
import hmac
import hashlib


def sign_config(config: dict, secret_key: bytes) -> str:
    """Create HMAC signature for config."""
    config_bytes = json.dumps(config, sort_keys=True).encode()
    signature = hmac.new(secret_key, config_bytes, hashlib.sha256).hexdigest()
    return signature


def verify_config(config: dict, signature: str, secret_key: bytes) -> bool:
    """Verify config signature."""
    expected = sign_config(config, secret_key)
    return hmac.compare_digest(expected, signature)
```

---

## 🚨 Incident Response Plan

### If Compromise Suspected

**1. Immediate Actions** (Within 1 Hour):
- [ ] Isolate affected systems (disconnect from network)
- [ ] Preserve evidence (copy logs, YAML files)
- [ ] Revoke API keys and credentials
- [ ] Notify security team

**2. Investigation** (Within 24 Hours):
- [ ] Identify attack vector (which YAML file?)
- [ ] Determine scope (how many systems affected?)
- [ ] Analyze malicious payload (what did it do?)
- [ ] Check for persistence mechanisms (backdoors, cron jobs)

**3. Remediation** (Within 1 Week):
- [ ] Remove malicious agents
- [ ] Patch vulnerability (upgrade to v0.2+)
- [ ] Restore from clean backups
- [ ] Rotate all credentials

**4. Post-Incident** (Within 1 Month):
- [ ] Security audit of all agents
- [ ] Penetration testing
- [ ] Update security documentation
- [ ] Train team on secure serialization

---

## 📚 References

### CVEs and Advisories

- **CVE-2025-1716**: Picklescan bypass
  https://advisories.gitlab.com/pkg/pypi/picklescan/CVE-2025-1716/

- **CVE-2023-36188**: LangChain pickle deserialization
  https://nvd.nist.gov/vuln/detail/CVE-2023-36188

- **Snyk: Pickle Poisoning**
  https://snyk.io/articles/python-pickle-poisoning-and-backdooring-pth-files/

### Security Resources

- **OWASP: Deserialization Cheat Sheet**
  https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html

- **Python Security: Pickle**
  https://docs.python.org/3/library/pickle.html#module-pickle
  _"Warning: The pickle module is not secure."_

- **Pydantic Security**
  https://docs.pydantic.dev/latest/concepts/strict_mode/

---

## ✅ Security Checklist

### Before Deployment

- [ ] No pickle usage in serialization code
- [ ] All YAML loading uses `safe_load()`
- [ ] Pydantic validation for all configs
- [ ] Function registry with whitelist
- [ ] Secrets via environment variables
- [ ] Path validation for file operations
- [ ] Security audit completed
- [ ] Penetration testing passed

### After Deployment

- [ ] Monitor for suspicious YAML files
- [ ] Regular security audits
- [ ] Incident response plan tested
- [ ] Team trained on secure patterns
- [ ] Dependencies kept up-to-date

---

## 🎯 Conclusion

**Finding**: Pickle-based serialization is **CRITICALLY INSECURE** for user-provided configuration files.

**Impact**: Remote Code Execution (RCE) vulnerability allows attackers to compromise systems by crafting malicious agent YAML files.

**Recommendation**: **Migrate to YAML + Pydantic + Function Registry immediately**. This approach:
- ✅ Prevents code execution
- ✅ Provides type safety
- ✅ Maintains human-readability
- ✅ Enables cross-machine portability

**Timeline**: 2-3 weeks to complete migration (see IMPLEMENTATION_STRATEGY.md)

---

**Last Updated**: 2025-10-13
**Security Level**: CRITICAL
**Action Required**: IMMEDIATE MIGRATION
