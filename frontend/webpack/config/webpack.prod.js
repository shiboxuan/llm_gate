const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const {BundleAnalyzerPlugin} = require('webpack-bundle-analyzer');
const CompressionPlugin = require('compression-webpack-plugin');
const {merge} = require('webpack-merge');
const commonConfig = require('./webpack.common.js');
const paths = require('../paths');
const {shouldOpenAnalyzer, ANALYZER_HOST, ANALYZER_PORT} = require('../conf');

const prodConfig = {
    mode: 'production',
    target: 'browserslist',
    output: {
        path: paths.appBuild,
        filename: 'js/[name].[contenthash:8].js',
        assetModuleFilename: 'images/[name].[contenthash:8].[ext]',
        publicPath: process.env.PUBLIC_PATH || '/',
        clean: true
    },
    plugins: [
        new MiniCssExtractPlugin({
            filename: 'css/[name].[contenthash:8].css',
            chunkFilename: 'css/[name].[contenthash:8].chunk.css',
            ignoreOrder: true
        }),
        new CompressionPlugin({
            test: /\.js$|\.html$|.\css/,
            threshold: 10240,
            deleteOriginalAssets: false
        })
    ],
    optimization: {
        minimizer: [
            new TerserPlugin({
                extractComments: false
            }),
            new CssMinimizerPlugin()
        ],
        splitChunks: {
            automaticNameDelimiter: '-',
            chunks: 'all',
            cacheGroups: {
                commons: {
                    test: /[\\/]node_modules[\\/](react|react-dom)[\\/]/,
                    name: 'commons',
                    chunks: 'all',
                    minSize: 0,
                    maxInitialRequests: 3,
                    priority: -10
                },
                utilCommon: {
                    name: 'util-common',
                    minSize: 0,
                    minChunks: 2,
                    priority: -20
                }
            }
        }
    }
};

if (shouldOpenAnalyzer) {
    prodConfig.plugins.push(
        new BundleAnalyzerPlugin({
            analyzerMode: 'server',
            analyzerHost: ANALYZER_HOST,
            analyzerPort: ANALYZER_PORT
        })
    );
}

module.exports = merge(commonConfig, prodConfig);
