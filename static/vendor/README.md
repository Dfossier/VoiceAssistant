# Vendor Libraries

This directory contains local copies of external libraries to avoid CORS and OpaqueResponseBlocking issues.

## Instructions to add TailwindCSS:

1. Download the TailwindCSS standalone CLI or the CDN build
2. Save it as `tailwind.min.css` in this directory
3. Update the HTML to reference the local file instead of the CDN

For now, we're using the CDN version, but if CORS issues persist, download a local copy.