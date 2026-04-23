#!/usr/bin/env node
// Convert SVG to PNG using Puppeteer/Chromium (supports foreignObject).
// Usage: node svg-to-png.js <input.svg> <output.png> [scale]
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
  const [,, svgPath, pngPath, scaleStr] = process.argv;
  if (!svgPath || !pngPath) {
    console.error('Usage: svg-to-png.js <input.svg> <output.png> [scale]');
    process.exit(1);
  }
  const scale = parseInt(scaleStr || '2', 10);
  const svgAbs = path.resolve(svgPath);
  if (!fs.existsSync(svgAbs)) {
    console.error(`SVG not found: ${svgAbs}`);
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  await page.goto(`file://${svgAbs}`, { waitUntil: 'networkidle0' });

  // Get SVG intrinsic dimensions from viewBox or width/height attributes
  const dims = await page.evaluate(() => {
    const svg = document.querySelector('svg');
    if (!svg) return null;
    const vb = svg.viewBox.baseVal;
    if (vb && vb.width > 0) return { w: vb.width, h: vb.height };
    return {
      w: parseFloat(svg.getAttribute('width')) || 800,
      h: parseFloat(svg.getAttribute('height')) || 600,
    };
  });
  if (!dims) {
    console.error('No SVG element found');
    await browser.close();
    process.exit(1);
  }

  await page.setViewport({
    width: Math.ceil(dims.w),
    height: Math.ceil(dims.h),
    deviceScaleFactor: scale,
  });
  // Re-navigate after viewport change to get proper layout
  await page.goto(`file://${svgAbs}`, { waitUntil: 'networkidle0' });
  await page.screenshot({ path: pngPath, fullPage: true, omitBackground: false });
  await browser.close();
})();
