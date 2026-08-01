const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const test = require('node:test');
const assert = require('node:assert/strict');
const puppeteer = require('puppeteer');

const root = path.resolve(__dirname, '..');

test('print links remain visually distinguishable from body text', async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    const page = await browser.newPage();
    const css = fs.readFileSync(
      path.join(root, 'static', 'pagedJS', 'css', 'cv.css'),
      'utf8'
    );
    await page.setContent(
      `<style>${css}</style><p>Body <a href="https://example.test">link</a></p>`
    );
    const styles = await page.$eval('a', (link) => {
      const computed = getComputedStyle(link);
      return {
        color: computed.color,
        decoration: computed.textDecorationLine,
      };
    });

    // Links must carry a non-color affordance (WCAG 1.4.1) and meet the
    // AAA 7:1 contrast ratio against the white page (WCAG 1.4.6). The
    // exact color is a design choice and deliberately not pinned here.
    assert.match(styles.decoration, /underline/);
    const channels = styles.color
      .match(/\d+/g)
      .slice(0, 3)
      .map((value) => {
        const c = Number(value) / 255;
        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
    const luminance =
      0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    const contrast = (1.0 + 0.05) / (luminance + 0.05);
    assert.ok(
      contrast >= 7,
      `link contrast ${contrast.toFixed(2)}:1 is below the AAA 7:1 minimum`
    );
  } finally {
    await browser.close();
  }
});

test('accessibility check fails when an expected artifact is absent', () => {
  const missing = path.join(os.tmpdir(), 'cv-output-that-does-not-exist.html');
  const result = spawnSync(
    process.execPath,
    [path.join(root, 'scripts', 'check-accessibility.js')],
    {
      cwd: root,
      encoding: 'utf8',
      env: {
        ...process.env,
        CV_ACCESSIBILITY_FRAGMENT: missing,
        CV_ACCESSIBILITY_PDF_SOURCE: missing,
        CV_ACCESSIBILITY_PDF: missing,
      },
    }
  );

  assert.notEqual(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout + result.stderr, /missing/i);
});

test('accessibility gate checks HTML and tagged PDF artifacts', async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-accessibility-'));
  const fragment = path.join(directory, 'fragment.html');
  const pdfSource = path.join(directory, 'pdf-source.html');
  const pdf = path.join(directory, 'cv.pdf');
  const markup =
    '<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">' +
    '<title>CV</title></head><body><main><section aria-labelledby="works">' +
    '<h1 id="works">Works</h1><ul><li>One work</li></ul>' +
    '</section></main></body></html>';
  fs.writeFileSync(fragment, '<section aria-labelledby="works">' +
    '<h3 id="works">Works</h3><ul><li>One work</li></ul></section>');
  fs.writeFileSync(pdfSource, markup);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  try {
    const page = await browser.newPage();
    await page.setContent(markup);
    await page.pdf({ path: pdf, tagged: true, outline: true });
  } finally {
    await browser.close();
  }

  try {
    const result = spawnSync(
      process.execPath,
      [path.join(root, 'scripts', 'check-accessibility.js')],
      {
        cwd: root,
        encoding: 'utf8',
        env: {
          ...process.env,
          CV_ACCESSIBILITY_FRAGMENT: fragment,
          CV_ACCESSIBILITY_PDF_SOURCE: pdfSource,
          CV_ACCESSIBILITY_PDF: pdf,
        },
      }
    );
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.match(result.stdout, /PDF: tagged structure/);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
