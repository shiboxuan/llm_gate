import {ENV} from '@/config/env';

// LLM Gate backend host. Same-origin by default ("/").
// Set LLM_GATE_HOST in .env to point to a different backend during development.
export const llmGateHost = ENV.LLM_GATE_HOST || '/';
