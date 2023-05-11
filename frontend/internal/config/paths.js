'use strict';

const path = require('path');
const fs = require('fs');
const url = require('url');

// Make sure any symlinks in the project folder are resolved:
// https://github.com/facebook/create-react-app/issues/637
const appDirectory = fs.realpathSync(process.cwd());
const resolveApp = relativePath => path.resolve(appDirectory, relativePath);

const envPublicUrl = process.env.PUBLIC_URL;

function ensureSlash(inputPath, needsSlash) {
  const hasSlash = inputPath.endsWith('/');
  if (hasSlash && !needsSlash) {
    return inputPath.substr(0, inputPath.length - 1);
  } else if (!hasSlash && needsSlash) {
    return `${inputPath}/`;
  } else {
    return inputPath;
  }
}

const getPublicUrl = appPackageJson =>
  envPublicUrl || require(appPackageJson).homepage;

// We use `PUBLIC_URL` environment variable or "homepage" field to infer
// "public path" at which the app is served.
// Webpack needs to know it to put the right <script> hrefs into HTML even in
// single-page apps that may serve index.html for nested URLs like /todos/42.
// We can't use a relative path in HTML because we don't want to load something
// like /todos/42/static/js/bundle.7289d.js. We have to know the root.
function getServedPath(appPackageJson) {
  const publicUrl = getPublicUrl(appPackageJson);
  const servedUrl =
    envPublicUrl || (publicUrl ? url.parse(publicUrl).pathname : '/');
  return ensureSlash(servedUrl, true);
}

const moduleFileExtensions = [
  'web.mjs',
  'mjs',
  'web.js',
  'js',
  'web.ts',
  'ts',
  'web.tsx',
  'tsx',
  'json',
  'web.jsx',
  'jsx',
];

// Resolve file paths in the same order as webpack
const resolveModule = (resolveFn, filePath) => {
  const extension = moduleFileExtensions.find(extension =>
    fs.existsSync(resolveFn(`${filePath}.${extension}`))
  );

  if (extension) {
    return resolveFn(`${filePath}.${extension}`);
  }

  return resolveFn(`${filePath}.js`);
};

const pages = [
    {
        name: 'expenses_page',
        html: resolveApp('public/expenses_page.html'),
        indexJs: resolveModule(resolveApp, 'src/expenses')
    },
    {
        name: 'payment_schedule',
        html: resolveApp('public/payment_schedule.html'),
        indexJs: resolveModule(resolveApp, 'src/payment_schedule')
    },

    // staff
    {
        name: 'workers_list',
        html: resolveApp('public/workers_list.html'),
        indexJs: resolveModule(resolveApp, 'src/workers_list')
    },
    {
        name: 'worker_documents',
        html: resolveApp('public/worker_documents.html'),
        indexJs: resolveModule(resolveApp, 'src/worker_documents')
    },
    {
        name: 'contracts_list',
        html: resolveApp('public/contracts_list.html'),
        indexJs: resolveModule(resolveApp, 'src/contracts_list')
    },

    // delivery
    {
        name: 'delivery_page',
        html: resolveApp('public/delivery_page.html'),
        indexJs: resolveModule(resolveApp, 'src/delivery_page')
    },
    {
        name: 'photo_checking_page',
        html: resolveApp('public/photo_checking_page.html'),
        indexJs: resolveModule(resolveApp, 'src/photo_checking_page')
    },
    {
        name: 'photo_global_dashboard',
        html: resolveApp('public/photo_global_dashboard.html'),
        indexJs: resolveModule(resolveApp, 'src/photo_global_dashboard')
    },
    {
        name: 'delivery_requests_report_page',
        html: resolveApp('public/delivery_requests_report_page.html'),
        indexJs: resolveModule(resolveApp, 'src/delivery_requests_report_page')
    },
    {
        name: 'delivery_imports_report_page',
        html: resolveApp('public/delivery_imports_report_page.html'),
        indexJs: resolveModule(resolveApp, 'src/delivery_imports_report_page')
    },
    {
        name: 'delivery_customers_page',
        html: resolveApp('public/delivery_customers_page.html'),
        indexJs: resolveModule(resolveApp, 'src/delivery_customers_page')
    },
];

// config after eject: we're in ./config/
module.exports = {
  dotenv: resolveApp('.env'),
  appPath: resolveApp('.'),
  appBuild: resolveApp('build'),
  appPublic: resolveApp('public'),
  appPages: pages,
  appPackageJson: resolveApp('package.json'),
  appSrc: resolveApp('src'),
  appTsConfig: resolveApp('tsconfig.json'),
  appJsConfig: resolveApp('jsconfig.json'),
  yarnLockFile: resolveApp('yarn.lock'),
  testsSetup: resolveModule(resolveApp, 'src/setupTests'),
  proxySetup: resolveApp('src/setupProxy.js'),
  appNodeModules: resolveApp('node_modules'),
  publicUrl: getPublicUrl(resolveApp('package.json')),
  servedPath: getServedPath(resolveApp('package.json')),
};



module.exports.moduleFileExtensions = moduleFileExtensions;
