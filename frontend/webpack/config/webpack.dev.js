const Webpack = require('webpack');
const {merge} = require('webpack-merge');
const commonConfig = require('./webpack.common.js');
const paths = require('../paths');

const DEFAULT_PORT = 9000;

// Backend target for dev-server proxy. Override with LLM_GATE_BACKEND env var.
const backendTarget = process.env.LLM_GATE_BACKEND || 'http://localhost:9981';

module.exports = () => {
    const devConfig = {
        mode: 'development',
        devtool: 'cheap-module-source-map',
        target: 'web',
        output: {
            path: paths.appBuild,
            publicPath: '/',
            filename: 'js/[name].js'
        },
        devServer: {
            host: '0.0.0.0',
            port: DEFAULT_PORT,
            compress: false,
            client: {
                logging: 'none',
                overlay: false
            },
            open: true,
            hot: true,
            historyApiFallback: true,
            proxy: [
                {
                    context: ['/api', '/health', '/v1'],
                    target: backendTarget,
                    changeOrigin: true
                }
            ]
        },
        plugins: [new Webpack.HotModuleReplacementPlugin()],
        optimization: {
            minimize: false,
            minimizer: [],
            splitChunks: {
                chunks: 'all',
                minSize: 0
            }
        }
    };

    return merge(commonConfig, devConfig);
};
