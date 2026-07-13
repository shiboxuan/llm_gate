/**
 * Unified env entry. Business code reads values via @/utils/variable or this file,
 * never directly from process.env at runtime (webpack DefinePlugin / dotenv-webpack
 * injects the values at build time).
 */

const pick = (raw: string | undefined): string => {
    return raw && raw !== 'undefined' ? raw : '';
};

export interface EnvConfig {
    LLM_GATE_HOST: string;
}

export const ENV: EnvConfig = {
    LLM_GATE_HOST: pick(process.env.LLM_GATE_HOST) || '/'
};
