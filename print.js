/* Print the Paged.js-rendered CV to a tagged, accessible PDF.
 *
 * This runs fully headless: it loads the generated HTML from disk (no web
 * server involved), waits for Paged.js to signal that pagination has
 * finished (via the window.PagedConfig `after` hook set in the template),
 * and asks Chromium for a tagged PDF with a document outline, so that the
 * result carries the heading/list/link structure that assistive
 * technology needs, rather than being a flat picture of text.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const PROJECT_ROOT = __dirname;
const INPUT_PATH = '/output/Eve-CV-PDF.html';
const OUTPUT = path.resolve(__dirname, 'output', 'Eve-CV.pdf');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

/* Paged.js loads its stylesheets with fetch(), which browsers refuse on
 * file:// URLs, so the document is served over a loopback-only HTTP
 * server on an ephemeral port for the duration of the print. */
function serveProject() {
  const server = http.createServer((request, response) => {
    const urlPath = decodeURIComponent(new URL(
      request.url, 'http://127.0.0.1'
    ).pathname);
    const filePath = path.join(PROJECT_ROOT, path.normalize(urlPath));

    if (!filePath.startsWith(PROJECT_ROOT) || !fs.existsSync(filePath)) {
      response.writeHead(404);
      response.end('not found');
      return;
    }

    response.writeHead(200, {
      'Content-Type':
        MIME_TYPES[path.extname(filePath)] || 'application/octet-stream',
    });
    fs.createReadStream(filePath).pipe(response);
  });

  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

(async () => {
  // the sandbox flags are needed on Linux distributions that restrict
  // unprivileged user namespaces; the browser only ever loads our own
  // generated files, so this does not process untrusted content
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const server = await serveProject();
  const port = server.address().port;

  try {
    const page = await browser.newPage();

    await page.goto(`http://127.0.0.1:${port}${INPUT_PATH}`, {
      waitUntil: 'networkidle2',
      timeout: 60000,
    });

    // wait for Paged.js to finish laying out the document
    await page.waitForFunction('window.__pagedDone === true', {
      timeout: 120000,
    });

    await page.pdf({
      path: OUTPUT,
      tagged: true,
      outline: true,
      preferCSSPageSize: true,
      printBackground: true,
    });

    console.log('Wrote tagged PDF to ' + OUTPUT);
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
