const HtmlWebpackPlugin = require('html-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const WebpackBar = require('webpackbar');
const ForkTsCheckerWebpackPlugin = require('fork-ts-checker-webpack-plugin');
const CopyPlugin = require('copy-webpack-plugin');
const Dotenv = require('dotenv-webpack');
const webpack = require('webpack');
const paths = require('../paths');
const {isDevelopment} = require('../env');
const {imageInlineSizeLimit} = require('../conf');

const cssLoaders = (importLoaders) => [
    isDevelopment ? 'style-loader' : MiniCssExtractPlugin.loader,
    {
        loader: 'css-loader',
        options: {
            modules: undefined,
            sourceMap: isDevelopment,
            importLoaders
        }
    },
    {
        loader: 'postcss-loader',
        options: {
            postcssOptions: {
                plugins: [
                    require('postcss-flexbugs-fixes'),
                    [
                        'postcss-preset-env',
                        {
                            autoprefixer: {
                                grid: true,
                                flexbox: 'no-2009'
                            },
                            stage: 3
                        }
                    ],
                    'postcss-normalize'
                ]
            }
        }
    }
];

const config = {
    entry: {
        app: paths.appIndex
    },
    cache: {
        type: 'filesystem',
        allowCollectingMemory: true,
        buildDependencies: {
            config: [__filename]
        }
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js', '.json'],
        alias: {
            '@': paths.appSrc
        }
    },
    module: {
        rules: [
            {
                test: /\.(tsx?|js)$/,
                loader: 'babel-loader',
                options: {cacheDirectory: true},
                exclude: [/node_modules/, /(.|_)min\.js$/]
            },
            {
                test: /\.css$/,
                use: cssLoaders(1)
            },
            {
                test: /\.less$/,
                use: [
                    ...cssLoaders(2),
                    {
                        loader: 'less-loader',
                        options: {
                            sourceMap: isDevelopment,
                            lessOptions: {
                                javascriptEnabled: true
                            }
                        }
                    }
                ]
            },
            {
                test: [/\.bmp$/, /\.gif$/, /\.jpe?g$/, /\.png$/, /\.avif$/, /\.svg$/],
                type: 'asset',
                parser: {
                    dataUrlCondition: {
                        maxSize: imageInlineSizeLimit
                    }
                }
            },
            {
                test: /\.(eot|ttf|woff|woff2?)$/,
                type: 'asset/resource'
            }
        ]
    },
    plugins: [
        new Dotenv({
            path: '.env',
            safe: false,
            systemvars: true,
            allowEmptyValues: true
        }),
        new webpack.DefinePlugin({
            ...paths.appDefineVariable,
            __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '')
        }),
        new HtmlWebpackPlugin({
            template: paths.appHtml,
            cache: true
        }),
        new CopyPlugin({
            patterns: [
                {
                    context: paths.appPublic,
                    from: '*',
                    to: paths.appBuild,
                    toType: 'dir',
                    noErrorOnMissing: true,
                    globOptions: {
                        dot: true,
                        gitignore: true,
                        ignore: ['**/index.html']
                    }
                }
            ]
        }),
        new WebpackBar({
            name: isDevelopment ? 'RUNNING' : 'BUNDLING',
            color: isDevelopment ? '#52c41a' : '#722ed1'
        }),
        new ForkTsCheckerWebpackPlugin({
            typescript: {
                configFile: paths.appTsConfig
            }
        })
    ]
};

module.exports = config;
