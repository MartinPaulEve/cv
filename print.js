const htmlPdf = require('html-pdf-chrome');

const options = {
    completionTrigger: new htmlPdf.CompletionTrigger.Timer(5000),
    chromeFlags: ['--disable-web-security', '--headless']
};

const url = 'http://127.0.0.1:8001/output/Eve-CV-PDF.html';
let pdf = htmlPdf.create(url, options).then((pdf) => pdf.toFile('./output/Eve-CV.pdf'));
