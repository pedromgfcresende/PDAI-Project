# Known MCP Server Configurations

Verified configs for popular MCP providers. Each entry includes the correct `.mcp.json` snippet and auth notes.

---

## Miro

**Transport**: HTTP (hosted)
**Auth**: OAuth 2.1 (browser flow via `/mcp auth`)

```json
{
  "miro": {
    "type": "http",
    "url": "https://mcp.miro.com/"
  }
}
```

**Common mistake**: The package `@mirohq/miro-mcp` does NOT exist on npm. Do not use stdio/npx for Miro — it's a hosted HTTP server.

**Notes**:
- Enterprise Plan users need an admin to enable MCP access first
- During OAuth you select which Miro workspace/team to connect
- No API token needed — authentication is purely browser-based OAuth

---

<!-- Add new servers below this line using the same format:

## Provider Name

**Transport**: stdio | http | sse
**Auth**: OAuth / API token / none

```json
{
  "provider-name": {
    ...config...
  }
}
```

**Common mistake**: (if any)
**Notes**: (setup quirks, gotchas)

-->
