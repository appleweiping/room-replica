// Run the Khronos glTF validator on the web model and fail on any error.
//
//   npm install --prefix .local/gltf-validation --no-save gltf-validator@2.0.0-dev.3.10
//   node scripts/validate_gltf.cjs [path/to/model.glb]
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const validator = require(path.join(root, '.local/gltf-validation/node_modules/gltf-validator'));

(async () => {
  const model = process.argv[2] || 'demo/public/models/room-web.glb';
  const report = await validator.validateBytes(new Uint8Array(fs.readFileSync(path.join(root, model))), {
    uri: model,
    format: 'glb',
    maxIssues: 0,
    externalResourceFunction: async (uri) => {
      throw new Error('The model should be self-contained but asked for ' + uri);
    },
  });
  const byCode = {};
  for (const m of report.issues.messages) byCode[m.code] = (byCode[m.code] || 0) + 1;
  const { numErrors, numWarnings, numInfos, numHints } = report.issues;
  console.log(JSON.stringify({ model, validator: report.validatorVersion, numErrors, numWarnings, numInfos, numHints, byCode }, null, 2));
  if (numErrors > 0) process.exit(1);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
