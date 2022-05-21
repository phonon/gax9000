/**
 * webpack.dev.js
 * -----------------------------------
 * Development configuration environment
 *
 * Notes:
 * - entry '@babel/polyfill' required for async/await
 */

'use strict';

const ReactRefreshWebpackPlugin = require('@pmmmwh/react-refresh-webpack-plugin');
const CopyPlugin = require('copy-webpack-plugin');
const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');
const path = require('path');
const webpack = require('webpack');

module.exports = merge(common, {
	mode: 'development',
	devtool: 'inline-source-map',
	devServer: {
		static: {
			publicPath: 'http://localhost/',
			directory: path.resolve(__dirname, '..', 'public'),
		},
		compress: true,
		port: 80,
		hot: true
	},
	watchOptions: {
		ignored: /node_modules/,
	},
	output: {
		path: path.resolve(__dirname, '../build'),
		filename: '[name].js',
	},
	module: {
		rules: [
			{
				test: /\.(png|jpg|gif)$/,
				loader: 'file-loader',
				options: {
					outputPath: 'images/',
					name: '[name].[ext]'
				}
			},
		]
	},
	plugins: [
		new ReactRefreshWebpackPlugin(),
		// new CopyPlugin([
		// 	{ from: path.resolve(__dirname, '../lib') },
		// ]),
	]

});
