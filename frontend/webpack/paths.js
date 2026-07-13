const path = require('path');
const fs = require('fs');

const appDirectory = fs.realpathSync(process.cwd());

function resolveApp(relativePath) {
    return path.resolve(appDirectory, relativePath);
}

const moduleFileExtensions = ['ts', 'tsx', 'js', 'jsx'];

function resolveModule(resolveFn, filePath) {
    const extension = moduleFileExtensions.find((ex) => fs.existsSync(resolveFn(`${filePath}.${ex}`)));
    if (extension) {
        return resolveFn(`${filePath}.${extension}`);
    }
    return resolveFn(`${filePath}.ts`);
}

function resolveDefineVariable() {
    const config = {};
    for (const key in process.env) {
        if (key.startsWith('LLM_GATE') || key === 'APP_ENV' || key === 'NODE_ENV' || key === 'PUBLIC_PATH') {
            config[`process.env.${key}`] = JSON.stringify(process.env[`${key}`]);
        }
    }
    return config;
}

module.exports = {
    resolveApp,
    appDefineVariable: resolveDefineVariable(),
    appBuild: resolveApp('build'),
    appPublic: resolveApp('public'),
    appIndex: resolveModule(resolveApp, 'src/index'),
    appHtml: resolveApp('public/index.html'),
    appNodeModules: resolveApp('node_modules'),
    appSrc: resolveApp('src'),
    appPackageJson: resolveApp('package.json'),
    appTsConfig: resolveApp('tsconfig.json'),
    moduleFileExtensions
};
