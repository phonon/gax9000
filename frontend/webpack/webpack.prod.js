/**
 * webpack.prod.js
 * -----------------------------------
 * production environment on AWS
 *
 */

const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const CopyPlugin = require('copy-webpack-plugin');
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;
const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');
const path = require('path');
const webpack = require('webpack');

module.exports = merge(common, {
	mode: 'production',
	watchOptions: {
		ignored: /node_modules/,
	},
	output: {
		path: path.resolve(__dirname, '../build'),
		publicPath: '/',
		filename: 'js/app.js',
		chunkFilename: 'js/app.[name].[id].[hash].js',
		library: 'Nodes',
		libraryTarget: 'var',
		libraryExport: 'default'
	},
	module: {
		rules: [
			{
				test: /\.(png|jpg|gif)$/,
				loader: 'file-loader',
				options: {
					publicPath: '/images/nodes',
					outputPath: 'images/nodes',
					name: '[name].[ext]'
				}
			},
		]
	},
	plugins: [
		new CleanWebpackPlugin(),
		new CopyPlugin([
			{ from: path.resolve(__dirname, '../lib') },
		]),
	]
});

module.exports = mainConfig;
