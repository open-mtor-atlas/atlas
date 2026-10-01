#!/usr/bin/env node
// mTOR Atlas MCP server (stdio). Read-only access to Oliver's mTOR Atlas:
// evidence-labelled studies, entities, pathway relations and open questions.
// Data: https://mtor-atlas.org/api/v1/ (CC BY 4.0, doi:10.5281/zenodo.22059963).
// The tools themselves are in tools.js, shared with the remote server (worker/).
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Atlas } from './lib.js';
import { createServer } from './tools.js';

await createServer(new Atlas()).connect(new StdioServerTransport());
