// Whether to enable bundle package analysis
const shouldOpenAnalyzer = false;
const ANALYZER_HOST = 'localhost';
const ANALYZER_PORT = '8888';

// Resource size limit for inlining images as base64
const imageInlineSizeLimit = 4 * 1024;

module.exports = {
    shouldOpenAnalyzer,
    ANALYZER_HOST,
    ANALYZER_PORT,
    imageInlineSizeLimit
};
