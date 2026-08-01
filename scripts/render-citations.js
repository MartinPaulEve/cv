/* Render CSL-JSON items to formatted bibliography entries, in one process.
 *
 * Usage: node render-citations.js <style.csl> <locale.xml>
 * stdin:  a JSON array of CSL-JSON items
 * stdout: a JSON array of formatted HTML entries, one per item, in order
 *
 * Each item is rendered as its own single-entry bibliography. That is
 * deliberate: rendering them together would make CSL substitute repeated
 * author names with em-dashes, which is wrong for a CV where every entry
 * should carry its authors.
 */

const fs = require('fs');
const CSL = require('citeproc');

const [, , stylePath, localePath] = process.argv;

const style = fs.readFileSync(stylePath, 'utf8');
const locale = fs.readFileSync(localePath, 'utf8');
const items = JSON.parse(fs.readFileSync(0, 'utf8'));

const itemsById = {};
for (const item of items) {
  itemsById[item.id] = item;
}

const engine = new CSL.Engine(
  {
    retrieveLocale: () => locale,
    retrieveItem: (id) => itemsById[id],
  },
  style
);

const entries = items.map((item) => {
  engine.updateItems([item.id]);
  const bibliography = engine.makeBibliography();
  return bibliography[1][0];
});

process.stdout.write(JSON.stringify(entries));
