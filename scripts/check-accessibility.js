/* Run axe-core WCAG checks over the generated CV outputs, headlessly.
 *
 * Two documents are checked:
 *
 *  1. output/Eve-CV.html — the HTML fragment that is transcluded into a
 *     website. It is wrapped in a minimal page scaffold here, because a
 *     fragment alone has no lang or title of its own to test.
 *  2. output/Eve-CV-PDF.html — the print source document. Paged.js is
 *     blocked during the check so that axe sees the semantic source
 *     rather than the paginated layout boxes.
 *
 * The script exits non-zero if any WCAG rule (A, AA, or AAA) is violated,
 * so it can act as a gate in local runs and CI.
 */

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const AXE_PATH = require.resolve('axe-core/axe.min.js');
const WCAG_TAGS = [
  'wcag2a', 'wcag2aa', 'wcag2aaa',
  'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa',
];

const FRAGMENT = path.resolve(__dirname, '..', 'output', 'Eve-CV.html');
const PDF_SOURCE = path.resolve(__dirname, '..', 'output', 'Eve-CV-PDF.html');

async function checkPage(browser, label, load) {
  const page = await browser.newPage();
  await load(page);
  await page.addScriptTag({ path: AXE_PATH });

  const results = await page.evaluate(async (tags) => {
    return await window.axe.run(document, {
      runOnly: { type: 'tag', values: tags },
    });
  }, WCAG_TAGS);

  await page.close();

  console.log(
    `${label}: ${results.violations.length} violation(s), ` +
    `${results.passes.length} rule(s) passed`
  );

  for (const violation of results.violations) {
    console.log(`  [${violation.impact}] ${violation.id}: ${violation.help}`);
    for (const node of violation.nodes.slice(0, 5)) {
      console.log(`    ${node.html.slice(0, 160)}`);
    }
  }

  return results.violations.length;
}

(async () => {
  // sandbox flags: see the note in print.js — only local generated
  // content is ever loaded
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  let violations = 0;

  try {
    if (fs.existsSync(FRAGMENT)) {
      violations += await checkPage(browser, 'HTML fragment', async (page) => {
        const fragment = fs.readFileSync(FRAGMENT, 'utf8');
        const scaffold =
          '<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">' +
          '<title>Publications</title></head><body><h1>Publications</h1>' +
          '<h2>Section scaffold</h2>' + fragment + '</body></html>';
        await page.setContent(scaffold, { waitUntil: 'load' });
      });
    } else {
      console.log('HTML fragment not present; skipping');
    }

    if (fs.existsSync(PDF_SOURCE)) {
      violations += await checkPage(browser, 'PDF source', async (page) => {
        // block Paged.js and remote fonts so axe sees the source semantics
        await page.setRequestInterception(true);
        page.on('request', (request) => {
          const url = request.url();
          if (url.includes('pagedjs') || url.includes('typekit')) {
            request.abort();
          } else {
            request.continue();
          }
        });
        await page.goto('file://' + PDF_SOURCE, { waitUntil: 'load' });
      });
    } else {
      console.log('PDF source not present; skipping');
    }
  } finally {
    await browser.close();
  }

  if (violations > 0) {
    console.error(`\nFAILED: ${violations} WCAG violation(s) found`);
    process.exit(1);
  }

  console.log('\nAll WCAG checks passed');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
