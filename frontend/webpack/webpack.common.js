/**
 * webpack.common.js
 * -----------------------------------
 * Common configuration environment
 *
 */

const path = require("path");
const webpack = require("webpack");
const HtmlWebpackPlugin = require('html-webpack-plugin');

// pages in app: map app {module}.js => {page}.html page
const pages = {
	controller: "index",
	monitor: "monitor",
};

module.exports = {
    context: path.resolve(__dirname, ".."),
    resolve: {
        modules: [
            "node_modules",
            // path.resolve(__dirname, "../wasm"),
            path.resolve(__dirname, ".."),
        ]
    },
    entry: Object.keys(pages).reduce((config, page) => {
        config[page] = `./src/${page}/index.js`;
        return config;
    }, {}),
    output: {
        globalObject: "self"
    },
    optimization: {
    splitChunks: {
        chunks: "all",
    },
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                exclude: /node_modules/,
                use: {
                    loader: "babel-loader",
                }
            },
            {
                test: /\.jsx$/,
                exclude: /node_modules/,
                use: {
                    loader: "babel-loader",
                }
            },
            {
                test: /\.css$/,
                use: [
                    { loader: "style-loader" },
                    { loader: "css-loader" }
                ]
            },
            {
                test: /\.(svg)$/,
                use: {
                    loader: "svg-url-loader",
                    options: {
                        noquotes: true
                    }
                }
            }
        ]
    },
    plugins: [].concat(
		Object.entries(pages).map(([entry, page]) => new HtmlWebpackPlugin({
			inject: true,
			template: `./public/${page}.html`,
			filename: `${page}.html`,
			chunks: [entry],
		})),
		[
			new webpack.ProvidePlugin({
				React: "react",
				FileSaver: "file-saver",
			})
		]
	),
};
