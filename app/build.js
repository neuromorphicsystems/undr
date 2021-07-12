const fs = require('fs');
const path = require('path');

const copy = (source, target) => {
    fs.mkdirSync(target);
    for (const entry of fs.readdirSync(source, {withFileTypes: true})) {
        if (entry.isFile()) {
            fs.copyFileSync(path.join(source, entry.name), path.join(target, entry.name));
        } else if (entry.isDirectory()) {
            copy(path.join(source, entry.name), path.join(target, entry.name));
        }
    }
};

fs.rmSync(path.join(__dirname, 'undr'), {recursive: true, force: true});
copy(path.join(path.dirname(__dirname), 'source'), path.join(__dirname, 'undr'));
fs.copyFileSync(
    path.join(path.dirname(__dirname), 'specification', 'undr_schema.json'),
    path.join(__dirname, 'undr', 'undr_schema.json')
);
fs.copyFileSync(
    path.join(path.dirname(__dirname), 'specification', '-index_schema.json'),
    path.join(__dirname, 'undr', '-index_schema.json')
);
fs.copyFileSync(
    path.join(path.dirname(__dirname), 'undr_default.toml'),
    path.join(__dirname, 'undr', 'undr_default.toml')
)
