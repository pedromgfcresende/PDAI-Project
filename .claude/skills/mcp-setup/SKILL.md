---
name: mcp-setup
description: "Diagnose and fix MCP (Model Context Protocol) server connection issues in Claude Code. Use this skill whenever the user mentions MCP servers not connecting, .mcp.json configuration, adding a new MCP server, 'Failed to reconnect', MCP authentication problems, or asks how to set up any MCP integration. Also trigger when the user mentions specific MCP providers like Miro, Obsidian, Slack, GitHub, etc. in the context of connecting them to Claude Code."
---

# MCP Setup & Troubleshooting

Help users configure, diagnose, and fix MCP server connections in Claude Code.

## Diagnostic Workflow

When a user reports an MCP issue, work through these steps:

### 1. Identify the problem

Read the `.mcp.json` file in the project root (or `~/.claude/.mcp.json` for global config). Common failure modes:

- **Wrong package name**: The npm package doesn't exist or is misspelled. Test with `npx -y <package> --version 2>&1` to verify.
- **Missing `type` field**: HTTP and SSE servers require `"type": "http"` or `"type": "sse"` explicitly. Without it, Claude Code defaults to stdio and the connection fails silently.
- **Auth not completed**: OAuth-based servers (like Miro) need `/mcp auth` after config is added.
- **Bad API token**: Token expired, revoked, or wrong env var name.
- **Network/firewall**: Hosted servers may be unreachable. Test with `curl -s -o /dev/null -w "%{http_code}" <url>`.

### 2. Check the known servers reference

Before searching the web, check `references/known-servers.md` for the correct config of popular MCP servers. This file contains verified configurations that have been tested and confirmed working.

If the server isn't in the reference file, research the correct setup:
- Search npm for the package: `npm search <provider> mcp`
- Check if the provider offers a hosted HTTP endpoint (increasingly common — these don't need npm)
- Look for the provider's official MCP documentation

### 3. Fix the config

Write the corrected `.mcp.json`. The file lives in the project root for project-scoped servers, or `~/.claude/.mcp.json` for global ones.

### 4. Authenticate if needed

- **OAuth servers**: Tell the user to run `/mcp` then `/mcp auth`
- **API token servers**: Help them find where to generate the token and set it in the `env` block

## .mcp.json Format Reference

The config file supports three transport types:

### stdio — Local process (npm packages)

The server runs as a local subprocess. Most community MCP servers use this.

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@scope/package-name"],
      "env": {
        "API_KEY": "your-key-here"
      }
    }
  }
}
```

### http — Hosted HTTP server

The server is hosted remotely. Official provider servers increasingly use this. The `"type": "http"` field is **required** — omitting it causes silent failure.

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://mcp.provider.com/"
    }
  }
}
```

### sse — Server-Sent Events

Similar to HTTP but uses SSE protocol for streaming. Less common.

```json
{
  "mcpServers": {
    "server-name": {
      "type": "sse",
      "url": "https://mcp.provider.com/sse"
    }
  }
}
```

## Multiple servers

You can define multiple servers in one file:

```json
{
  "mcpServers": {
    "miro": {
      "type": "http",
      "url": "https://mcp.miro.com/"
    },
    "obsidian": {
      "command": "npx",
      "args": ["-y", "obsidian-mcp"],
      "env": {}
    }
  }
}
```

## Gotchas

- **npm 404 errors**: If `npx` returns a 404, the package name is wrong. Don't guess — search npm or check the provider's docs. Many providers have switched from npm packages to hosted HTTP servers.
- **`type` field**: Only needed for `http` and `sse`. Stdio servers infer the type from `command`. But for HTTP/SSE, forgetting `type` is the #1 config mistake.
- **Enterprise restrictions**: Some providers (like Miro) require an admin to enable MCP access on Enterprise plans.
- **OAuth flow**: After adding an OAuth-based server config, the user must run `/mcp auth` to complete the browser-based login. The server won't work until this is done.
