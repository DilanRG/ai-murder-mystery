---
description: How to add a new LLM backend provider (AI Horde, local llama.cpp, etc.)
---

# Add a New LLM Backend Provider

The LLM layer uses an abstract base class. Adding a new provider means creating a new client class.

## Steps

### 1. Create a new client file
Create `backend/llm/<provider_name>_client.py`.

### 2. Implement the `LLMClientBase` interface
```python
from llm.api_client import LLMClientBase, LLMResponse

class NewProviderClient(LLMClientBase):
    """Client for <Provider Name>."""

    async def generate(self, messages: list[dict], **kwargs) -> LLMResponse:
        # Implement the API call
        ...

    async def check_connection(self) -> bool:
        # Return True if the provider is reachable
        ...
```

### 3. Register the provider
In `backend/llm/api_client.py`, add the new provider to the `get_client()` factory function:
```python
def get_client(provider: str) -> LLMClientBase:
    match provider:
        case "openrouter":
            return OpenRouterClient()
        case "<new_provider>":
            from llm.<provider_name>_client import NewProviderClient
            return NewProviderClient()
```

### 4. Add config options
In `backend/config/settings.py`, add any provider-specific settings (API URL, auth, etc.).

### 5. Test
// turbo
```
cd c:\random scripting\game\backend
python -m pytest tests/test_llm_client.py -v -k "new_provider"
```
