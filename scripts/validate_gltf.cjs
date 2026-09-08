const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const packageDirectory = path.join(root, '.local/gltf-validation/node_modules/gltf-validator');
const validator = require(packageDirectory);
const packageVersion = JSON.parse(fs.readFileSync(path.join(packageDirectory, 'package.json'), 'utf8')).version;
if (packageVersion !== '2.0.0-dev.3.10') {
  throw new Error('Install the pinned validator: npm install --prefix .local/gltf-validation --no-save --ignore-scripts gltf-validator@2.0.0-dev.3.10');
}

(async () => {
  const relativeModel = process.argv[2] || 'demo/public/models/room.glb';
  const relativeReport = process.argv[3] || 'docs/gltf-validation.json';
  const relativeRun = process.argv[4] || 'docs/gltf-validation-run.json';
  const filename = path.join(root, relativeModel);
  const source = fs.readFileSync(filename);
  const sha256 = crypto.createHash('sha256').update(source).digest('hex');
  const startedAt = new Date().toISOString();
  const options = {uri: relativeModel, format: 'glb', maxIssues: 0, writeTimestamp: true};
  const externalRequests = [];
  const report = await validator.validateBytes(new Uint8Array(source), {
    ...options,
    externalResourceFunction: async uri => {
      externalRequests.push(uri);
      throw new Error('Self-contained GLB unexpectedly requested an external resource: ' + uri);
    }
  });
  fs.writeFileSync(path.join(root, relativeReport), JSON.stringify(report, null, 2) + '\n');
  const currentSha256 = crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
  const provenance = {
    tool: 'KhronosGroup glTF-Validator official npm package',
    package: 'gltf-validator',
    packageVersion,
    validatorVersion: validator.version(),
    officialSource: 'https://github.com/KhronosGroup/glTF-Validator',
    registry: 'https://registry.npmjs.org',
    source: relativeModel,
    sourceBytes: source.length,
    sourceSha256: sha256,
    sourceSha256AfterValidation: currentSha256,
    sourceUnchangedDuringValidation: sha256 === currentSha256,
    startedAt,
    completedAt: new Date().toISOString(),
    options,
    externalResourceRequests: externalRequests,
    ignoredIssues: [],
    severityOverrides: {},
    fullReport: relativeReport,
    reportWasFiltered: false
  };
  fs.writeFileSync(path.join(root, relativeRun), JSON.stringify(provenance, null, 2) + '\n');
  const byCode = {};
  for (const m of report.issues.messages) byCode[m.code] = (byCode[m.code] || 0) + 1;
  console.log(JSON.stringify({
    validatorVersion: report.validatorVersion,
    sourceSha256: sha256,
    sourceUnchanged: sha256 === currentSha256,
    issues: {...report.issues, messages: undefined},
    countsByCode: byCode,
    firstErrors: report.issues.messages.filter(m => m.severity === 0).slice(0, 10),
    firstWarnings: report.issues.messages.filter(m => m.severity === 1).slice(0, 10)
  }, null, 2));
  if (report.issues.numErrors || report.issues.numWarnings || report.issues.truncated || sha256 !== currentSha256) process.exitCode = 1;
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
