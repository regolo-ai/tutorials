# How Regolo Diagram Studio works

## Pipeline

For one run, `diagram_wizard/server.py` makes three calls to the chat API, in this order:

1. **Extract components.** The model reads the project skeleton and returns JSON with at most 6 nodes and 8 edges, tailored to the chosen diagram type.
2. **Draw the diagram.** The model gets the topology and the structural rules of the chosen layout and returns an inline SVG on a 4px grid. The SVG is accepted only if it follows the layout (for example a delta ledger must contain BEFORE and AFTER); otherwise the built-in builder in `regolo_diagram_tui.py` draws the layout from the topology.
3. **Write the knowledge base.** The model gets the topology and the skeleton and writes the Markdown sections. It runs at the same time as step 2, because it needs only the topology.

Stage timings, tokens and cost are recorded for each call and shown in the result.

## Run modes

| Mode | What runs |
|---|---|
| Regolo routing | step 1 on `brick-complexity-pro`, steps 2 and 3 on the model you chose. If the router's JSON is unusable, step 1 is repeated on your model. |
| Single model | steps 1 to 3 on your model |
| Compare on my repo | two runs in parallel: a **baseline** (the same files uncompressed, first 12 KB each, one model) and the **optimized** run (compressed skeleton, routing) |

Costs come from `diagram_wizard/prices.json`. A model without a price shows tokens only and `n/a` for cost.

## How the folder is read

The server reads the folder itself, because a browser cannot reveal a real path and its folder picker uploads every file.

- **`.gitignore` is honoured.** In a git repository the list comes from `git ls-files --cached --others --exclude-standard`, which includes nested and global ignore rules. Outside git, the `.gitignore` files are parsed (negation, `**`, anchored and directory-only rules).
- **Always skipped:** `node_modules`, `.git`, build output, dot files such as `.env`, lock files, and names containing secret, credential or private.
- **Selection:** readable code and config files, ranked so that compose files, SQL and schema files, Terraform and Kubernetes manifests, entry points and manifests come first, with at most 16 files and 12 KB of each.
- **Compression:** comments are dropped and each file is cut to 35 lines and 1,400 characters. Values on lines with key, secret, token or password in the name are replaced by `<redacted>`, also in the uncompressed baseline.

## Privacy and the local server

- The API key lives in the browser tab and is sent to the local server on each request, which forwards it to the Regolo API. It is not written to disk and the server never reads `.env`.
- The server listens on `127.0.0.1` only. It rejects requests with a foreign `Host` header and cross-site POSTs.
- Only the skeleton of the selected files is sent to the model.

## Diagram layouts

The six layouts follow diagram types of the open source [diagram-design](https://github.com/cathrynlavery/diagram-design) project: architecture and containment, architecture delta, database schema, sequence, data flow and deployment. Regolo Diagram Studio reimplements the layouts with its own builders and prompts; it does not run the diagram-design skill itself.

## Troubleshooting

- *"Regolo rejected this API key"*: copy the whole key; it must belong to an account with access to the models endpoint.
- *The folder dialog does not open*: paste the path in the field instead. The dialog needs `osascript` (macOS) or `zenity` (Linux).
- *"That folder has too many files"*: choose a specific project, not a parent folder of many projects.
- *The diagram looks plain*: the model's SVG did not follow the layout and the built-in layout was used. Try a larger model.
