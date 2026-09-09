#!/usr/bin/env node
/**
 * REGOLO Demo - Node.js MCP Server
 * Illustrates standard tool registration in Javascript/Typescript.
 */

const readline = require("readline");

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

function handleMessage(line) {
  if (!line.trim()) return;
  try {
    const req = JSON.parse(line);
    const msgId = req.id;
    let resp;

    if (req.method === "initialize") {
      resp = {
        jsonrpc: "2.0",
        id: msgId,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "regolo-node-helper", version: "1.0.0" }
        }
      };
    } else if (req.method === "tools/list") {
      resp = {
        jsonrpc: "2.0",
        id: msgId,
        result: {
          tools: [
            {
              name: "json_beautify",
              description: "Format and validate JSON payloads with customizable indentation spaces.",
              inputSchema: {
                type: "object",
                properties: {
                  rawJson: {
                    type: "string",
                    description: "Valid JSON string to format."
                  },
                  indent: {
                    type: "number",
                    description: "Number of indentation spaces (default 2)."
                  }
                },
                required: ["rawJson"]
              }
            }
          ]
        }
      };
    } else {
      resp = { jsonrpc: "2.0", id: msgId, result: {} };
    }

    process.stdout.write(JSON.stringify(resp) + "\n");
  } catch (err) {
    process.stdout.write(
      JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32603, message: err.message } }) + "\n"
    );
  }
}

rl.on("line", handleMessage);
