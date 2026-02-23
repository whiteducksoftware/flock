# openclaw-engine-transport Specification

## Purpose
TBD - created by archiving change openclaw-http-transport. Update Purpose after archive.
## Requirements
### Requirement: Gateway Communication Protocol
The OpenClawEngine MUST communicate with the OpenClaw gateway via the documented `/v1/responses` HTTP endpoint.
(Previously: used undocumented `/api/sessions/spawn` endpoint)

#### Scenario: Successful request to responses endpoint
- GIVEN a configured OpenClaw gateway with responses endpoint enabled
- WHEN the engine sends a POST request
- THEN it targets `{gateway_url}/v1/responses`

#### Scenario: Gateway without responses endpoint enabled
- GIVEN a gateway where `responses.enabled` is false
- WHEN the engine sends a request
- THEN it receives a 405 or 404 error
- AND raises a `RuntimeError` with a message suggesting the config change

### Requirement: Request Format
The engine MUST send requests as OpenResponses-compatible JSON with `model`, `input`, optional `instructions`, and `stream: false`.
(Previously: sent spawn-specific payload with `task`, `label`, `runTimeoutSeconds`, `cleanup`)

#### Scenario: Request with agent description
- GIVEN an agent with description "Creates pizza recipes"
- WHEN the engine builds the request payload
- THEN `instructions` is set to "Creates pizza recipes"
- AND `input` contains the schema and input data
- AND `model` is set to `"openclaw"`
- AND `stream` is `false`

#### Scenario: Request without agent description
- GIVEN an agent with no description
- WHEN the engine builds the request payload
- THEN `instructions` is omitted or empty
- AND `input` contains the schema and input data

### Requirement: Authentication
The engine MUST send the gateway token via `Authorization: Bearer <token>` header.
(Previously: same — no change)

#### Scenario: Token present
- GIVEN a GatewayConfig with token "my-token"
- WHEN the engine sends a request
- THEN the `Authorization` header is `Bearer my-token`

#### Scenario: No token configured
- GIVEN a GatewayConfig with no token
- WHEN the engine sends a request
- THEN no `Authorization` header is sent

### Requirement: Agent Targeting
The engine MUST target a specific OpenClaw agent via the `x-openclaw-agent-id` header, defaulting to `"main"`.
(Previously: no agent targeting; spawn created isolated sessions)

#### Scenario: Default agent ID
- GIVEN a GatewayConfig without agent_id
- WHEN the engine sends a request
- THEN the `x-openclaw-agent-id` header is set to `"main"`

#### Scenario: Custom agent ID
- GIVEN a GatewayConfig with agent_id="beta"
- WHEN the engine sends a request
- THEN the `x-openclaw-agent-id` header is set to `"beta"`

### Requirement: Response Parsing
The engine MUST extract the assistant's text content from the OpenResponses output structure (`output[].content[].text`) and parse it as JSON.
(Previously: extracted from `result` field in spawn response)

#### Scenario: Valid JSON in response output
- GIVEN a response with `output[0].content[0].text` containing valid JSON
- WHEN the engine parses the response
- THEN it returns the parsed JSON as a dict

#### Scenario: Malformed JSON in response output
- GIVEN a response with `output[0].content[0].text` containing invalid JSON
- WHEN the engine parses the response
- THEN it raises a `ValueError` for repair attempt

#### Scenario: Empty output
- GIVEN a response with no output items
- WHEN the engine parses the response
- THEN it raises a `ValueError`

### Requirement: Error Handling
The engine MUST map HTTP error codes to exceptions:
- 401/403 → `ValueError` (auth failure, not retried)
- 400 → `RuntimeError` (bad request, not retried)
- 429 → `RuntimeError` (rate limited, retried)
- 5xx → `RuntimeError` (server error, retried)
- Response `status: "failed"` → `RuntimeError` (retried)
(Previously: similar mapping but for spawn-specific errors)

#### Scenario: Auth failure
- GIVEN a gateway returning 401
- WHEN the engine processes the response
- THEN it raises `ValueError` with "auth" in the message
- AND the error is NOT retried

#### Scenario: Server error
- GIVEN a gateway returning 500
- WHEN the engine processes the response
- THEN it raises `RuntimeError`
- AND the error IS retried

#### Scenario: Rate limit
- GIVEN a gateway returning 429
- WHEN the engine processes the response
- THEN it raises `RuntimeError`
- AND the error IS retried (immediate, same as transient errors)

### Requirement: Agent ID Configuration
`GatewayConfig` MUST support an optional `agent_id` field (default: `"main"`) to control which OpenClaw agent handles requests.

#### Scenario: Default agent ID
- GIVEN a GatewayConfig without agent_id
- WHEN the config is constructed
- THEN `agent_id` is `"main"`

#### Scenario: Custom agent ID
- GIVEN a GatewayConfig with agent_id="beta"
- WHEN the config is constructed
- THEN `agent_id` is `"beta"`

### Requirement: Gateway Endpoint Documentation
Documentation MUST state that the OpenClaw gateway requires `gateway.http.endpoints.responses.enabled: true`.

#### Scenario: Documentation includes config requirement
- GIVEN the OpenClaw integration guide
- WHEN a user reads the setup section
- THEN it includes the required gateway config snippet

<!-- removed obsolete REMOVED section for new capability spec -->

